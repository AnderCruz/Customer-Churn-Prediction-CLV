"""Validate explicit monthly usage and historical snapshot facts."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    calculate_catalogue_charge,
)
from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode


class ObservationError(ValueError):
    """A supplied usage or snapshot fact violates a supported invariant."""


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """A monthly usage fact with caller-supplied inclusive period bounds."""

    subscription_id: str
    usage_month: date
    period_start: date
    period_end: date
    active_users: int | None = None
    total_users: int | None = None
    sessions_count: int | None = None
    events_count: int | None = None
    usage_volume: Decimal | None = None
    usage_metric: str | None = None
    available_at: datetime | None = None

    def __post_init__(self) -> None:
        _check_reference(self.subscription_id)
        if self.available_at is not None and (
            type(self.available_at) is not datetime or self.available_at.utcoffset() is None
        ):
            raise ObservationError("Usage availability must be timezone-aware.")
        if any(
            type(day) is not date for day in (self.usage_month, self.period_start, self.period_end)
        ):
            raise ObservationError("Expected explicit usage dates.")
        if not self.period_start <= self.usage_month <= self.period_end:
            raise ObservationError("The usage label must fall within the supplied period.")
        for count in (self.active_users, self.total_users, self.sessions_count, self.events_count):
            if count is not None and (type(count) is not int or not 0 <= count < 2**63):
                raise ObservationError("Expected a non-negative signed 64-bit usage count.")
        if (
            self.active_users is not None
            and self.total_users is not None
            and self.active_users > self.total_users
        ):
            raise ObservationError("Active users exceed total users.")
        if self.usage_volume is not None and (
            type(self.usage_volume) is not Decimal
            or not self.usage_volume.is_finite()
            or self.usage_volume < 0
        ):
            raise ObservationError("Expected a finite non-negative Decimal usage volume.")
        if self.usage_metric is not None and (
            type(self.usage_metric) is not str or not self.usage_metric.strip()
        ):
            raise ObservationError("Expected a non-empty usage metric.")


@dataclass(frozen=True, slots=True)
class SnapshotRecord:
    """An explicit historical state and its shared evidence timestamps."""

    subscription_id: str
    snapshot_date: date
    subscription_status: EpisodeStatus
    observed_at: datetime
    occurred_at: datetime
    effective_at: datetime
    available_at: datetime
    plan_id: str | None = None
    billing_frequency: BillingFrequency | None = None
    recurring_revenue: Decimal | None = None
    currency: str | None = None
    auto_renew: bool | None = None

    def __post_init__(self) -> None:
        _check_reference(self.subscription_id)
        if (
            type(self.snapshot_date) is not date
            or type(self.subscription_status) is not EpisodeStatus
        ):
            raise ObservationError("Expected a snapshot date and a supported historical status.")
        if any(
            type(stamp) is not datetime or stamp.utcoffset() is None
            for stamp in (self.observed_at, self.occurred_at, self.effective_at, self.available_at)
        ):
            raise ObservationError("Snapshot evidence timestamps must be timezone-aware.")
        observed = self.observed_at.astimezone(UTC)
        if observed.date() != self.snapshot_date:
            raise ObservationError("The observation must match the snapshot date in UTC.")
        if any(
            stamp.astimezone(UTC) > observed
            for stamp in (self.occurred_at, self.effective_at, self.available_at)
        ):
            raise ObservationError("Snapshot evidence extends beyond the observation.")
        if self.auto_renew is not None and type(self.auto_renew) is not bool:
            raise ObservationError("Expected a Boolean renewal flag.")
        commercial = (self.plan_id, self.billing_frequency, self.recurring_revenue, self.currency)
        if any(value is not None for value in commercial):
            if (
                self.plan_id is None
                or self.billing_frequency is None
                or self.currency != "GBP"
                or type(self.recurring_revenue) is not Decimal
                or not self.recurring_revenue.is_finite()
            ):
                raise ObservationError("Expected complete historical GBP catalogue facts.")
            charge = calculate_catalogue_charge(self.plan_id, self.billing_frequency)
            if self.recurring_revenue != charge.recurring_revenue:
                raise ObservationError("Expected monthly-normalised catalogue revenue.")


def _check_reference(identifier: str) -> None:
    if type(identifier) is not str or not identifier or identifier.strip() != identifier:
        raise ObservationError("Expected an explicit subscription identifier.")


def _validate_records[T: (UsageRecord, SnapshotRecord)](
    records: Iterable[T],
    episodes: Iterable[SubscriptionEpisode],
    record_type: type[T],
    cutoff: date,
) -> tuple[T, ...]:
    if type(cutoff) is not date:
        raise ObservationError("Expected an explicit extraction cutoff date.")
    by_id: dict[str, SubscriptionEpisode] = {}
    seen_ids: set[str] = set()
    for episode in episodes:
        if type(episode) is not SubscriptionEpisode or episode.subscription_id.lower() in seen_ids:
            raise ObservationError("Expected unique typed subscription episodes.")
        by_id[episode.subscription_id] = episode
        seen_ids.add(episode.subscription_id.lower())
    grouped: dict[tuple[str, date], T] = {}
    for record in records:
        if type(record) is not record_type:
            raise ObservationError("Expected a supported typed observation record.")
        episode = by_id.get(record.subscription_id)
        if episode is None:
            raise ObservationError("Unknown observation subscription.")
        if isinstance(record, UsageRecord):
            if (
                record.period_start < episode.start_date
                or record.period_end > cutoff
                or (episode.end_date is not None and record.period_end > episode.end_date)
            ):
                raise ObservationError("The usage period exceeds the supplied episode or cutoff.")
            if (
                record.available_at is not None
                and record.available_at.astimezone(UTC).date() > cutoff
            ):
                raise ObservationError("Usage availability exceeds the supplied cutoff.")
            day = record.usage_month.replace(day=1)
        else:
            if not episode.start_date <= record.snapshot_date <= cutoff:
                raise ObservationError("The snapshot date exceeds the supplied start or cutoff.")
            if any(
                stamp.astimezone(UTC).date() < episode.start_date
                for stamp in (record.occurred_at, record.effective_at)
            ):
                raise ObservationError("Snapshot evidence precedes the supplied episode start.")
            day = record.snapshot_date
        key = (record.subscription_id, day)
        if key in grouped:
            raise ObservationError("Duplicate observation grain.")
        grouped[key] = record
    return tuple(grouped[key] for key in sorted(grouped))


def validate_usage(
    records: Iterable[UsageRecord], episodes: Iterable[SubscriptionEpisode], *, cutoff: date
) -> tuple[UsageRecord, ...]:
    """Validate explicit usage periods and order by subscription and labelled month."""
    return _validate_records(records, episodes, UsageRecord, cutoff)


def validate_snapshots(
    records: Iterable[SnapshotRecord], episodes: Iterable[SubscriptionEpisode], *, cutoff: date
) -> tuple[SnapshotRecord, ...]:
    """Validate and order explicitly evidenced historical snapshots."""
    return _validate_records(records, episodes, SnapshotRecord, cutoff)
