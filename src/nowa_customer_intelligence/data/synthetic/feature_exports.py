"""Write a local Fieldwise feature matrix, metadata and outcome evidence as separate files."""

import argparse
from collections.abc import Iterable
from dataclasses import asdict
from hashlib import file_digest
from json import dumps
from pathlib import Path
from tempfile import TemporaryDirectory

from ..eda_inputs import (
    REFERENCE_CUTOFF,
    fieldwise_reference,
    reference_candidates,
    reference_follow_up,
)
from .churn_experiment import ChurnExperiment, ExperimentEvidenceError
from .feature_matrix import (
    FEATURE_BUNDLE_VERSION,
    FEATURE_SPEC_VERSION,
    FEATURE_SPECS,
    FeatureMatrix,
    assess_feature_quality,
    build_feature_matrix,
)


def _write_rows(path: Path, rows: Iterable[dict]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(dumps(row, default=str, allow_nan=False, separators=(",", ":")) + "\n")


def write_feature_bundle(matrix: FeatureMatrix, destination: Path) -> dict:
    """Create a local bundle with a manifest binding file order and checksums."""
    if destination.exists() or destination.is_symlink():
        raise ExperimentEvidenceError("Feature bundle destination already exists.")
    report = assess_feature_quality(matrix)
    names = tuple(spec.name for spec in FEATURE_SPECS)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=destination.parent, prefix=".phase05-") as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        _write_rows(
            staging / "observations.jsonl",
            (asdict(row) for row in matrix.observations),
        )
        _write_rows(
            staging / "predictors.jsonl",
            (dict(zip(names, row, strict=True)) for row in matrix.predictors),
        )
        _write_rows(
            staging / "prediction_eligibility.jsonl", (asdict(row) for row in matrix.eligibility)
        )
        if matrix.outcomes is not None:
            _write_rows(
                staging / "outcomes.jsonl",
                (
                    asdict(row) | {"binary_target": row.outcome.binary_target}
                    for row in matrix.outcomes
                ),
            )
        checksums = {}
        for path in sorted(staging.iterdir()):
            with path.open("rb") as stream:
                checksums[path.name] = {
                    "sha256": file_digest(stream, "sha256").hexdigest(),
                    "bytes": path.stat().st_size,
                }
        manifest = {
            "bundle_version": FEATURE_BUNDLE_VERSION,
            "feature_spec_version": FEATURE_SPEC_VERSION,
            "scope": "fieldwise-fictional-development",
            "predictor_columns": names,
            "configuration": asdict(matrix.configuration),
            "inputs": [asdict(item) for item in matrix.inputs],
            "internal_evidence_sha256": matrix.evidence_sha256,
            "quality": report,
            "files": checksums,
        }
        (staging / "manifest.json").write_text(
            dumps(manifest, indent=2, default=str, allow_nan=False) + "\n", encoding="utf-8"
        )
        staging.rename(destination)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New local bundle directory.")
    parser.add_argument(
        "--registry", type=Path, required=True, help="Local Fieldwise replay Registry."
    )
    parser.add_argument("--inference-only", action="store_true", help="Omit outcome adjudication.")
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("output directory already exists")
    if args.registry.resolve().is_relative_to(args.output.resolve()):
        parser.error("registry must be outside the bundle")
    experiment = ChurnExperiment(REFERENCE_CUTOFF)
    args.registry.parent.mkdir(parents=True, exist_ok=True)
    with fieldwise_reference(registry_path=args.registry) as (run, source):
        matrix = build_feature_matrix(
            run,
            source,
            experiment,
            reference_candidates(run, experiment),
            simulation_follow_up=None if args.inference_only else reference_follow_up(),
            include_outcomes=not args.inference_only,
        )
        report = write_feature_bundle(matrix, args.output)
    print(
        f"{report['rows']} rows, {report['features']} features, "
        f"{report['duplicate_keys']} duplicate keys."
    )


if __name__ == "__main__":
    main()
