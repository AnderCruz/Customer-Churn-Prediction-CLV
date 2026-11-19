"""Verify temporal maturity and group assignment without model training."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    ExperimentEvidenceError,
    OutcomeClassification,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import OutcomeState
from nowa_customer_intelligence.data.synthetic.historical_features import (
    HistoricalFeatureResult,
    HistoricalFeatures,
)
from nowa_customer_intelligence.data.synthetic.modelling_dataset import (
    ModellingDataset,
    ModellingObservation,
    SplitBoundaries,
    split_modelling_dataset,
)

_FIRST = "aaaaaaaa-1234-4234-8234-123456789abc"
_SECOND = "bbbbbbbb-1234-4234-8234-123456789abc"
_THIRD = "cccccccc-1234-4234-8234-123456789abc"
_T = datetime(2024, 1, 1, tzinfo=UTC)
_LIMITS = SplitBoundaries(_T + timedelta(days=30), _T + timedelta(days=60), _T + timedelta(days=90))
_FEATURES = HistoricalFeatures(
    100,
    "launch",
    "monthly",
    Decimal("79.00"),
    None,
    None,
    None,
    None,
    None,
    0,
    2,
    False,
    0,
    0,
    0,
    None,
)


def _row(identifier: str, offset: int, *, customer: str = "group-1") -> ModellingObservation:
    t = _T + timedelta(days=offset)
    return ModellingObservation(
        identifier,
        customer,
        t,
        t + timedelta(days=5),
        t + timedelta(days=5),
        HistoricalFeatureResult(_FEATURES, t, (), None),
        OutcomeClassification(OutcomeState.CONFIRMED_NEGATIVE, "fixture"),
    )


def _dataset(*rows: ModellingObservation) -> ModellingDataset:
    return ModellingDataset(rows, (), (), ())


def test_episode_and_customer_disjoint_modes_are_distinct() -> None:
    initial = _row(_FIRST, 1)
    repeated = _row(_FIRST, 31)
    new_episode = _row(_SECOND, 32)
    test = _row(_THIRD, 64, customer="group-2")
    dataset = _dataset(test, repeated, initial, new_episode)
    result = split_modelling_dataset(dataset, _LIMITS)
    assert (result.training, result.validation, result.test) == (
        (initial,),
        (new_episode,),
        (test,),
    )
    assert result.excluded[0].observation == repeated
    assert result.excluded[0].reason == "group_assigned_to_earlier_partition"
    grouped = split_modelling_dataset(dataset, replace(_LIMITS, customer_disjoint=True))
    assert grouped.training == (initial,) and grouped.validation == () and grouped.test == (test,)
    assert len(grouped.excluded) == 2


def test_horizon_and_ascertainment_have_independent_maturity_gates() -> None:
    crossing = _row(_FIRST, 26)
    late = replace(_row(_SECOND, 1), ascertainment_cutoff=_LIMITS.training_end)
    finally_outside = _row(_THIRD, 100)
    result = split_modelling_dataset(_dataset(crossing, late, finally_outside), _LIMITS)
    assert [row.reason for row in result.excluded] == [
        "ascertainment_crosses_boundary",
        "outcome_horizon_crosses_boundary",
        "outside_split_window",
    ]
    assert result.training == result.validation == result.test == ()


def test_split_rejects_unresolved_targets_and_future_feature_evidence() -> None:
    original = _row(_FIRST, 1)
    unresolved = replace(
        original, outcome=OutcomeClassification(OutcomeState.RIGHT_CENSORED, "fixture")
    )
    with pytest.raises(ExperimentEvidenceError, match="ineligible"):
        split_modelling_dataset(_dataset(unresolved), _LIMITS)
    invalid = replace(
        original,
        features=replace(
            original.features, latest_evidence_at=original.observed_at + timedelta(days=1)
        ),
    )
    with pytest.raises(ExperimentEvidenceError, match="future or missing"):
        split_modelling_dataset(_dataset(invalid), _LIMITS)
    with pytest.raises(ExperimentEvidenceError, match="chronological"):
        replace(_LIMITS, validation_end=_LIMITS.training_end)
