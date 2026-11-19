"""Hold supplied synthetic outcome evidence independently of contract projection."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from nowa_customer_intelligence.data.synthetic.episodes import SubscriptionEpisode


class OutcomeEvidenceError(ValueError):
    """An explicit internal outcome fact violates an evidence boundary."""


class OutcomeState(StrEnum):
    """Internal supplied classifications without binary label semantics."""

    CONFIRMED_POSITIVE = "confirmed_positive"
    CONFIRMED_NEGATIVE = "confirmed_negative"
    RIGHT_CENSORED = "right_censored"
    PENDING_ASCERTAINMENT = "pending_ascertainment"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True, slots=True)
class OutcomeEvidence:
    """Reference a source fact and when its information was available."""

    source_ref: str
    available_at: datetime
    occurred_at: datetime | None = None
    effective_at: datetime | None = None

    def __post_init__(self) -> None:
        if type(self.source_ref) is not str or not self.source_ref.strip():
            raise OutcomeEvidenceError("Expected an explicit source fact reference.")
        _utc(self.available_at)
        for timestamp in (self.occurred_at, self.effective_at):
            if timestamp is not None:
                _utc(timestamp)


def _utc(timestamp: datetime) -> datetime:
    if type(timestamp) is not datetime or timestamp.utcoffset() is None:
        raise OutcomeEvidenceError("Expected timezone-aware outcome timestamps.")
    return timestamp.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class OutcomeRecord:
    """An episode observation with a supplied, semantically uncertified outcome."""

    subscription_id: str
    observation_at: datetime
    ascertainment_cutoff: datetime
    state: OutcomeState
    evidence: tuple[OutcomeEvidence, ...] = ()
    follow_up_through: datetime | None = None

    @property
    def semantically_certified(self) -> bool:
        """Policy certification remains unavailable for supplied classifications."""
        return False

    def __post_init__(self) -> None:
        if type(self.subscription_id) is not str or not self.subscription_id.strip():
            raise OutcomeEvidenceError("Expected an episode reference.")
        if type(self.state) is not OutcomeState:
            raise OutcomeEvidenceError("Expected a supported internal outcome state.")
        observation = _utc(self.observation_at)
        ascertainment = _utc(self.ascertainment_cutoff)
        if ascertainment < observation:
            raise OutcomeEvidenceError("Ascertainment precedes the observation.")
        if self.follow_up_through is not None and not (
            observation <= _utc(self.follow_up_through) <= ascertainment
        ):
            raise OutcomeEvidenceError("Follow-up is outside the supplied observation interval.")
        if type(self.evidence) is not tuple or any(
            type(fact) is not OutcomeEvidence for fact in self.evidence
        ):
            raise OutcomeEvidenceError("Expected immutable typed outcome evidence.")
        if len({fact.source_ref for fact in self.evidence}) != len(self.evidence):
            raise OutcomeEvidenceError("Duplicate outcome evidence reference.")
        if any(
            _utc(stamp) > ascertainment
            for fact in self.evidence
            for stamp in (fact.available_at, fact.occurred_at, fact.effective_at)
            if stamp is not None
        ):
            raise OutcomeEvidenceError("Outcome evidence extends beyond ascertainment.")
        if self.state is OutcomeState.CONFIRMED_POSITIVE and not any(
            fact.effective_at is not None and _utc(fact.effective_at) > observation
            for fact in self.evidence
        ):
            raise OutcomeEvidenceError(
                "A supplied positive requires explicit post-observation evidence."
            )
        if self.state in (OutcomeState.CONFIRMED_NEGATIVE, OutcomeState.RIGHT_CENSORED) and (
            not self.evidence or self.follow_up_through is None
        ):
            raise OutcomeEvidenceError(
                "The supplied state requires evidence and a follow-up endpoint."
            )


def validate_outcomes(
    outcomes: Iterable[OutcomeRecord], episodes: Iterable[SubscriptionEpisode]
) -> tuple[OutcomeRecord, ...]:
    """Check episode references and order unique episode observations."""
    by_id: dict[str, SubscriptionEpisode] = {}
    identities: set[str] = set()
    for episode in episodes:
        if (
            type(episode) is not SubscriptionEpisode
            or episode.subscription_id.lower() in identities
        ):
            raise OutcomeEvidenceError("Expected unique typed episodes for outcome references.")
        by_id[episode.subscription_id] = episode
        identities.add(episode.subscription_id.lower())
    records: dict[tuple[str, datetime], OutcomeRecord] = {}
    for record in outcomes:
        if type(record) is not OutcomeRecord:
            raise OutcomeEvidenceError("Expected a typed outcome record.")
        episode = by_id.get(record.subscription_id)
        if episode is None:
            raise OutcomeEvidenceError("Unknown outcome episode.")
        observation = _utc(record.observation_at)
        if observation.date() < episode.start_date:
            raise OutcomeEvidenceError("Outcome observation precedes episode start.")
        key = (record.subscription_id, observation)
        if key in records:
            raise OutcomeEvidenceError("Duplicate episode observation.")
        records[key] = record
    return tuple(records[key] for key in sorted(records))
