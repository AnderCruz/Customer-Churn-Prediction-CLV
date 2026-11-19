"""Synthetic-only subscription churn policy and outcome classification."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from nowa_customer_intelligence.data.synthetic.episodes import (
    EpisodeValidationError,
    _read_supplied_uuid,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import OutcomeState

POLICY_ID = "fieldwise-subscription-churn"
POLICY_VERSION = 1


class ExperimentEvidenceError(ValueError):
    """Explicit experiment evidence violates an identity or temporal invariant."""


def utc_instant(value: datetime) -> datetime:
    """Require an explicit aware timestamp and compare it on the UTC timeline."""
    if type(value) is not datetime or value.utcoffset() is None:
        raise ExperimentEvidenceError("Expected a timezone-aware experiment timestamp.")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ChurnExperiment:
    """Versioned fictional experiment parameters independent of configuration v1."""

    extraction_cutoff: datetime
    history_days: int = 90
    horizon_days: int = 30

    def __post_init__(self) -> None:
        utc_instant(self.extraction_cutoff)
        for days in (self.history_days, self.horizon_days):
            if type(days) is not int or days <= 0:
                raise ExperimentEvidenceError("Expected positive whole-day experiment windows.")


@dataclass(frozen=True, slots=True)
class ExperimentObservation:
    """One episode observation with separate feature and adjudication cutoffs."""

    observed_at: datetime
    ascertainment_cutoff: datetime

    def __post_init__(self) -> None:
        if utc_instant(self.observed_at) > utc_instant(self.ascertainment_cutoff):
            raise ExperimentEvidenceError("Ascertainment precedes observation.")

    def bounds(self, experiment: ChurnExperiment) -> tuple[datetime, datetime, datetime, datetime]:
        """Return UTC history start, observation, horizon end and ascertainment."""
        t = utc_instant(self.observed_at)
        a = utc_instant(self.ascertainment_cutoff)
        if a > utc_instant(experiment.extraction_cutoff):
            raise ExperimentEvidenceError("Ascertainment exceeds extraction.")
        try:
            return (
                t - timedelta(days=experiment.history_days),
                t,
                t + timedelta(days=experiment.horizon_days),
                a,
            )
        except OverflowError:
            raise ExperimentEvidenceError(
                "The experiment window exceeds supported dates."
            ) from None


class IneligibilityReason(StrEnum):
    """Structured exclusions rather than implicit binary negatives."""

    INVALID_IDENTITY = "invalid_or_ambiguous_identity"
    INSUFFICIENT_HISTORY = "insufficient_observation_history"
    MISSING_HISTORICAL_STATE = "missing_historical_plan_or_activation"
    EXPLICIT_EXCLUSION = "explicit_exclusion"
    NOT_ACTIVE = "outside_observation_risk_set"


@dataclass(frozen=True, slots=True)
class TerminationEvidence:
    """An explicit synthetic termination candidate and adjudication timestamps."""

    subscription_id: str
    source_ref: str
    occurred_at: datetime
    effective_at: datetime
    available_at: datetime
    resolved_at: datetime | None
    confirmed: bool

    def __post_init__(self) -> None:
        if type(self.source_ref) is not str or not self.source_ref.strip():
            raise ExperimentEvidenceError("Expected authoritative termination evidence.")
        occurrence, availability = utc_instant(self.occurred_at), utc_instant(self.available_at)
        utc_instant(self.effective_at)
        if (
            type(self.confirmed) is not bool
            or (self.confirmed and self.resolved_at is None)
            or (
                self.resolved_at is not None
                and utc_instant(self.resolved_at) < max(occurrence, availability)
            )
        ):
            raise ExperimentEvidenceError("Contradictory termination adjudication evidence.")


@dataclass(frozen=True, slots=True)
class FollowUpEvidence:
    """Explicit attestation of observed, complete episode follow-up."""

    subscription_id: str
    source_ref: str
    complete_through: datetime
    available_at: datetime

    def __post_init__(self) -> None:
        if type(self.source_ref) is not str or not self.source_ref.strip():
            raise ExperimentEvidenceError("Expected explicit follow-up evidence.")
        if utc_instant(self.available_at) < utc_instant(self.complete_through):
            raise ExperimentEvidenceError("Follow-up was recorded before it was complete.")


@dataclass(frozen=True, slots=True)
class OutcomeClassification:
    """Internal outcome with a binary target only for resolved classes."""

    state: OutcomeState
    reason: str
    source_ref: str | None = None

    @property
    def binary_target(self) -> int | None:
        """Return the experiment target, preserving unresolved states as missing."""
        if self.state is OutcomeState.CONFIRMED_POSITIVE:
            return 1
        if self.state is OutcomeState.CONFIRMED_NEGATIVE:
            return 0
        return None


def classify_outcome(
    subscription_id: str,
    observation: ExperimentObservation,
    experiment: ChurnExperiment,
    *,
    terminations: tuple[TerminationEvidence, ...] = (),
    follow_up: FollowUpEvidence | None = None,
    exclusion: IneligibilityReason | None = None,
) -> OutcomeClassification:
    """Classify from explicit facts for this episode and this observation only."""
    _, t, horizon, ascertainment = observation.bounds(experiment)
    try:
        _read_supplied_uuid(subscription_id)
    except EpisodeValidationError:
        return OutcomeClassification(OutcomeState.INELIGIBLE, IneligibilityReason.INVALID_IDENTITY)
    if exclusion is not None:
        if type(exclusion) is not IneligibilityReason:
            raise ExperimentEvidenceError("Expected a supported eligibility exclusion.")
        return OutcomeClassification(OutcomeState.INELIGIBLE, exclusion)
    if any(fact.subscription_id != subscription_id for fact in terminations) or (
        follow_up is not None and follow_up.subscription_id != subscription_id
    ):
        raise ExperimentEvidenceError("Outcome evidence belongs to a different episode.")
    if (
        len({fact.source_ref for fact in terminations}) != len(terminations)
        or sum(fact.confirmed for fact in terminations) > 1
    ):
        raise ExperimentEvidenceError("Duplicate or contradictory termination evidence.")
    through = None
    if follow_up is not None:
        through = utc_instant(follow_up.complete_through)
        if not t <= through <= utc_instant(experiment.extraction_cutoff):
            raise ExperimentEvidenceError("Follow-up exceeds the supported observation interval.")

    pending = False
    for fact in terminations:
        effective = utc_instant(fact.effective_at)
        resolved = (
            fact.resolved_at is not None
            and max(utc_instant(fact.resolved_at), utc_instant(fact.available_at)) <= ascertainment
        )
        if fact.confirmed and resolved and effective <= t:
            return OutcomeClassification(OutcomeState.INELIGIBLE, IneligibilityReason.NOT_ACTIVE)
        if effective <= t and not resolved:
            pending = True
        if not t < effective <= horizon:
            continue
        if fact.confirmed and resolved and effective <= ascertainment:
            return OutcomeClassification(
                OutcomeState.CONFIRMED_POSITIVE, "qualified_effective_termination", fact.source_ref
            )
        if not resolved or fact.confirmed:
            pending = True
    if pending:
        return OutcomeClassification(OutcomeState.PENDING_ASCERTAINMENT, "unresolved_candidate")
    if follow_up is None or utc_instant(follow_up.available_at) > ascertainment:
        return OutcomeClassification(
            OutcomeState.PENDING_ASCERTAINMENT, "missing_ascertained_follow_up"
        )
    if through < horizon:
        return OutcomeClassification(
            OutcomeState.RIGHT_CENSORED, "complete_partial_follow_up", follow_up.source_ref
        )
    return OutcomeClassification(
        OutcomeState.CONFIRMED_NEGATIVE,
        "complete_horizon_without_termination",
        follow_up.source_ref,
    )
