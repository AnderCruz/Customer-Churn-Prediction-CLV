"""Verify synthetic-only classification against explicit evidence boundaries."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    ChurnExperiment,
    ExperimentEvidenceError,
    ExperimentObservation,
    FollowUpEvidence,
    IneligibilityReason,
    TerminationEvidence,
    classify_outcome,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import OutcomeState
from nowa_customer_intelligence.data.synthetic.modelling_dataset import SimulationFollowUp

_ID = "aaaaaaaa-1234-4234-8234-123456789abc"
_T = datetime(2024, 2, 1, tzinfo=UTC)
_H = _T + timedelta(days=30)
_A = _H + timedelta(days=5)
_EXPERIMENT = ChurnExperiment(_A)
_WINDOW = ExperimentObservation(_T, _A)


def _event(at: datetime) -> TerminationEvidence:
    return TerminationEvidence(_ID, "termination-fact", at, at, at, at, True)


def _classify(**kwargs):
    return classify_outcome(_ID, _WINDOW, _EXPERIMENT, **kwargs)


@pytest.mark.parametrize(
    ("offset", "state", "label"),
    [
        (0, OutcomeState.INELIGIBLE, None),
        (1, OutcomeState.CONFIRMED_POSITIVE, 1),
        (30, OutcomeState.CONFIRMED_POSITIVE, 1),
        (31, OutcomeState.CONFIRMED_NEGATIVE, 0),
    ],
)
def test_target_excludes_t_and_includes_horizon_endpoint(
    offset: int, state: OutcomeState, label: int | None
) -> None:
    actual = _classify(
        terminations=(_event(_T + timedelta(days=offset)),),
        follow_up=FollowUpEvidence(_ID, "complete", _H, _A),
    )
    assert (actual.state, actual.binary_target) == (state, label)


def test_missing_followup_and_unresolved_candidates_never_become_negatives() -> None:
    assert _classify().state is OutcomeState.PENDING_ASCERTAINMENT
    fact = _event(_H)
    late = replace(fact, available_at=_A + timedelta(days=1), resolved_at=_A + timedelta(days=1))
    full = FollowUpEvidence(_ID, "complete", _H, _A)
    for candidate in (late, replace(fact, confirmed=False, resolved_at=None)):
        outcome = _classify(terminations=(candidate,), follow_up=full)
        assert outcome.state is OutcomeState.PENDING_ASCERTAINMENT
        assert outcome.binary_target is None
    assert _classify(follow_up=replace(full, available_at=_A + timedelta(days=1))).reason == (
        "missing_ascertained_follow_up"
    )
    disproved = replace(fact, confirmed=False)
    assert _classify(terminations=(disproved,), follow_up=full).binary_target == 0


def test_censoring_requires_explicit_complete_followup_before_horizon() -> None:
    partial = FollowUpEvidence(_ID, "complete-short-followup", _H - timedelta(days=1), _A)
    state = _classify(follow_up=partial)
    assert state.state is OutcomeState.RIGHT_CENSORED and state.binary_target is None
    assert state.source_ref == partial.source_ref
    excluded = _classify(exclusion=IneligibilityReason.EXPLICIT_EXCLUSION, follow_up=partial)
    assert excluded.state is OutcomeState.INELIGIBLE and excluded.binary_target is None


def test_invalid_identity_or_conflicting_evidence_never_creates_a_label() -> None:
    assert classify_outcome("bad-id", _WINDOW, _EXPERIMENT).reason is (
        IneligibilityReason.INVALID_IDENTITY
    )
    event = _event(_H)
    with pytest.raises(ExperimentEvidenceError, match="different episode"):
        _classify(terminations=(replace(event, subscription_id="wrong-episode"),))
    with pytest.raises(ExperimentEvidenceError, match="contradictory"):
        _classify(terminations=(event, event))
    with pytest.raises(ExperimentEvidenceError, match="adjudication"):
        replace(event, resolved_at=_T)
    with pytest.raises(ExperimentEvidenceError, match="before it was complete"):
        FollowUpEvidence(_ID, "early", _H, _T)
    with pytest.raises(ExperimentEvidenceError, match="supported observation interval"):
        _classify(
            follow_up=FollowUpEvidence(
                _ID, "future", _A + timedelta(days=1), _A + timedelta(days=1)
            )
        )


def test_cutoffs_and_simulation_recording_lag_are_explicit() -> None:
    with pytest.raises(ExperimentEvidenceError, match="extraction"):
        ExperimentObservation(_T, _A + timedelta(days=1)).bounds(_EXPERIMENT)
    with pytest.raises(ExperimentEvidenceError, match="precedes"):
        ExperimentObservation(_T, _T - timedelta(days=1))
    with pytest.raises(ExperimentEvidenceError, match="timezone-aware"):
        ChurnExperiment(_A.replace(tzinfo=None))
    with pytest.raises(ExperimentEvidenceError, match="whole-day"):
        ChurnExperiment(_A, history_days=0)
    ledger = SimulationFollowUp("closed-fixture-ledger", _A, recording_lag_days=2)
    explicit = ledger.evidence_for(_ID, ExperimentObservation(_T, _H), _EXPERIMENT)
    assert explicit.complete_through == _H - timedelta(days=2)
    assert explicit.available_at == _H
    assert ledger.evidence_for(_ID, ExperimentObservation(_T, _T), _EXPERIMENT) is None
