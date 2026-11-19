"""Verify synthetic evidence rules and isolated one-defect negative fixtures."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.synthetic.billing import InvoiceFact, InvoiceStatus
from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord
from nowa_customer_intelligence.data.synthetic.episodes import (
    EpisodeEvent,
    EpisodeEventType,
    EpisodeStatus,
    EpisodeValidationError,
    SubscriptionEpisode,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import (
    OutcomeEvidence,
    OutcomeEvidenceError,
    OutcomeRecord,
    OutcomeState,
)
from nowa_customer_intelligence.data.synthetic.observations import (
    ObservationError,
    SnapshotRecord,
    UsageRecord,
)
from nowa_customer_intelligence.data.synthetic.semantic_validation import (
    ReactivationEvidence,
    ValidationStatus,
    validate_synthetic_evidence,
)

_ID = "aaaaaaaa-1234-4234-8234-123456789abc"
_NEXT = "bbbbbbbb-1234-4234-8234-123456789abc"
_UNKNOWN = "cccccccc-1234-4234-8234-123456789abc"
_JAN = date(2024, 1, 1)
_FEB = date(2024, 2, 1)
_CUTOFF = date(2024, 4, 1)
_EST = datetime(2024, 1, 1, tzinfo=UTC)
_TERM = datetime(2024, 1, 20, tzinfo=UTC)
_OBS = datetime(2024, 3, 1, tzinfo=UTC)
_A = _OBS + timedelta(days=4)
_CUSTOMERS = (CustomerRecord("owner-1", _JAN, "GB"), CustomerRecord("owner-2", _JAN, "GB"))
_EVENT = EpisodeEvent("established-1", EpisodeEventType.ESTABLISHED, _EST)
_EPISODE = SubscriptionEpisode(_ID, "owner-1", _JAN, EpisodeStatus.ACTIVE, establishment=_EVENT)
_SUCCESSOR = SubscriptionEpisode(_NEXT, "owner-1", _FEB, EpisodeStatus.ACTIVE)
_USAGE = UsageRecord(_ID, _FEB, _FEB, date(2024, 2, 29), available_at=_OBS)
_SNAPSHOT = SnapshotRecord(_ID, _OBS.date(), EpisodeStatus.ACTIVE, _OBS, _OBS, _OBS, _OBS)
_INVOICE = InvoiceFact("invoice-1", _ID, _FEB, Decimal("79.00"), InvoiceStatus.PENDING)
_OUTCOME = OutcomeRecord(
    _ID,
    _OBS,
    _A,
    OutcomeState.CONFIRMED_POSITIVE,
    (OutcomeEvidence("source-1", _A, effective_at=_OBS + timedelta(days=3)),),
)
_LINK = ReactivationEvidence(_ID, _NEXT, _TERM, datetime(2024, 2, 1, tzinfo=UTC))


def _inputs() -> dict[str, object]:
    return {
        "customers": _CUSTOMERS,
        "episodes": (_EPISODE, _SUCCESSOR),
        "cutoff": _CUTOFF,
        "observation_at": _OBS,
        "usage": (_USAGE,),
        "snapshots": (_SNAPSHOT,),
        "invoices": (_INVOICE,),
        "outcomes": (_OUTCOME,),
        "episode_owners": {_ID: "owner-1", _NEXT: "owner-1"},
        "event_owners": {_EVENT.event_id: _ID},
        "invoice_owners": {_INVOICE.invoice_id: _ID},
        "reactivations": (_LINK,),
    }


def _findings(**changes):
    return {row.rule: row for row in validate_synthetic_evidence(**(_inputs() | changes))}


def test_supported_evidence_passes_without_claiming_blocked_policy() -> None:
    results = _findings()
    assert {row.status for row in results.values()} == {
        ValidationStatus.PASSED,
        ValidationStatus.BLOCKED_BY_UNRESOLVED_POLICY,
    }
    assert results["target_and_eligibility"].decisions
    with pytest.raises(FrozenInstanceError):
        results["target_and_eligibility"].status = ValidationStatus.PASSED


@pytest.mark.parametrize(
    ("changes", "rule", "reason"),
    [
        (
            {"episodes": (_EPISODE, replace(_EPISODE, subscription_id=_ID.upper()))},
            "episode_population",
            "invalid_episode_ownership_or_identity",
        ),
        (
            {"episodes": (replace(_EPISODE, customer_id="absent"), _SUCCESSOR)},
            "episode_population",
            "invalid_episode_ownership_or_identity",
        ),
        (
            {"usage": (replace(_USAGE, subscription_id=_UNKNOWN),)},
            "usage_facts",
            "invalid_supplied_facts",
        ),
        ({"usage": (_USAGE, _USAGE)}, "usage_facts", "invalid_supplied_facts"),
        ({"snapshots": (_SNAPSHOT, _SNAPSHOT)}, "snapshot_facts", "invalid_supplied_facts"),
        (
            {"episode_owners": {_ID: "owner-2", _NEXT: "owner-1"}},
            "customer_episode_attribution",
            "contradictory_source_attribution",
        ),
        (
            {"event_owners": {_EVENT.event_id: _NEXT}},
            "event_attribution",
            "contradictory_source_attribution",
        ),
        (
            {"invoice_owners": {_INVOICE.invoice_id: _NEXT}},
            "invoice_attribution",
            "contradictory_source_attribution",
        ),
        (
            {"observation_at": _OBS - timedelta(seconds=1)},
            "feature_availability",
            "future_feature_evidence",
        ),
        (
            {"observation_at": _OBS.replace(tzinfo=None)},
            "feature_availability",
            "invalid_observation_cutoff",
        ),
        ({"cutoff": _OBS.date()}, "outcome_extraction_cutoff", "outcome_exceeds_extraction_cutoff"),
        (
            {"outcomes": (replace(_OUTCOME, subscription_id=_UNKNOWN),)},
            "outcome_facts",
            "invalid_supplied_facts",
        ),
        (
            {"reactivations": (replace(_LINK, next_subscription_id=_ID),)},
            "historical_episode_separation",
            "contradictory_episode_lineage",
        ),
        (
            {"reactivations": (replace(_LINK, terminated_at=_LINK.established_at),)},
            "historical_episode_separation",
            "contradictory_episode_chronology",
        ),
        (
            {"reactivations": ("private-sentinel",)},
            "historical_episode_separation",
            "invalid_lineage_evidence",
        ),
    ],
)
def test_isolated_negative_population_fixtures(
    changes: dict, rule: str, reason: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    valid = _inputs()
    before = validate_synthetic_evidence(**valid)
    negative = valid | changes
    before_negative = repr(negative)
    failed = {row.rule: row for row in validate_synthetic_evidence(**negative)}
    assert failed[rule].status is ValidationStatus.FAILED
    assert failed[rule].reason == reason
    assert "private-sentinel" not in repr(failed[rule])
    assert repr(negative) == before_negative
    assert validate_synthetic_evidence(**valid) == before
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    ("constructor", "error", "category"),
    [
        (
            lambda: replace(_SNAPSHOT, available_at=_OBS + timedelta(seconds=1)),
            ObservationError,
            "extends beyond",
        ),
        (lambda: replace(_OUTCOME, evidence=()), OutcomeEvidenceError, "post-observation evidence"),
        (lambda: replace(_EVENT, event_type="suspended"), EpisodeValidationError, "outside"),
    ],
)
def test_isolated_negative_record_construction(
    constructor: Callable[[], object], error: type[Exception], category: str
) -> None:
    before = repr((_SNAPSHOT, _OUTCOME, _EVENT))
    with pytest.raises(error, match=category):
        constructor()
    assert repr((_SNAPSHOT, _OUTCOME, _EVENT)) == before
    assert _findings()["feature_availability"].status is ValidationStatus.PASSED


def test_incomplete_records_never_pass_the_unavailable_checks() -> None:
    result = _findings(
        observation_at=None,
        snapshots=None,
        reactivations=(),
        event_owners=None,
        invoice_owners=None,
        outcomes=None,
    )
    for rule in (
        "feature_availability",
        "snapshot_facts",
        "historical_episode_separation",
        "event_attribution",
        "invoice_attribution",
        "outcome_extraction_cutoff",
    ):
        assert result[rule].status is ValidationStatus.NOT_EVALUATED
    missing_availability = _findings(usage=(replace(_USAGE, available_at=None),))
    assert missing_availability["feature_availability"].status is ValidationStatus.NOT_EVALUATED
    assert missing_availability["usage_facts"].status is ValidationStatus.PASSED


def test_partial_and_unknown_event_bindings_are_distinct() -> None:
    partial = _findings(episode_owners={_ID: "owner-1"})
    assert partial["customer_episode_attribution"].status is ValidationStatus.NOT_EVALUATED
    no_events = (replace(_EPISODE, establishment=None), _SUCCESSOR)
    assert _findings(episodes=no_events)["event_attribution"].reason == "unknown_source_fact"
    assert _findings(episodes=no_events)["establishment_chronology"].status is (
        ValidationStatus.NOT_EVALUATED
    )


def test_establishment_beyond_extraction_cutoff_is_rejected() -> None:
    event = replace(_EVENT, recorded_at=datetime(2024, 4, 2, tzinfo=UTC))
    finding = _findings(episodes=(replace(_EPISODE, establishment=event), _SUCCESSOR))
    assert finding["establishment_chronology"].reason == "event_exceeds_extraction_cutoff"
    assert finding["establishment_chronology"].status is ValidationStatus.FAILED


def test_same_day_cyclic_lineage_fails_even_with_coherent_individual_links() -> None:
    same_day = (replace(_EPISODE, establishment=None), replace(_SUCCESSOR, start_date=_JAN))
    links = (
        ReactivationEvidence(_ID, _NEXT, _EST, _EST + timedelta(hours=1)),
        ReactivationEvidence(_NEXT, _ID, _EST, _EST + timedelta(hours=1)),
    )
    assert (
        _findings(episodes=same_day, reactivations=links)["historical_episode_separation"].reason
        == "cyclic_episode_lineage"
    )


def test_inclusive_usage_period_must_finish_before_feature_observation() -> None:
    unfinished = replace(_USAGE, period_end=_OBS.date())
    assert (
        _findings(usage=(unfinished,))["feature_availability"].reason == "future_feature_evidence"
    )


def test_empty_input_and_invalid_extraction_context() -> None:
    findings = validate_synthetic_evidence([], [], cutoff=_CUTOFF, observation_at=_OBS)
    assert all(row.status is not ValidationStatus.PASSED for row in findings)
    with pytest.raises(ValueError, match="extraction"):
        validate_synthetic_evidence([], [], cutoff=None)
