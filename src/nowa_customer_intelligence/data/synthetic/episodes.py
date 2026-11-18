"""Validate explicit synthetic episode facts without allocating identity."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from re import fullmatch
from uuid import RFC_4122, UUID

from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord


class EpisodeValidationError(ValueError):
    """Explicit episode facts violate a supported invariant."""


class EpisodeStatus(StrEnum):
    """Controlled subscription categories from Customer Data Contract v1.1."""

    ACTIVE = "active"
    TRIAL = "trial"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    PAUSED = "paused"


class EpisodeEventType(StrEnum):
    """Events which this foundation can record from explicit evidence."""

    ESTABLISHED = "established"


def _read_supplied_uuid(value: str) -> UUID:
    if type(value) is not str or not fullmatch(
        r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value
    ):
        raise EpisodeValidationError("Expected a supplied hyphenated subscription UUID.")
    identifier = UUID(value)
    if identifier.variant != RFC_4122:
        raise EpisodeValidationError("Expected a supplied standard subscription UUID.")
    return identifier


@dataclass(frozen=True, slots=True)
class EpisodeEvent:
    """Explicit establishment evidence with separate timestamps."""

    event_id: str
    event_type: EpisodeEventType
    occurred_at: datetime
    effective_at: datetime | None = None
    recorded_at: datetime | None = None

    def __post_init__(self) -> None:
        if (
            type(self.event_id) is not str
            or not self.event_id
            or self.event_id.strip() != self.event_id
        ):
            raise EpisodeValidationError("Expected a non-empty event identifier.")
        if self.event_type is not EpisodeEventType.ESTABLISHED:
            raise EpisodeValidationError("The episode transition is outside the supported scope.")
        for timestamp in (self.occurred_at, self.effective_at, self.recorded_at):
            if timestamp is not None and (
                type(timestamp) is not datetime or timestamp.utcoffset() is None
            ):
                raise EpisodeValidationError("Event timestamps must be timezone-aware.")
        if self.occurred_at is None:
            raise EpisodeValidationError("Event occurrence time is required.")


@dataclass(frozen=True, slots=True)
class SubscriptionEpisode:
    """One caller-established contractual episode using a supplied UUID.

    Status and dates are explicit facts. They provide no identity or transition inference.
    """

    subscription_id: str
    customer_id: str
    start_date: date
    subscription_status: EpisodeStatus
    end_date: date | None = None
    cancellation_date: date | None = None
    establishment: EpisodeEvent | None = None

    def __post_init__(self) -> None:
        _read_supplied_uuid(self.subscription_id)
        if (
            type(self.customer_id) is not str
            or not self.customer_id
            or self.customer_id.strip() != self.customer_id
        ):
            raise EpisodeValidationError("Expected a non-empty customer identifier.")
        if type(self.subscription_status) is not EpisodeStatus:
            raise EpisodeValidationError("Expected a supported subscription status.")
        if type(self.start_date) is not date:
            raise EpisodeValidationError("Expected a subscription start date.")
        for boundary in (self.end_date, self.cancellation_date):
            if boundary is not None and (type(boundary) is not date or boundary < self.start_date):
                raise EpisodeValidationError("An episode date is invalid or precedes its start.")
        if self.establishment is not None:
            if type(self.establishment) is not EpisodeEvent:
                raise EpisodeValidationError("Expected explicit establishment evidence.")
            if self.establishment.occurred_at.astimezone(UTC).date() < self.start_date:
                raise EpisodeValidationError("Establishment occurrence precedes the episode start.")


def build_episode_population(
    customers: Iterable[CustomerRecord], episodes: Iterable[SubscriptionEpisode]
) -> tuple[SubscriptionEpisode, ...]:
    """Validate explicit ownership and return episodes ordered by UUID value."""
    owners: dict[str, CustomerRecord] = {}
    for customer in customers:
        if type(customer) is not CustomerRecord or customer.customer_id in owners:
            raise EpisodeValidationError("Expected unique typed customer records.")
        owners[customer.customer_id] = customer
    records: dict[UUID, SubscriptionEpisode] = {}
    event_ids: set[str] = set()
    for episode in episodes:
        if type(episode) is not SubscriptionEpisode:
            raise EpisodeValidationError("Expected typed subscription episodes.")
        identifier = _read_supplied_uuid(episode.subscription_id)
        if identifier in records:
            raise EpisodeValidationError("Duplicate subscription identifier.")
        owner = owners.get(episode.customer_id)
        if owner is None:
            raise EpisodeValidationError("Unknown owning customer.")
        if episode.start_date < owner.created_at:
            raise EpisodeValidationError("The episode starts before customer creation.")
        if episode.establishment is not None:
            event_id = episode.establishment.event_id
            if event_id in event_ids:
                raise EpisodeValidationError("Duplicate establishment event identifier.")
            event_ids.add(event_id)
        records[identifier] = episode
    return tuple(records[identifier] for identifier in sorted(records))
