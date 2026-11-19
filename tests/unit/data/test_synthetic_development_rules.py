"""Exercise the bounded billing, observation and lifecycle rules."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    BillingValidationError,
    InvoiceStatus,
    PlanChange,
    billing_anniversary,
    schedule_episode_billing,
)
from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord
from nowa_customer_intelligence.data.synthetic.episodes import (
    EpisodeStatus,
    EpisodeValidationError,
    SubscriptionEpisode,
)
from nowa_customer_intelligence.data.synthetic.identity_registry import (
    EpisodeIdentity,
    EpisodeIdentityRegistry,
)
from nowa_customer_intelligence.data.synthetic.lifecycle import (
    GeneratedEpisode,
    LifecycleFact,
    LifecycleKind,
    generate_episodes,
    validate_lifecycle,
)
from nowa_customer_intelligence.data.synthetic.observations import (
    ObservationError,
    UsageAssumptions,
    generate_episode_observations,
)
from nowa_customer_intelligence.data.synthetic.random_streams import create_random_stream

_ID = "aaaaaaaa-1234-4234-8234-123456789abc"
_START = date(2024, 1, 31)
_END = date(2024, 4, 1)
_EPISODE = SubscriptionEpisode(_ID, "customer-1", _START, EpisodeStatus.EXPIRED, end_date=_END)


def test_short_months_preserve_original_anchor_and_annual_amounts() -> None:
    assert billing_anniversary(_START, 1, BillingFrequency.MONTHLY) == date(2024, 2, 29)
    assert billing_anniversary(_START, 2, BillingFrequency.MONTHLY) == date(2024, 3, 31)
    leap = date(2024, 2, 29)
    assert billing_anniversary(leap, 1, BillingFrequency.ANNUAL) == date(2025, 2, 28)
    assert billing_anniversary(leap, 4, BillingFrequency.ANNUAL) == date(2028, 2, 29)
    annual = schedule_episode_billing(
        replace(_EPISODE, end_date=None, subscription_status=EpisodeStatus.ACTIVE),
        paid_activation=_START,
        cutoff=date(2025, 2, 1),
        plan_id="launch",
        frequency=BillingFrequency.ANNUAL,
        subsequent_payment=InvoiceStatus.PENDING,
    )
    assert [row.invoice.amount for row in annual] == [Decimal("853.20")] * 2
    assert [row.recurring_revenue for row in annual] == [Decimal("71.10")] * 2


def test_plan_changes_at_next_boundary_and_failed_payment_is_explicit() -> None:
    schedule = schedule_episode_billing(
        _EPISODE,
        paid_activation=_START,
        cutoff=_END,
        plan_id="launch",
        frequency=BillingFrequency.MONTHLY,
        subsequent_payment=InvoiceStatus.FAILED,
        plan_changes=(PlanChange(date(2024, 2, 29), "growth"),),
    )
    assert [row.invoice.amount for row in schedule] == [
        Decimal("79.00"),
        Decimal("79.00"),
        Decimal("249.00"),
    ]
    assert [row.invoice.invoice_status for row in schedule] == [
        InvoiceStatus.PAID,
        InvoiceStatus.FAILED,
        InvoiceStatus.FAILED,
    ]
    assert all(row.payment_event.invoice_id == row.invoice.invoice_id for row in schedule)
    assert schedule[-1].period_end == _END
    assert _EPISODE.end_date == _END
    assert schedule[-1].invoice.paid_date is None


@pytest.mark.parametrize(
    "changes",
    [
        {"paid_activation": _END},
        {"subsequent_payment": InvoiceStatus.REFUNDED},
        {"plan_changes": (PlanChange(_END, "growth"),)},
        {"plan_changes": (PlanChange(_START, "growth"), PlanChange(_START, "scale"))},
    ],
)
def test_billing_rejects_unsupported_facts(changes: dict[str, object]) -> None:
    arguments = {
        "paid_activation": _START,
        "cutoff": _END,
        "plan_id": "launch",
        "frequency": BillingFrequency.MONTHLY,
        "subsequent_payment": InvoiceStatus.PENDING,
    }
    with pytest.raises(BillingValidationError):
        schedule_episode_billing(_EPISODE, **(arguments | changes))


def test_completed_months_and_late_evidence_are_as_known() -> None:
    charges = schedule_episode_billing(
        _EPISODE,
        paid_activation=_START,
        cutoff=_END,
        plan_id="launch",
        frequency=BillingFrequency.MONTHLY,
        subsequent_payment=InvoiceStatus.PENDING,
        plan_changes=(PlanChange(date(2024, 2, 1), "growth"),),
    )
    late = datetime(2024, 2, 5, tzinfo=UTC)
    usage, snapshots = generate_episode_observations(
        _EPISODE,
        charges,
        late,
        observation_cutoff=datetime(2024, 3, 31, 23, tzinfo=UTC),
        assumptions=UsageAssumptions(2, 2, 10, 10),
        stream=create_random_stream(1, "usage"),
    )
    assert [row.snapshot_date for row in snapshots] == [date(2024, 2, 29)]
    assert snapshots[0].recurring_revenue == Decimal("249.00")
    assert [row.usage_month for row in usage] == [date(2024, 2, 1)]
    assert usage[0].active_users <= usage[0].total_users == 2
    assert usage[0].available_at == datetime(2024, 3, 1, tzinfo=UTC)
    with pytest.raises(ObservationError, match="next day"):
        UsageAssumptions(0, 1, 1, 1, reporting_lag_days=0)


def test_explicit_reactivation_preserves_history_and_rejects_overlap(tmp_path: Path) -> None:
    raw = b"""
config_schema_version: 1
base:
  population: {customer_count: 1, episode_count_min: 1, episode_count_max: 3}
  history: {start_date: '2024-01-01', cutoff_date: '2024-04-01'}
  master_seed: 42
  workflow: BASIC
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios: {baseline: {scenario_version: 1}}
"""
    effective = resolve_configuration(load_configuration(raw), "baseline")
    customer = CustomerRecord("customer-1", _START, "GB")
    registry = EpisodeIdentityRegistry(tmp_path / "registry.sqlite")
    with pytest.raises(EpisodeValidationError, match="History cannot"):
        generate_episodes(
            effective,
            (customer,),
            registry,
            client="fixture",
            namespace="test",
            target=3,
        )
    rows = generate_episodes(
        effective,
        (customer,),
        registry,
        client="fixture",
        namespace="test",
        target=2,
    )
    validate_lifecycle(rows, cutoff=_END)
    first, successor = sorted(rows, key=lambda row: row.episode.start_date)
    assert first.episode.end_date < successor.episode.start_date
    assert successor.prior_subscription_id == first.episode.subscription_id
    assert successor.facts[2].kind is LifecycleKind.REACTIVATED
    contradicts = replace(first, episode=replace(first.episode, end_date=None))
    with pytest.raises(EpisodeValidationError, match="transition"):
        validate_lifecycle((contradicts, successor), cutoff=_END)
    with pytest.raises(EpisodeValidationError, match="lineage"):
        validate_lifecycle((first, replace(successor, prior_subscription_id=_ID)), cutoff=_END)


def test_billing_anniversary_rejects_invalid_input() -> None:
    with pytest.raises(BillingValidationError, match="non-negative"):
        billing_anniversary(_START, -1, BillingFrequency.MONTHLY)
    with pytest.raises(BillingValidationError, match="frequency"):
        billing_anniversary(_START, 0, "annual")
    with pytest.raises(BillingValidationError, match="date range"):
        billing_anniversary(date.max, 1, BillingFrequency.ANNUAL)


def test_rejects_within_day_lifecycle_reversal_and_naive_evidence() -> None:
    day = datetime(2024, 1, 31, tzinfo=UTC)
    episode = replace(_EPISODE, end_date=None, subscription_status=EpisodeStatus.ACTIVE)
    identity = EpisodeIdentity("client", "fixture", "source-key", "established-key")
    established = LifecycleFact(_ID, LifecycleKind.ESTABLISHED, day, day.replace(hour=12), day)
    activated = LifecycleFact(_ID, LifecycleKind.ACTIVATED, day, day, day)
    with pytest.raises(EpisodeValidationError, match="out of order"):
        validate_lifecycle(
            (GeneratedEpisode(identity, episode, _START, (established, activated)),),
            cutoff=_END,
        )
    with pytest.raises(EpisodeValidationError, match="timezone-aware"):
        replace(activated, available_at=day.replace(tzinfo=None))


def test_termination_must_strictly_follow_activation() -> None:
    instant = datetime(2024, 1, 31, tzinfo=UTC)
    episode = replace(_EPISODE, end_date=_START)
    identity = EpisodeIdentity("client", "fixture", "source-key", "established-key")
    facts = tuple(
        LifecycleFact(_ID, kind, instant, instant, instant)
        for kind in (LifecycleKind.ESTABLISHED, LifecycleKind.ACTIVATED, LifecycleKind.TERMINATED)
    )
    with pytest.raises(EpisodeValidationError, match="contradict episode dates"):
        validate_lifecycle((GeneratedEpisode(identity, episode, _START, facts),), cutoff=_END)
