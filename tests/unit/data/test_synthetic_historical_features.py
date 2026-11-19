"""Verify historical predictors and isolation from future and target evidence."""

from dataclasses import fields, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

import pytest

from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    InvoiceStatus,
    schedule_episode_billing,
)
from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    ChurnExperiment,
    ExperimentEvidenceError,
    ExperimentObservation,
    IneligibilityReason,
)
from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode
from nowa_customer_intelligence.data.synthetic.historical_features import (
    HistoricalFeatures,
    HistoricalPlanCorrection,
    build_historical_features,
)
from nowa_customer_intelligence.data.synthetic.lifecycle import LifecycleFact, LifecycleKind
from nowa_customer_intelligence.data.synthetic.observations import SnapshotRecord, UsageRecord

_ID = "aaaaaaaa-1234-4234-8234-123456789abc"
_DAY = date(2024, 1, 1)
_ACTIVATION = datetime.combine(_DAY, time.min, UTC)
_T = datetime(2024, 5, 1, tzinfo=UTC)
_E = datetime(2024, 8, 1, tzinfo=UTC)
_EXPERIMENT = ChurnExperiment(_E)
_FACT = LifecycleFact(_ID, LifecycleKind.ACTIVATED, _ACTIVATION, _ACTIVATION, _ACTIVATION)
_EPISODE = SubscriptionEpisode(_ID, "account", _DAY, EpisodeStatus.ACTIVE)
_SNAP_TIME = datetime(2024, 4, 30, 23, tzinfo=UTC)
_SNAPSHOT = SnapshotRecord(
    _ID,
    _SNAP_TIME.date(),
    EpisodeStatus.ACTIVE,
    _SNAP_TIME,
    _SNAP_TIME,
    _SNAP_TIME,
    _SNAP_TIME,
    "launch",
    BillingFrequency.MONTHLY,
    Decimal("79.00"),
    "GBP",
)
_BILLING = schedule_episode_billing(
    _EPISODE,
    paid_activation=_DAY,
    cutoff=date(2024, 6, 30),
    plan_id="launch",
    frequency=BillingFrequency.MONTHLY,
    subsequent_payment=InvoiceStatus.FAILED,
)
_USAGE = (
    UsageRecord(
        _ID,
        date(2024, 3, 1),
        date(2024, 3, 1),
        date(2024, 3, 31),
        active_users=2,
        sessions_count=6,
        events_count=10,
        usage_volume=Decimal("1.25"),
        available_at=datetime(2024, 4, 1, tzinfo=UTC),
    ),
    UsageRecord(
        _ID,
        date(2024, 4, 1),
        date(2024, 4, 1),
        date(2024, 4, 30),
        active_users=4,
        sessions_count=8,
        events_count=12,
        usage_volume=Decimal("2.25"),
        available_at=_T,
    ),
)


def _features(t: datetime = _T, **changes):
    values = {
        "history_start": _DAY,
        "lifecycle": (_FACT,),
        "snapshots": (_SNAPSHOT,),
        "usage": _USAGE,
        "billing": _BILLING,
    }
    return build_historical_features(
        _ID, ExperimentObservation(t, t + timedelta(days=30)), _EXPERIMENT, **(values | changes)
    )


def test_uses_historical_features_and_keeps_metadata_out_of_predictors() -> None:
    result = _features()
    predictors = result.predictors
    assert result.exclusion is None and result.latest_evidence_at == _T
    assert predictors.plan_id == "launch" and predictors.recurring_revenue == Decimal("79.00")
    assert predictors.active_users_mean == 3 and predictors.recent_active_users_change == 2
    assert predictors.sessions_total == 14 and predictors.events_total == 22
    assert predictors.usage_volume_total == Decimal("3.50")
    assert not predictors.usage_coverage_complete
    assert (predictors.observed_usage_months, predictors.expected_usage_months) == (2, 3)
    assert predictors.invoices_issued == predictors.invoices_failed_known == 4
    assert predictors.invoices_overdue_known is None
    assert "overdue_history_unavailable" in result.unavailable
    names = {field.name for field in fields(HistoricalFeatures)}
    assert not names & {
        "subscription_id",
        "customer_id",
        "outcome",
        "binary_target",
        "end_date",
        "ascertainment_cutoff",
        "policy_id",
        "source_ref",
    }


def test_future_termination_usage_invoices_and_corrections_do_not_change_predictors() -> None:
    later = _T + timedelta(days=2)
    termination = LifecycleFact(_ID, LifecycleKind.TERMINATED, later, later, later)
    correction = HistoricalPlanCorrection(
        _ID,
        "growth",
        BillingFrequency.MONTHLY,
        Decimal("249.00"),
        _T,
        _T,
        later,
    )
    late_usage = replace(
        _USAGE[-1],
        usage_month=date(2024, 5, 1),
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 31),
        active_users=999,
        available_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    future_snapshot = replace(
        _SNAPSHOT,
        snapshot_date=later.date(),
        observed_at=later,
        occurred_at=later,
        effective_at=later,
        available_at=later,
    )
    base = _features(
        billing=tuple(row for row in _BILLING if row.invoice.invoice_date <= _T.date())
    )
    extended = _features(
        lifecycle=(_FACT, termination),
        usage=(*_USAGE, late_usage),
        snapshots=(_SNAPSHOT, future_snapshot),
        corrections=(correction,),
    )
    assert extended == base
    assert _features(later, corrections=(correction,)).predictors.plan_id == "growth"


def test_latest_invoice_status_does_not_backfill_historical_payment() -> None:
    invoice = _BILLING[2]
    future = _T + timedelta(days=1)
    paid = replace(
        invoice,
        invoice=replace(
            invoice.invoice, invoice_status=InvoiceStatus.PAID, paid_date=future.date()
        ),
        payment_event=replace(
            invoice.payment_event,
            status=InvoiceStatus.PAID,
            occurred_at=future,
            effective_at=future,
            available_at=future,
        ),
    )
    historical = _features(billing=(paid,)).predictors
    assert historical.invoices_issued == 1
    assert historical.invoices_paid_known == historical.invoices_failed_known == 0
    assert _features(future, billing=(paid,)).predictors.invoices_paid_known == 1


def test_preserves_explicit_reasons_for_insufficient_or_invalid_history() -> None:
    assert _features(history_start=date(2024, 4, 1)).exclusion is (
        IneligibilityReason.INSUFFICIENT_HISTORY
    )
    assert _features(snapshots=()).exclusion is IneligibilityReason.MISSING_HISTORICAL_STATE
    assert _features(lifecycle=()).predictors.episode_age_days is None
    missing_usage = _features(usage=(replace(_USAGE[0], available_at=None), _USAGE[1]))
    assert not missing_usage.predictors.usage_coverage_complete
    assert missing_usage.predictors.observed_usage_months == 1
    with pytest.raises(ExperimentEvidenceError, match="different episode"):
        _features(usage=(replace(_USAGE[0], subscription_id="different"),))
