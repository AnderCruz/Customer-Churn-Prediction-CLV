"""Generate and render local evidence for the fixed Phase 06 research protocol."""

import argparse
import platform
from dataclasses import dataclass
from hashlib import file_digest, sha256
from importlib.metadata import version
from json import dumps, loads
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
from joblib import dump
from threadpoolctl import threadpool_limits

from ...data.eda_inputs import (
    REFERENCE_CUTOFF,
    fieldwise_reference,
    reference_candidates,
    reference_follow_up,
)
from ...data.synthetic.churn_experiment import ChurnExperiment
from ...data.synthetic.feature_exports import write_feature_bundle
from ...data.synthetic.feature_matrix import (
    FEATURE_SPEC_VERSION,
    FEATURE_SPECS,
    build_feature_matrix,
)
from .dataset import (
    GROUP_SALT,
    HOLDOUT_END,
    HOLDOUT_SEED,
    MIN_POSITIVE_ACCOUNTS,
    REFERENCE_SEED,
    TRAIN_END,
    TRAIN_GROUP_PERCENT,
    VALIDATION_END,
    Bundle,
    ResolvedObservation,
    load_bundle,
    model_inputs,
    partition,
    support,
)
from .estimators import (
    ADVANCED,
    BASELINES,
    MODEL_SEED,
    FittedCandidate,
    account_intervals,
    churn_scores,
    cohort_errors,
    diagnostics,
    fit_candidates,
    metrics,
    select_candidate,
)

PROTOCOL = "nci-phase06-v1"
HOLDOUT_SCOPE = "fieldwise-fictional-phase06-holdout"
DEFAULT_REFERENCE = Path("data/processed/phase05-fieldwise-final")
DEFAULT_WORKSPACE = Path("data/processed/phase06-research")


def _write(path: Path, report: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(dumps(report, indent=2, allow_nan=False) + "\n")


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True, slots=True)
class Design:
    """Partition membership and the aggregate evidence bound to it."""

    training: tuple[ResolvedObservation, ...]
    validation: tuple[ResolvedObservation, ...]
    holdout: tuple[ResolvedObservation, ...]
    audit: dict


def evaluate_design(
    reference: Bundle, reserve: Bundle | None, unavailable: str | None = None
) -> Design:
    """Verify grouped independence and determine which evidence gates pass."""
    development, exclusions = partition(reference, fresh=False)
    training, validation = development["training"], development["validation"]
    if {row.customer for row in training} & {row.customer for row in validation} or {
        row.key.subscription_id for row in training
    } & {row.key.subscription_id for row in validation}:
        raise ValueError("Development partitions share account or episode identity.")
    holdout = ()
    holdout_exclusions = {}
    if reserve:
        if (
            reference.episodes & reserve.episodes
            or reference.evidence_hash == reserve.evidence_hash
        ):
            raise ValueError("The reserved population is not distinct from the development source.")
        reserved, holdout_exclusions = partition(reserve, fresh=True)
        holdout = reserved["holdout"]
    partitions = {"training": training, "validation": validation, "holdout": holdout}
    counts = {name: support(rows) for name, rows in partitions.items()}
    development_allowed = all(
        counts[name]["positives"] and counts[name]["negatives"] for name in development
    )
    failed = [
        name
        for name, minimum in MIN_POSITIVE_ACCOUNTS.items()
        if counts[name]["positive_customers"] < minimum or not counts[name]["negatives"]
    ]
    audit = {
        "protocol": PROTOCOL,
        "feature_spec": FEATURE_SPEC_VERSION,
        "outcome_policy": "fieldwise-subscription-churn v1",
        "history_days": 90,
        "horizon_days": 30,
        "model_seed": MODEL_SEED,
        "reference_seed": reference.seed,
        "reserved_seed": HOLDOUT_SEED,
        "reserved_namespace": HOLDOUT_SCOPE,
        "group_salt": GROUP_SALT,
        "training_group_percent": TRAIN_GROUP_PERCENT,
        "boundaries": {
            "training_end": TRAIN_END.isoformat(),
            "validation_end": VALIDATION_END.isoformat(),
            "holdout_end": HOLDOUT_END.isoformat(),
        },
        "reference_manifest_sha256": reference.manifest_hash,
        "reference_evidence_sha256": reference.evidence_hash,
        "holdout_manifest_sha256": reserve.manifest_hash if reserve else None,
        "holdout_evidence_sha256": reserve.evidence_hash if reserve else None,
        "reference_inventory": reference.inventory,
        "holdout_inventory": reserve.inventory if reserve else None,
        "reference_coverage": reference.coverage,
        "features": [
            {
                "feature": spec.name,
                "group": spec.category,
                "type": spec.dtype.__name__,
                "nullable": spec.nullable,
                "missing": reference.feature_missingness[spec.name],
                "calculation": spec.calculation,
            }
            for spec in FEATURE_SPECS
        ],
        "support": counts,
        "development_exclusions": exclusions,
        "holdout_exclusions": holdout_exclusions,
        "development_allowed": development_allowed,
        "confirmation_allowed": development_allowed and not failed and reserve is not None,
        "confirmation_support_minimum": MIN_POSITIVE_ACCOUNTS,
        "confirmation_support_failures": failed,
        "holdout_unavailable": unavailable,
    }
    return Design(training, validation, holdout, audit)


def _prepare(reference_path: Path, workspace: Path, *, development_only: bool) -> dict:
    reference = load_bundle(reference_path, seed=REFERENCE_SEED)
    workspace.mkdir(parents=True, exist_ok=False)
    reserve = None
    unavailable = None
    if development_only:
        unavailable = "Fresh population omitted for a development-only run."
    else:
        with fieldwise_reference(
            registry_path=workspace / "holdout.sqlite",
            master_seed=HOLDOUT_SEED,
            client_scope=HOLDOUT_SCOPE,
        ) as (run, source):
            experiment = ChurnExperiment(REFERENCE_CUTOFF)
            matrix = build_feature_matrix(
                run,
                source,
                experiment,
                reference_candidates(run, experiment),
                simulation_follow_up=reference_follow_up(),
            )
            write_feature_bundle(matrix, workspace / "holdout")
        reserve = load_bundle(workspace / "holdout", seed=HOLDOUT_SEED)
    design = evaluate_design(reference, reserve, unavailable)
    _write(workspace / "design.json", design.audit)
    return design.audit


def _selection_detail(candidate: FittedCandidate, rows: tuple[ResolvedObservation, ...]) -> dict:
    threshold = candidate.report["threshold"]
    return {
        "selected": candidate.report["name"],
        "validation_intervals": account_intervals(rows, candidate.validation_scores, threshold),
        "validation_cohorts": cohort_errors(rows, candidate.validation_scores, threshold),
    }


def _run(reference_path: Path, workspace: Path) -> dict:
    previous = loads((workspace / "design.json").read_bytes())
    reference = load_bundle(reference_path, seed=REFERENCE_SEED)
    reserve = (
        load_bundle(workspace / "holdout", seed=HOLDOUT_SEED)
        if previous["holdout_manifest_sha256"] is not None
        else None
    )
    design = evaluate_design(reference, reserve, previous["holdout_unavailable"])
    if design.audit != previous:
        raise ValueError("The pre-fit audit or source provenance changed after preparation.")
    if not design.audit["development_allowed"]:
        raise ValueError("Both development partitions must contain both classes before fitting.")
    start = workspace / "run-started.json"
    _write(start, {"design_sha256": _hash(workspace / "design.json")})
    with TemporaryDirectory(dir=workspace, prefix=".results-") as temporary, threadpool_limits(1):
        staging = Path(temporary) / "results"
        staging.mkdir()
        baseline = fit_candidates(BASELINES, design.training, design.validation)
        baseline_rows = [candidate.report for candidate in baseline.values()]
        logistic = select_candidate(baseline_rows[1:])
        base_report = {
            "design": design.audit,
            "candidates": baseline_rows,
            **_selection_detail(baseline[logistic], design.validation),
        }
        _write(staging / "baseline.json", base_report)
        advanced = fit_candidates(ADVANCED, design.training, design.validation)
        all_candidates = baseline | advanced
        selected = select_candidate([candidate.report for candidate in all_candidates.values()])
        winner = all_candidates[selected]
        threshold = winner.report["threshold"]
        # Record the trained artefact, threshold and full metric set before scoring.
        dump(winner.pipeline, staging / "selected.joblib")
        frozen = {
            "protocol": PROTOCOL,
            "design_sha256": _hash(workspace / "design.json"),
            "model_sha256": _hash(staging / "selected.joblib"),
            "candidate": selected,
            "parameters": winner.report["parameters"],
            "threshold": threshold,
            "selection": "highest validation AP, earlier declared candidate wins ties",
            "metrics": [
                "average_precision",
                "roc_auc",
                "precision",
                "recall",
                "f1",
                "brier",
                "tn",
                "fp",
                "fn",
                "tp",
            ],
            "environment": {
                "python": platform.python_version(),
                **{name: version(name) for name in ("numpy", "pandas", "scikit-learn", "joblib")},
            },
        }
        _write(workspace / "frozen.json", frozen)
        final = None
        if design.audit["confirmation_allowed"]:
            scores = churn_scores(winner.pipeline, model_inputs(design.holdout))
            target = np.array([row.target for row in design.holdout])
            final = {
                "metrics": metrics(target, scores, threshold),
                **diagnostics(target, scores),
                "intervals": account_intervals(design.holdout, scores, threshold),
                "cohorts": cohort_errors(design.holdout, scores, threshold),
            }
        report = {
            "design": design.audit,
            "baseline_sha256": _hash(staging / "baseline.json"),
            "candidates": [candidate.report for candidate in advanced.values()],
            **_selection_detail(winner, design.validation),
            "frozen": frozen,
            "holdout": final,
        }
        _write(staging / "advanced.json", report)
        _write(
            staging / "manifest.json",
            {name: _hash(staging / name) for name in ("baseline.json", "advanced.json")},
        )
        staging.rename(workspace / "results")
    return report


def load_reports(directory: Path) -> tuple[dict, dict]:
    """Read paired, checksum-verified JSON without deserialising a model."""
    manifest = loads((directory / "manifest.json").read_bytes())
    reports = []
    for name in ("baseline.json", "advanced.json"):
        content = (directory / name).read_bytes()
        if sha256(content).hexdigest() != manifest[name]:
            raise ValueError(f"Research report integrity failed: {name}.")
        reports.append(loads(content))
    baseline, advanced = reports
    if (
        advanced["baseline_sha256"] != manifest["baseline.json"]
        or baseline["design"] != advanced["design"]
        or baseline["design"]["protocol"] != PROTOCOL
    ):
        raise ValueError("Baseline and advanced reports do not share the verified protocol.")
    return baseline, advanced


def main() -> None:
    """Run either the label-only pre-fit gate or the single controlled fit."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "run"))
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument(
        "--development-only",
        action="store_true",
        help="Prepare without generating the reserved population.",
    )
    args = parser.parse_args()
    if args.action == "prepare":
        report = _prepare(args.reference, args.workspace, development_only=args.development_only)
        print(
            dumps(
                {
                    name: report[name]
                    for name in ("support", "confirmation_allowed", "confirmation_support_failures")
                },
                indent=2,
            )
        )
    else:
        if args.development_only:
            parser.error("--development-only is only used with prepare")
        report = _run(args.reference, args.workspace)
        print(
            f"Validation candidate: {report['selected']}. "
            f"Holdout scored: {report['holdout'] is not None}."
        )


if __name__ == "__main__":
    main()
