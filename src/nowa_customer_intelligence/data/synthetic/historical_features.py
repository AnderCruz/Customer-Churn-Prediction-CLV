"""Construct allowlisted predictors from facts available at an observation cutoff."""

from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from statistics import mean

from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    InvoiceStatus,
    ScheduledCharge,
    calculate_catalogue_charge,
)
from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    ChurnExperiment,
    ExperimentEvidenceError,
    ExperimentObservation,
    IneligibilityReason,
    utc_instant,
)
from nowa_customer_intelligence.data.synthetic.lifecycle import LifecycleFact, LifecycleKind
from nowa_customer_intelligence.data.synthetic.observations import SnapshotRecord, UsageRecord


@dataclass(frozen=True, slots=True)
class HistoricalPlanCorrection:
    """Explicit historical plan evidence outside the contractual snapshot rows."""

    subscription_id: str
    plan_id: str
    billing_frequency: BillingFrequency
    recurring_revenue: Decimal
    occurred_at: datetime
    effective_at: datetime
    available_at: datetime

    def __post_init__(self) -> None:
        for stamp in (self.occurred_at, self.effective_at, self.available_at):
            utc_instant(stamp)
        charge = calculate_catalogue_charge(self.plan_id, self.billing_frequency)
        if type(self.recurring_revenue) is not Decimal or (
            self.recurring_revenue != charge.recurring_revenue
        ):
            raise ExperimentEvidenceError("Historical commercial amounts contradict the catalogue.")


@dataclass(frozen=True, slots=True)
class HistoricalFeatures:
    """Predictor values only. Identity, timestamps and targets are kept separately."""

    episode_age_days: int | None
    plan_id: str | None
    billing_frequency: str | None
    recurring_revenue: Decimal | None
    active_users_mean: float | None
    sessions_total: int | None
    events_total: int | None
    usage_volume_total: Decimal | None
    recent_active_users_change: int | None
    observed_usage_months: int
    expected_usage_months: int
    usage_coverage_complete: bool
    invoices_issued: int
    invoices_paid_known: int
    invoices_failed_known: int
    invoices_overdue_known: int | None


@dataclass(frozen=True, slots=True)
class HistoricalFeatureResult:
    """Predictors, cutoff evidence and explicit coverage limitations."""

    predictors: HistoricalFeatures
    latest_evidence_at: datetime | None
    unavailable: tuple[str, ...]
    exclusion: IneligibilityReason | None


def _month_end(month: date) -> date:
    return month.replace(day=monthrange(month.year, month.month)[1])


def _completed_months(start: datetime, through: datetime) -> set[date]:
    month = start.date().replace(day=1)
    months = set()
    while month <= through.date():
        end = _month_end(month)
        if (
            datetime.combine(month, time.min, UTC) >= start
            and datetime.combine(end, time.max, UTC) <= through
        ):
            months.add(month)
        if end >= through.date():
            break
        month = end + timedelta(days=1)
    return months


def _complete_sum(values: list[int | Decimal | None]) -> int | Decimal | None:
    if not values or any(value is None for value in values):
        return None
    return sum(value for value in values if value is not None)


def build_historical_features(
    subscription_id: str,
    observation: ExperimentObservation,
    experiment: ChurnExperiment,
    *,
    history_start: date,
    lifecycle: tuple[LifecycleFact, ...],
    snapshots: tuple[SnapshotRecord, ...],
    usage: tuple[UsageRecord, ...],
    billing: tuple[ScheduledCharge, ...],
    corrections: tuple[HistoricalPlanCorrection, ...] = (),
) -> HistoricalFeatureResult:
    """Build an as-known view without reading the final subscription master or targets."""
    start, t, _, _ = observation.bounds(experiment)
    if any(
        row.subscription_id != subscription_id
        for rows in (lifecycle, snapshots, usage, corrections)
        for row in rows
    ) or any(row.invoice.subscription_id != subscription_id for row in billing):
        raise ExperimentEvidenceError("Historical facts belong to a different episode.")

    # Use activation evidence only. Terminations and outcome facts are never predictor inputs.
    activations = [
        fact
        for fact in lifecycle
        if fact.kind is LifecycleKind.ACTIVATED
        and max(
            utc_instant(fact.occurred_at),
            utc_instant(fact.effective_at),
            utc_instant(fact.available_at),
        )
        <= t
    ]
    if len(activations) > 1:
        raise ExperimentEvidenceError("Conflicting historical activation evidence.")
    activation = activations[0] if activations else None
    evidence = []
    if activation is not None:
        evidence.append(utc_instant(activation.available_at))

    commercial = []
    for record in snapshots:
        if (
            record.snapshot_date <= t.date()
            and max(
                utc_instant(record.observed_at),
                utc_instant(record.occurred_at),
                utc_instant(record.effective_at),
                utc_instant(record.available_at),
            )
            <= t
            and record.plan_id is not None
            and record.billing_frequency is not None
            and record.recurring_revenue is not None
        ):
            commercial.append(
                (
                    (utc_instant(record.observed_at), utc_instant(record.available_at)),
                    (record.plan_id, record.billing_frequency.value, record.recurring_revenue),
                )
            )
    for correction in corrections:
        if (
            max(
                utc_instant(correction.effective_at),
                utc_instant(correction.occurred_at),
                utc_instant(correction.available_at),
            )
            <= t
        ):
            commercial.append(
                (
                    (utc_instant(correction.effective_at), utc_instant(correction.available_at)),
                    (
                        correction.plan_id,
                        correction.billing_frequency.value,
                        correction.recurring_revenue,
                    ),
                )
            )
    prices = (None, None, None)
    if commercial:
        last = max(rank for rank, _ in commercial)
        latest = {values for rank, values in commercial if rank == last}
        if len(latest) != 1:
            raise ExperimentEvidenceError("Contradictory historical commercial evidence.")
        prices = latest.pop()
        evidence.append(last[1])

    expected = _completed_months(start, t)
    monthly = {}
    for row in usage:
        if (
            row.period_start in expected
            and row.period_end == _month_end(row.period_start)
            and row.available_at is not None
            and start <= utc_instant(row.available_at) <= t
        ):
            if row.period_start in monthly:
                raise ExperimentEvidenceError("Duplicate historical usage month.")
            monthly[row.period_start] = row
            evidence.append(utc_instant(row.available_at))
    months = sorted(monthly)
    rows = [monthly[month] for month in months]
    active = [record.active_users for record in rows if record.active_users is not None]
    recent_change = None
    if len(rows) >= 2 and _month_end(months[-2]) + timedelta(days=1) == months[-1]:
        prev, recent = rows[-2].active_users, rows[-1].active_users
        if prev is not None and recent is not None:
            recent_change = recent - prev

    issued = known_paid = known_failed = known_overdue = 0
    overdue_evidence = False
    used_invoice_ids: set[str] = set()
    for charge in billing:
        issue = datetime.combine(charge.invoice.invoice_date, time.min, UTC)
        if not start <= issue <= t:
            continue
        if charge.invoice.invoice_id in used_invoice_ids:
            raise ExperimentEvidenceError("Duplicate historical invoice identity.")
        used_invoice_ids.add(charge.invoice.invoice_id)
        issued += 1
        evidence.append(issue)
        event = charge.payment_event
        if event.invoice_id != charge.invoice.invoice_id:
            raise ExperimentEvidenceError("Payment evidence does not match its invoice.")
        if (
            max(
                utc_instant(event.occurred_at),
                utc_instant(event.effective_at),
                utc_instant(event.available_at),
            )
            <= t
        ):
            evidence.append(utc_instant(event.available_at))
            known_paid += event.status is InvoiceStatus.PAID
            known_failed += event.status is InvoiceStatus.FAILED
            known_overdue += event.status is InvoiceStatus.OVERDUE
            overdue_evidence |= event.status is InvoiceStatus.OVERDUE

    exclusion = None
    if activation is None or not commercial:
        exclusion = IneligibilityReason.MISSING_HISTORICAL_STATE
    elif start.date() < history_start or utc_instant(activation.effective_at) > start:
        exclusion = IneligibilityReason.INSUFFICIENT_HISTORY

    predictors = HistoricalFeatures(
        (t - utc_instant(activation.effective_at)).days if activation is not None else None,
        *prices,
        mean(active) if active else None,
        _complete_sum([row.sessions_count for row in rows]),
        _complete_sum([row.events_count for row in rows]),
        _complete_sum([row.usage_volume for row in rows]),
        recent_change,
        len(months),
        len(expected),
        bool(expected) and set(months) == expected,
        issued,
        known_paid,
        known_failed,
        known_overdue if overdue_evidence else None,
    )
    unavailable = tuple(
        name
        for name, value in (
            ("usage_volume_unavailable", predictors.usage_volume_total),
            ("active_user_history_unavailable", predictors.active_users_mean),
            ("session_history_unavailable", predictors.sessions_total),
            ("event_history_unavailable", predictors.events_total),
            ("activation_evidence_unavailable", predictors.episode_age_days),
            ("overdue_history_unavailable", predictors.invoices_overdue_known),
            ("recent_usage_change_unavailable", predictors.recent_active_users_change),
            ("historical_commercial_state_unavailable", predictors.plan_id),
        )
        if value is None
    )
    if not predictors.usage_coverage_complete:
        unavailable += ("usage_coverage_incomplete",)
    return HistoricalFeatureResult(predictors, max(evidence, default=None), unavailable, exclusion)
