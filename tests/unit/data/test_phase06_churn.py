"""Check Phase 06 input isolation, temporal maturity and validation-only decisions."""

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from hashlib import sha256
from json import dumps, loads
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import numpy as np
import pandas as pd
import pytest

from nowa_customer_intelligence.data.synthetic.feature_matrix import (
    FEATURE_BUNDLE_VERSION,
    FEATURE_SPEC_VERSION,
    FEATURE_SPECS,
    ObservationKey,
)
from nowa_customer_intelligence.models.churn.dataset import (
    COLUMNS,
    EXTRACTION,
    REFERENCE_SEED,
    TRAIN_END,
    VALIDATION_END,
    Bundle,
    ResolvedObservation,
    development_group,
    load_bundle,
    model_inputs,
    partition,
)
from nowa_customer_intelligence.models.churn.estimators import (
    BASELINES,
    build_pipeline,
    churn_scores,
    diagnostics,
    metrics,
    select_candidate,
    select_threshold,
    threshold_sweep,
)


def feature_row() -> dict:
    values = {int: 1, float: 0.5, Decimal: "79.00", str: "launch"}
    return {spec.name: values[spec.dtype] for spec in FEATURE_SPECS} | {
        "billing_frequency": "monthly",
        "active_users_change": None,
        "latest_sessions": 0,
    }


def write_bundle(tmp_path: Path, invalid_case: str = "") -> None:
    observed = TRAIN_END - timedelta(days=50)
    ledger = []
    for index, state in enumerate(
        ("confirmed_positive", "confirmed_negative", "right_censored", "ineligible"), 1
    ):
        key = {"subscription_id": str(UUID(int=index)), "observed_at": observed.isoformat()}
        target = {"confirmed_positive": 1, "confirmed_negative": 0}.get(state)
        info = {
            "confirmed_positive": "qualified_effective_termination",
            "confirmed_negative": "complete_horizon_without_termination",
        }
        ledger.append(
            (
                {
                    "key": key,
                    "exclusion": None if index < 4 else "insufficient_observation_history",
                },
                {
                    "key": key,
                    "customer_id": f"customer-{index}",
                    "latest_evidence_at": (
                        observed + timedelta(days=1) if invalid_case == "future" else observed
                    ).isoformat(),
                },
                {
                    "key": key,
                    "ascertainment_cutoff": (observed + timedelta(days=30)).isoformat(),
                    "horizon_end": (observed + timedelta(days=30)).isoformat(),
                    "outcome": {"state": state, "reason": info.get(state), "source_ref": "fixture"},
                    "retrospective_training_eligible": index < 3,
                    "binary_target": 0 if index == 3 and invalid_case == "censor" else target,
                },
            )
        )
    values = feature_row()
    if invalid_case == "predictor":
        values["customer_id"] = "unapproved"
    ledgers = {
        "prediction_eligibility": [row[0] for row in ledger],
        "observations": [row[1] for row in ledger[:3]],
        "predictors": [values] * 3,
        "outcomes": [row[2] for row in ledger],
    }
    manifest = {
        "bundle_version": FEATURE_BUNDLE_VERSION,
        "feature_spec_version": FEATURE_SPEC_VERSION,
        "scope": "fieldwise-fictional-development",
        "predictor_columns": COLUMNS,
        "configuration": {
            "experiment": {
                "history_days": 90,
                "horizon_days": 30,
                "extraction_cutoff": EXTRACTION.isoformat(),
            },
            "generation": {
                "scenario_id": "baseline",
                "scenario_version": 1,
                "seed_reference": sha256(
                    b"nowa.synthetic.seed-reference.v1\0" + (42).to_bytes(8, "big")
                ).hexdigest(),
            },
        },
        "internal_evidence_sha256": "fixture",
        "files": {},
    }
    for ledger_name, rows in ledgers.items():
        path = tmp_path / f"{ledger_name}.jsonl"
        data = "".join(dumps(row) + "\n" for row in rows).encode()
        path.write_bytes(data)
        manifest["files"][path.name] = {"bytes": len(data), "sha256": sha256(data).hexdigest()}
    (tmp_path / "manifest.json").write_text(dumps(manifest), encoding="utf-8")


def test_bundle_keeps_decimal_and_missingness_until_model_boundary(tmp_path: Path) -> None:
    write_bundle(tmp_path)
    bundle = load_bundle(tmp_path, seed=REFERENCE_SEED)
    assert bundle.inventory["prediction_eligible"] == 3
    assert [item.target for item in bundle.rows] == [1, 0]
    assert bundle.rows[0].predictors[COLUMNS.index("monthly_recurring_gbp")] == Decimal("79.00")
    frame = model_inputs(bundle.rows)
    assert tuple(frame) == COLUMNS
    assert np.isnan(frame.at[0, "active_users_change"])
    assert frame.at[0, "latest_sessions"] == 0


@pytest.mark.parametrize(
    "case, message",
    [
        ("future", "future predictor"),
        ("predictor", "ordered Phase 05 registry"),
        ("censor", "training eligibility"),
        ("checksum", "bundle integrity"),
    ],
)
def test_bundle_fails_closed_on_invalid_evidence(tmp_path: Path, case: str, message: str) -> None:
    write_bundle(tmp_path, case)
    if case == "checksum":
        path = tmp_path / "manifest.json"
        manifest = loads(path.read_text())
        manifest["files"]["predictors.jsonl"]["sha256"] = "wrong"
        path.write_text(dumps(manifest))
    with pytest.raises(ValueError, match=message):
        load_bundle(tmp_path, seed=REFERENCE_SEED)


def test_temporal_purge_and_account_isolation() -> None:
    train = next(
        f"account-{i}" for i in range(100) if development_group(f"account-{i}") == "training"
    )
    valid = next(
        f"account-{i}" for i in range(100) if development_group(f"account-{i}") == "validation"
    )
    earlier = TRAIN_END - timedelta(days=40)
    row = ResolvedObservation(
        ObservationKey(str(UUID(int=1)), earlier),
        train,
        earlier + timedelta(days=30),
        earlier + timedelta(days=30),
        1,
        (),
    )
    later = replace(
        row,
        key=ObservationKey(str(UUID(int=2)), TRAIN_END),
        horizon=TRAIN_END + timedelta(days=30),
        ascertainment=TRAIN_END + timedelta(days=30),
    )
    boundary = replace(row, ascertainment=TRAIN_END)
    validation = replace(later, customer=valid, key=ObservationKey(str(UUID(int=3)), TRAIN_END))
    after_validation = replace(validation, key=replace(validation.key, observed_at=VALIDATION_END))
    bundle = Bundle(
        (row, later, boundary, validation, after_validation),
        frozenset(),
        REFERENCE_SEED,
        "manifest",
        "evidence",
        {},
        {},
        {},
    )
    partitions, excluded = partition(bundle, fresh=False)
    assert partitions == {"training": (row,), "validation": (validation,)}
    assert excluded == {
        "account_allocated_to_other_partition": 1,
        "label_not_mature_at_boundary": 1,
        "previously_examined_period_or_later": 1,
    }


def test_preprocessing_statistics_do_not_learn_validation_values(tmp_path: Path) -> None:
    write_bundle(tmp_path)
    bundle = load_bundle(tmp_path, seed=REFERENCE_SEED)
    frame = model_inputs(bundle.rows)
    frame["episode_age_days"] = [10.0, 20.0]
    frame["plan_id"] = ["launch", "launch"]
    frame["latest_sessions"] = [0.0, np.nan]
    fitted = build_pipeline(BASELINES[1]).fit(frame, [0, 1])
    preprocessor = fitted.named_steps["preprocessing"]
    numeric = preprocessor.named_transformers_["numeric"]
    base = numeric.named_steps["median"]
    assert base.statistics_[0] == 15
    validation = frame.copy()
    validation["episode_age_days"] = 1_000
    validation["plan_id"] = "new"
    assert np.isfinite(fitted.predict_proba(validation)).all()
    assert base.statistics_[0] == 15
    assert preprocessor.named_transformers_["category"].categories_[0].tolist() == ["launch"]
    flags = preprocessor.named_transformers_["missing"].transform(
        frame[[spec.name for spec in FEATURE_SPECS if spec.nullable]]
    )
    sessions_index = [spec.name for spec in FEATURE_SPECS if spec.nullable].index("latest_sessions")
    assert flags[:, sessions_index].tolist() == [False, True]


def test_metrics_threshold_ties_and_model_selection() -> None:
    target = np.array([0, 1, 0, 1])
    scores = np.array([0.1, 0.4, 0.2, 0.9])
    threshold = select_threshold(threshold_sweep(target, scores))
    observed = metrics(target, scores, threshold)
    assert threshold == 0.4
    assert [observed[key] for key in ("tn", "fp", "fn", "tp")] == [2, 0, 0, 2]
    assert observed["average_precision"] == observed["roc_auc"] == observed["f1"] == 1
    assert select_threshold([{"threshold": 0.2, "f1": 0.4}, {"threshold": 0.5, "f1": 0.4}]) == 0.5
    candidates = [
        {"name": "simple", "validation": {"average_precision": 0.2}, "holdout": 0},
        {"name": "complex", "validation": {"average_precision": 0.2}, "holdout": 1},
    ]
    assert select_candidate(candidates) == "simple"


@pytest.mark.parametrize("classes", [(0, 1), (1, 0)])
def test_churn_scores_follow_class_label_and_preserve_row_order(classes: tuple[int, int]) -> None:
    predictors = pd.DataFrame({"score": [0.7, 0.2, 0.9]})

    def probabilities(frame: pd.DataFrame) -> np.ndarray:
        scores = frame["score"].to_numpy()
        columns = {0: 1 - scores, 1: scores}
        return np.column_stack([columns[label] for label in classes])

    pipeline = SimpleNamespace(
        classes_=np.array(classes),
        predict_proba=probabilities,
    )
    np.testing.assert_array_equal(churn_scores(pipeline, predictors), predictors["score"])


def test_churn_scores_reject_unexpected_class_labels() -> None:
    pipeline = SimpleNamespace(classes_=np.array([0, 2]))
    with pytest.raises(ValueError, match="binary churn classes 0 and 1"):
        churn_scores(pipeline, pd.DataFrame())


@pytest.mark.parametrize(
    ("scores", "ap", "auc", "counts"),
    [
        ([0.1, 0.9, 0.2, 0.8], 1, 1, [2, 0, 0, 2]),
        ([0.9, 0.1, 0.8, 0.2], 5 / 12, 0, [0, 2, 2, 0]),
        ([0.6, 0.6, 0.6, 0.6], 0.5, 0.5, [0, 2, 0, 2]),
        ([0.1, 0.9, 0.6, 0.4], 5 / 6, 0.75, [1, 1, 1, 1]),
    ],
)
def test_class_one_ranking_and_inclusive_threshold(
    scores: list[float], ap: float, auc: float, counts: list[int]
) -> None:
    target = np.array([0, 1, 0, 1])
    probabilities = np.array(scores)
    result = metrics(target, probabilities, threshold=0.6)
    assert result["average_precision"] == pytest.approx(ap)
    assert result["roc_auc"] == pytest.approx(auc)
    assert [result[key] for key in ("tn", "fp", "fn", "tp")] == counts
    _, fp, fn, tp = counts
    assert result["precision"] == pytest.approx(tp / (tp + fp))
    assert result["recall"] == pytest.approx(tp / (tp + fn))
    assert result["f1"] == pytest.approx(2 * tp / (2 * tp + fp + fn))
    assert result["brier"] == pytest.approx(np.mean((target - probabilities) ** 2))


def test_calibration_bin_uses_confirmed_churn_and_includes_score_boundaries() -> None:
    target = np.array([1, 0, 1, 0, 1])
    scores = np.array([0, 0.01, 0.05, 0.35, 1])
    bins = diagnostics(target, scores)["calibration"]
    assert [row["count"] for row in bins] == [1, 1, 1, 0, 2]
    assert [row["positives"] for row in bins] == [1, 0, 1, 0, 1]
    assert [row["observed_rate"] for row in bins] == [1, 0, 1, None, 0.5]
