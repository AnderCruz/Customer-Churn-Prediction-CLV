"""Construct the explicitly authorised fictional lifecycle and stable source keys."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from json import dumps

from nowa_customer_intelligence.data.synthetic.configuration import EffectiveConfiguration
from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord
from nowa_customer_intelligence.data.synthetic.episodes import (
    EpisodeEvent,
    EpisodeEventType,
    EpisodeStatus,
    EpisodeValidationError,
    SubscriptionEpisode,
    build_episode_population,
)
from nowa_customer_intelligence.data.synthetic.identity_registry import (
    EpisodeIdentity,
    EpisodeIdentityRegistry,
)
from nowa_customer_intelligence.data.synthetic.random_streams import create_random_stream


class LifecycleKind(StrEnum):
    """Explicit facts used by the fictional baseline only."""

    ESTABLISHED = "established"
    ACTIVATED = "activated"
    RENEWED = "renewed"
    TERMINATED = "terminated"
    REACTIVATED = "reactivated"


@dataclass(frozen=True, slots=True)
class LifecycleFact:
    """An effective event with independent occurrence and availability timestamps."""

    subscription_id: str
    kind: LifecycleKind
    occurred_at: datetime
    effective_at: datetime
    available_at: datetime

    def __post_init__(self) -> None:
        if type(self.kind) is not LifecycleKind:
            raise EpisodeValidationError("Unsupported fictional lifecycle event.")
        if any(
            type(stamp) is not datetime or stamp.utcoffset() is None
            for stamp in (self.occurred_at, self.effective_at, self.available_at)
        ):
            raise EpisodeValidationError("Expected timezone-aware lifecycle evidence.")


@dataclass(frozen=True, slots=True)
class GeneratedEpisode:
    """A supplied Registry identity and explicitly generated history."""

    identity: EpisodeIdentity
    episode: SubscriptionEpisode
    paid_activation: date
    facts: tuple[LifecycleFact, ...]
    prior_subscription_id: str | None = None


@dataclass(frozen=True, slots=True)
class _Establishment:
    owner: CustomerRecord
    identity: EpisodeIdentity
    start: date
    end: date | None
    prior_source_key: str | None


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _establishment(
    effective: EffectiveConfiguration,
    owner: CustomerRecord,
    client: str,
    namespace: str,
    start: date,
    end: date | None,
    prior: str | None,
) -> _Establishment:
    # The explicit role and predecessor distinguish establishment facts, independent of row order.
    key_payload = dumps(
        [
            effective.scenario_id,
            effective.scenario_version,
            effective.master_seed,
            owner.customer_id,
            prior,
        ],
        separators=(",", ":"),
    ).encode()
    key = sha256(key_payload).hexdigest()
    evidence = sha256(
        dumps([key, owner.customer_id, start.isoformat(), prior], separators=(",", ":")).encode()
    ).hexdigest()
    return _Establishment(
        owner, EpisodeIdentity(client, namespace, key, evidence), start, end, prior
    )


def generate_episodes(
    effective: EffectiveConfiguration,
    customers: tuple[CustomerRecord, ...],
    registry: EpisodeIdentityRegistry,
    *,
    client: str,
    namespace: str,
    target: int,
    activation_evidence_lag_days: int = 0,
) -> tuple[GeneratedEpisode, ...]:
    """Generate at most one explicit post-termination reactivation per customer."""
    if type(effective) is not EffectiveConfiguration or any(
        type(owner) is not CustomerRecord for owner in customers
    ):
        raise EpisodeValidationError("Expected resolved configuration and typed customer facts.")
    if len(customers) != effective.population.customer_count or len(
        {owner.customer_id for owner in customers}
    ) != len(customers):
        raise EpisodeValidationError("Customer population does not match the requested count.")
    bounds = effective.population
    if (
        type(target) is not int
        or not bounds.episode_count_min <= target <= bounds.episode_count_max
        or target < len(customers)
    ):
        raise EpisodeValidationError("The episode target is outside the supported bounds.")
    if type(activation_evidence_lag_days) is not int or activation_evidence_lag_days < 0:
        raise EpisodeValidationError("Expected a non-negative activation evidence lag.")
    cutoff = date.fromisoformat(effective.history.cutoff_date)
    if activation_evidence_lag_days > (date.max - cutoff).days:
        raise EpisodeValidationError("Activation evidence lag exceeds the supported date range.")
    start = date.fromisoformat(effective.history.start_date)
    owners = sorted(customers, key=lambda owner: owner.customer_id)
    if any(
        type(owner.created_at) is not date or not start <= owner.created_at <= cutoff
        for owner in owners
    ):
        raise EpisodeValidationError("Customer creation falls outside configured history.")
    candidates = [owner for owner in owners if (cutoff - owner.created_at).days >= 3]
    extra = target - len(owners)
    if extra > len(candidates):
        raise EpisodeValidationError(
            "History cannot support the requested exclusive reactivations."
        )
    stream = create_random_stream(
        effective.master_seed, "episode.reactivation", namespace=effective.scenario_id
    )
    reactivated = {
        candidates[int(index)].customer_id
        for index in stream.choice(len(candidates), size=extra, replace=False)
    }
    pending = []
    for owner in owners:
        end = None
        if owner.customer_id in reactivated:
            end = owner.created_at + timedelta(days=(cutoff - owner.created_at).days // 2)
        initial = _establishment(effective, owner, client, namespace, owner.created_at, end, None)
        pending.append(initial)
        if end is not None:
            pending.append(
                _establishment(
                    effective,
                    owner,
                    client,
                    namespace,
                    end + timedelta(days=1),
                    None,
                    initial.identity.source_key,
                )
            )
    allocations = registry.allocate_many(row.identity for row in pending)
    identifiers = {
        row.identity.source_key: identifier
        for row, identifier in zip(pending, allocations, strict=True)
    }
    generated = []
    for row, identifier in zip(pending, allocations, strict=True):
        opened = _midnight(row.start)
        available = opened + timedelta(days=activation_evidence_lag_days)
        episode = SubscriptionEpisode(
            identifier,
            row.owner.customer_id,
            row.start,
            EpisodeStatus.ACTIVE if row.end is None else EpisodeStatus.EXPIRED,
            end_date=row.end,
            establishment=EpisodeEvent(
                row.identity.establishment_ref, EpisodeEventType.ESTABLISHED, opened, opened, opened
            ),
        )
        facts = [
            LifecycleFact(identifier, LifecycleKind.ESTABLISHED, opened, opened, opened),
            LifecycleFact(identifier, LifecycleKind.ACTIVATED, opened, opened, available),
        ]
        if row.prior_source_key is not None:
            facts.append(
                LifecycleFact(identifier, LifecycleKind.REACTIVATED, opened, opened, available)
            )
        if row.end is not None:
            ended = _midnight(row.end)
            facts.append(LifecycleFact(identifier, LifecycleKind.TERMINATED, ended, ended, ended))
        generated.append(
            GeneratedEpisode(
                row.identity,
                episode,
                row.start,
                tuple(facts),
                identifiers[row.prior_source_key] if row.prior_source_key is not None else None,
            )
        )
    order = build_episode_population(customers, (row.episode for row in generated))
    by_id = {row.episode.subscription_id: row for row in generated}
    return tuple(by_id[episode.subscription_id] for episode in order)


def validate_lifecycle(episodes: tuple[GeneratedEpisode, ...], *, cutoff: date) -> None:
    """Validate baseline transitions, reactivation lineage and non-overlap."""
    identifiers = {row.episode.subscription_id.lower() for row in episodes}
    if len(identifiers) != len(episodes):
        raise EpisodeValidationError("Duplicate subscription identifier.")
    groups: dict[str, list[GeneratedEpisode]] = {}
    for row in episodes:
        groups.setdefault(row.episode.customer_id, []).append(row)
        episode = row.episode
        expected_prefix = (
            LifecycleKind.ESTABLISHED,
            LifecycleKind.ACTIVATED,
            *((LifecycleKind.REACTIVATED,) if row.prior_subscription_id is not None else ()),
        )
        kinds = tuple(fact.kind for fact in row.facts)
        close = (LifecycleKind.TERMINATED,) if episode.end_date is not None else ()
        if kinds != (
            *expected_prefix,
            *((LifecycleKind.RENEWED,) * kinds.count(LifecycleKind.RENEWED)),
            *close,
        ):
            raise EpisodeValidationError("Unsupported fictional lifecycle transition.")
        if episode.subscription_status is not (
            EpisodeStatus.EXPIRED if close else EpisodeStatus.ACTIVE
        ):
            raise EpisodeValidationError("Episode status contradicts its explicit lifecycle.")
        effective_times = [fact.effective_at.astimezone(UTC) for fact in row.facts]
        event_dates = [stamp.date() for stamp in effective_times]
        if effective_times != sorted(effective_times) or row.paid_activation != event_dates[1]:
            raise EpisodeValidationError("Fictional lifecycle events are out of order.")
        if event_dates[0] != episode.start_date or (
            close
            and (event_dates[-1] != episode.end_date or effective_times[-1] <= effective_times[1])
        ):
            raise EpisodeValidationError("Fictional lifecycle facts contradict episode dates.")
        if any(
            fact.subscription_id != episode.subscription_id
            or fact.effective_at.astimezone(UTC).date() > cutoff
            or fact.occurred_at.astimezone(UTC).date() > cutoff
            or fact.available_at.astimezone(UTC) < fact.occurred_at.astimezone(UTC)
            for fact in row.facts
        ):
            raise EpisodeValidationError("Invalid fictional lifecycle evidence.")
        renewal_dates = [
            fact.effective_at.astimezone(UTC).date()
            for fact in row.facts
            if fact.kind is LifecycleKind.RENEWED
        ]
        if len(renewal_dates) != len(set(renewal_dates)) or any(
            day <= row.paid_activation or (episode.end_date is not None and day >= episode.end_date)
            for day in renewal_dates
        ):
            raise EpisodeValidationError("Invalid fictional renewal evidence.")

    for population in groups.values():
        population.sort(key=lambda row: row.episode.start_date)
        previous = None
        for row in population:
            if previous is None:
                if row.prior_subscription_id is not None:
                    raise EpisodeValidationError("Reactivation lacks its prior episode.")
            elif (
                row.prior_subscription_id != previous.episode.subscription_id
                or previous.episode.end_date is None
                or row.episode.start_date <= previous.episode.end_date
            ):
                raise EpisodeValidationError("Episode overlap or invalid reactivation lineage.")
            previous = row
