"""Exercise evidence structure without implementing outcome policy."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode
from nowa_customer_intelligence.data.synthetic.ground_truth import (
    OutcomeEvidence,
    OutcomeEvidenceError,
    OutcomeRecord,
    OutcomeState,
    validate_outcomes,
)

_ID = "aaaaaaaa-1234-4234-8234-123456789abc"
_T = datetime(2024, 3, 1, tzinfo=UTC)
_A = _T + timedelta(days=3)
_FACT = OutcomeEvidence("fixture-source", _A, effective_at=_T + timedelta(days=1))
_EPISODE = SubscriptionEpisode(_ID, "customer-1", date(2024, 1, 1), EpisodeStatus.ACTIVE)


@pytest.mark.parametrize("state", list(OutcomeState))
def test_preserves_all_supplied_states_without_certification(state: OutcomeState) -> None:
    record = OutcomeRecord(_ID, _T, _A, state, (_FACT,), _A)
    assert validate_outcomes([record], [_EPISODE]) == (record,)
    assert record.state is state and not record.semantically_certified
    assert not hasattr(record, "label")
    with pytest.raises(FrozenInstanceError):
        record.state = OutcomeState.INELIGIBLE


@pytest.mark.parametrize(
    "changes",
    [
        {"subscription_id": ""},
        {"state": "positive"},
        {"observation_at": _T.replace(tzinfo=None)},
        {"ascertainment_cutoff": _T - timedelta(days=1)},
        {"follow_up_through": _A + timedelta(days=1)},
        {"evidence": [_FACT]},
        {"evidence": (_FACT, _FACT)},
        {"evidence": ()},
        {"evidence": (replace(_FACT, available_at=_A + timedelta(seconds=1)),)},
        {"evidence": (replace(_FACT, effective_at=None),)},
    ],
)
def test_rejects_invalid_positive_evidence(changes: dict[str, object]) -> None:
    valid = OutcomeRecord(_ID, _T, _A, OutcomeState.CONFIRMED_POSITIVE, (_FACT,))
    with pytest.raises(OutcomeEvidenceError):
        replace(valid, **changes)


@pytest.mark.parametrize("state", [OutcomeState.CONFIRMED_NEGATIVE, OutcomeState.RIGHT_CENSORED])
def test_supplied_follow_up_states_need_evidence_and_endpoint(state: OutcomeState) -> None:
    with pytest.raises(OutcomeEvidenceError, match="follow-up"):
        OutcomeRecord(_ID, _T, _A, state, (_FACT,))


def test_rejects_empty_fact_refs_and_naive_evidence_times() -> None:
    with pytest.raises(OutcomeEvidenceError, match="source fact"):
        OutcomeEvidence("", _A)
    with pytest.raises(OutcomeEvidenceError, match="timezone-aware"):
        OutcomeEvidence("fixture", _A, occurred_at=_T.replace(tzinfo=None))


def test_outcomes_order_and_duplicate_instants() -> None:
    first = OutcomeRecord(_ID, _T, _A, OutcomeState.PENDING_ASCERTAINMENT)
    second = replace(first, observation_at=_T + timedelta(days=1))
    assert validate_outcomes([second, first], [_EPISODE]) == (first, second)
    equivalent = replace(first, observation_at=_T.astimezone(timezone(timedelta(hours=2))))
    with pytest.raises(OutcomeEvidenceError, match="Duplicate"):
        validate_outcomes([first, equivalent], [_EPISODE])
    with pytest.raises(OutcomeEvidenceError, match="Unknown"):
        validate_outcomes([first], [])
    with pytest.raises(OutcomeEvidenceError, match="unique typed"):
        validate_outcomes([first], [_EPISODE, _EPISODE])
    with pytest.raises(OutcomeEvidenceError, match="typed outcome"):
        validate_outcomes(["fixture"], [_EPISODE])
    with pytest.raises(OutcomeEvidenceError, match="precedes"):
        validate_outcomes([first], [replace(_EPISODE, start_date=date(2024, 3, 2))])
