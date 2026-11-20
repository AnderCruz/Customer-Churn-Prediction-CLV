"""Batch 09 pre-Phase 06 experimental technical spike on fictional data."""

from dataclasses import dataclass, fields
from datetime import timedelta
from decimal import Decimal
from math import isfinite

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    POLICY_ID,
    POLICY_VERSION,
    ChurnExperiment,
    ExperimentEvidenceError,
    utc_instant,
)
from nowa_customer_intelligence.data.synthetic.episodes import (
    EpisodeValidationError,
    _read_supplied_uuid,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import OutcomeState
from nowa_customer_intelligence.data.synthetic.historical_features import HistoricalFeatures
from nowa_customer_intelligence.data.synthetic.modelling_dataset import (
    ModellingDataset,
    ModellingObservation,
    ModellingSplit,
    SplitBoundaries,
    split_modelling_dataset,
)
from nowa_customer_intelligence.data.synthetic.provenance import GateFinding, GateStatus

_NUMERIC = (
    "episode_age_days",
    "recurring_revenue",
    "active_users_mean",
    "sessions_total",
    "events_total",
    "recent_active_users_change",
    "observed_usage_months",
    "expected_usage_months",
    "usage_coverage_complete",
    "invoices_issued",
    "invoices_paid_known",
    "invoices_failed_known",
)
_CATEGORICAL = ("plan_id", "billing_frequency")
_THRESHOLDS = (0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80)
_POSITIVE_SUPPORT = (30, 10, 10)


@dataclass(frozen=True, slots=True)
class PartitionSupport:
    """Class and independent episode support without predictor information."""

    partition: str
    positive: int
    negative: int
    positive_episodes: int

    @property
    def prevalence(self) -> float:
        """Return the positive fraction among resolved observations."""
        return (
            self.positive / (self.positive + self.negative)
            if self.positive + self.negative
            else 0.0
        )


@dataclass(frozen=True, slots=True)
class ModelDatasetAcceptance:
    """Required gates and the measured support for each partition."""

    gates: tuple[GateFinding, ...]
    support: tuple[PartitionSupport, ...]

    @property
    def accepted(self) -> bool:
        """Accept only when every mandatory gate passed."""
        return all(gate.status is GateStatus.PASSED for gate in self.gates if gate.required)


@dataclass(frozen=True, slots=True)
class EvaluationMetrics:
    """Per-partition metrics for a fixed model and threshold."""

    precision: float
    recall: float
    f1: float
    average_precision: float
    roc_auc: float
    confusion: tuple[tuple[int, int], tuple[int, int]]
    predicted_positive_rate: float


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    """Validation-only model and threshold selection evidence."""

    model: str
    threshold: float
    metrics: EvaluationMetrics


@dataclass(frozen=True, slots=True)
class BaselineEvaluation:
    """Validation comparisons and one held-out evaluation of the selected candidate."""

    acceptance: ModelDatasetAcceptance
    validation: tuple[CandidateEvaluation, ...]
    selected: CandidateEvaluation
    test: EvaluationMetrics


def _valid_identity(row: ModellingObservation) -> bool:
    if type(row.customer_id) is not str or not row.customer_id.strip():
        return False
    try:
        _read_supplied_uuid(row.subscription_id)
    except EpisodeValidationError:
        return False
    return True


def _predictor_values(row: ModellingObservation) -> dict[str, float | str]:
    if row.features is None or type(row.features.predictors) is not HistoricalFeatures:
        raise ExperimentEvidenceError("Expected typed historical predictors.")
    predictors = row.features.predictors
    values: dict[str, float | str] = {}
    for name in _NUMERIC:
        value = getattr(predictors, name)
        if value is None:
            values[name] = np.nan
            continue
        if type(value) not in (int, float, Decimal, bool) or not isfinite(value):
            raise ExperimentEvidenceError("A numeric historical predictor is invalid.")
        values[name] = float(value)
    for name in _CATEGORICAL:
        value = getattr(predictors, name)
        if type(value) is not str or not value:
            raise ExperimentEvidenceError("A required historical category is missing.")
        values[name] = value
    return values


def _checked_predictors(rows: tuple[ModellingObservation, ...]) -> bool:
    try:
        for row in rows:
            _predictor_values(row)
    except ExperimentEvidenceError:
        return False
    return True


def _support(name: str, rows: tuple[ModellingObservation, ...]) -> PartitionSupport:
    positives = [row for row in rows if row.outcome.binary_target == 1]
    return PartitionSupport(
        name,
        len(positives),
        sum(row.outcome.binary_target == 0 for row in rows),
        len({row.subscription_id.lower() for row in positives}),
    )


def evaluate_model_dataset(
    dataset: ModellingDataset,
    split: ModellingSplit,
    experiment: ChurnExperiment,
    boundaries: SplitBoundaries,
    *,
    reconstructed: ModellingDataset | None,
) -> ModelDatasetAcceptance:
    """Check the authorised experiment's evidence before any model is fitted."""
    labelled = dataset.labelled
    all_rows = (*labelled, *dataset.right_censored, *dataset.pending, *dataset.ineligible)
    partitions = (split.training, split.validation, split.test)
    limits = tuple(
        map(
            utc_instant,
            (
                boundaries.training_end,
                boundaries.validation_end,
                boundaries.test_end,
            ),
        )
    )
    support = tuple(
        _support(name, rows)
        for name, rows in zip(
            ("training", "validation", "test"),
            partitions,
            strict=True,
        )
    )
    episode_sets = [{row.subscription_id.lower() for row in rows} for rows in partitions]
    account_sets = [{row.customer_id for row in rows} for rows in partitions]
    proceeds = [tuple(utc_instant(row.observed_at) for row in rows) for rows in partitions]
    chronological = all(
        all(
            value < limits[index] and (index == 0 or value >= limits[index - 1]) for value in values
        )
        for index, values in enumerate(proceeds)
    )

    def gate(name: str, passed: bool) -> GateFinding:
        return GateFinding(name, GateStatus.PASSED if passed else GateStatus.FAILED)

    def disjoint(values: list[set]) -> bool:
        return sum(map(len, values)) == len(set().union(*values))

    assigned = tuple(row for rows in partitions for row in rows) + tuple(
        exclusion.observation for exclusion in split.excluded
    )
    evidence = {field.name for field in fields(HistoricalFeatures)}
    gates = (
        gate("canonical_identity", all(_valid_identity(row) for row in labelled)),
        gate(
            "explicit_experiment_policy",
            bool(all_rows)
            and all(
                row.policy_id == POLICY_ID
                and row.policy_version == POLICY_VERSION
                and utc_instant(row.horizon_end)
                == utc_instant(row.observed_at) + timedelta(days=experiment.horizon_days)
                for row in all_rows
            ),
        ),
        gate(
            "resolved_target_evidence",
            all(
                (
                    row.outcome.state is OutcomeState.CONFIRMED_POSITIVE
                    and row.outcome.reason == "qualified_effective_termination"
                    or row.outcome.state is OutcomeState.CONFIRMED_NEGATIVE
                    and row.outcome.reason == "complete_horizon_without_termination"
                )
                and bool(row.outcome.source_ref)
                for row in labelled
            ),
        ),
        gate(
            "unresolved_outcomes_preserved",
            all(
                row.outcome.state is expected and row.outcome.binary_target is None
                for expected, rows in (
                    (OutcomeState.RIGHT_CENSORED, dataset.right_censored),
                    (OutcomeState.PENDING_ASCERTAINMENT, dataset.pending),
                    (OutcomeState.INELIGIBLE, dataset.ineligible),
                )
                for row in rows
            ),
        ),
        gate(
            "required_feature_history",
            all(
                row.features is not None
                and row.features.exclusion is None
                and row.features.predictors.episode_age_days is not None
                and row.features.predictors.episode_age_days >= experiment.history_days
                and row.features.predictors.recurring_revenue is not None
                for row in labelled
            ),
        ),
        gate(
            "no_future_feature_evidence",
            all(
                row.features is not None
                and row.features.latest_evidence_at is not None
                and utc_instant(row.features.latest_evidence_at) <= utc_instant(row.observed_at)
                for row in labelled
            ),
        ),
        gate(
            "label_maturity",
            all(
                utc_instant(row.observed_at)
                <= utc_instant(row.ascertainment_cutoff)
                <= utc_instant(experiment.extraction_cutoff)
                and utc_instant(row.horizon_end) <= utc_instant(experiment.extraction_cutoff)
                and max(utc_instant(row.horizon_end), utc_instant(row.ascertainment_cutoff)) < limit
                for rows, limit in zip(partitions, limits, strict=True)
                for row in rows
            ),
        ),
        gate("chronological_ordering", chronological),
        gate("episode_disjointness", disjoint(episode_sets)),
        GateFinding(
            "customer_disjointness",
            (GateStatus.PASSED if disjoint(account_sets) else GateStatus.FAILED)
            if boundaries.customer_disjoint
            else GateStatus.INAPPLICABLE,
            boundaries.customer_disjoint,
        ),
        gate(
            "both_classes_in_each_partition",
            all(row.positive > 0 and row.negative > 0 for row in support),
        ),
        gate(
            "independent_positive_support",
            all(
                row.positive_episodes >= target
                for row, target in zip(support, _POSITIVE_SUPPORT, strict=True)
            ),
        ),
        gate("historical_predictor_allowlist", _checked_predictors(labelled)),
        GateFinding(
            "deterministic_reconstruction",
            GateStatus.NOT_EVALUATED
            if reconstructed is None
            else GateStatus.PASSED
            if reconstructed == dataset
            else GateStatus.FAILED,
        ),
        gate(
            "predictor_target_separation",
            set((*_NUMERIC, *_CATEGORICAL)) <= evidence
            and not evidence
            & {
                "subscription_id",
                "customer_id",
                "outcome",
                "binary_target",
                "observed_at",
                "ascertainment_cutoff",
                "end_date",
            }
            and all(row.features is not None for row in labelled),
        ),
        gate(
            "split_accounting",
            len(assigned) == len(labelled)
            and len({(row.subscription_id.lower(), row.observed_at) for row in all_rows})
            == len(all_rows)
            and set(assigned) == set(labelled),
        ),
    )
    return ModelDatasetAcceptance(gates, support)


def _matrix(rows: tuple[ModellingObservation, ...]) -> tuple[pd.DataFrame, np.ndarray]:
    return (
        pd.DataFrame((_predictor_values(row) for row in rows), columns=(*_NUMERIC, *_CATEGORICAL)),
        np.array([row.outcome.binary_target for row in rows], dtype=int),
    )


def _pipeline(model) -> Pipeline:
    transforms = ColumnTransformer(
        [
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
                        ("scale", StandardScaler()),
                    ]
                ),
                list(_NUMERIC),
            ),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), list(_CATEGORICAL)),
        ]
    )
    return Pipeline([("features", transforms), ("classifier", model)])


def _metrics(y: np.ndarray, scores: np.ndarray, threshold: float) -> EvaluationMetrics:
    predictions = scores >= threshold
    tn, fp, fn, tp = (
        int(value) for value in confusion_matrix(y, predictions, labels=[0, 1]).ravel()
    )
    return EvaluationMetrics(
        float(precision_score(y, predictions, zero_division=0)),
        float(recall_score(y, predictions, zero_division=0)),
        float(f1_score(y, predictions, zero_division=0)),
        float(average_precision_score(y, scores)),
        float(roc_auc_score(y, scores)),
        ((tn, fp), (fn, tp)),
        float(predictions.mean()),
    )


def evaluate_first_churn_baselines(
    dataset: ModellingDataset,
    experiment: ChurnExperiment,
    boundaries: SplitBoundaries,
    *,
    reconstructed: ModellingDataset | None = None,
) -> BaselineEvaluation:
    """Fit on training only and evaluate held-out predictions for one selected model."""
    split = split_modelling_dataset(dataset, boundaries)
    acceptance = evaluate_model_dataset(
        dataset, split, experiment, boundaries, reconstructed=reconstructed
    )
    if not acceptance.accepted:
        failed = ", ".join(
            gate.gate
            for gate in acceptance.gates
            if gate.required and gate.status is not GateStatus.PASSED
        )
        raise ExperimentEvidenceError(f"Training blocked by required gates: {failed}.")
    x_train, y_train = _matrix(split.training)
    x_validation, y_validation = _matrix(split.validation)
    options = (
        ("dummy_prior", DummyClassifier(strategy="prior")),
        ("logistic_unweighted", LogisticRegression(max_iter=1000, random_state=42)),
        (
            "logistic_balanced",
            LogisticRegression(max_iter=1000, random_state=42, class_weight="balanced"),
        ),
    )
    evaluated = []
    for name, classifier in options:
        model = _pipeline(classifier)
        model.fit(x_train, y_train)
        scores = model.predict_proba(x_validation)[:, 1]
        threshold = max(
            _THRESHOLDS,
            key=lambda value: (
                f1_score(y_validation, scores >= value, zero_division=0),
                value,
            ),
        )
        evaluated.append(
            (CandidateEvaluation(name, threshold, _metrics(y_validation, scores, threshold)), model)
        )

    selected, model = max(evaluated, key=lambda row: row[0].metrics.average_precision)

    # Held-out scoring starts only after the model and threshold are fixed.
    x_test, y_test = _matrix(split.test)
    return BaselineEvaluation(
        acceptance,
        tuple(row for row, _ in evaluated),
        selected,
        _metrics(y_test, model.predict_proba(x_test)[:, 1], selected.threshold),
    )
