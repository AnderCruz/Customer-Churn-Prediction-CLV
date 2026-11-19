"""Evaluate independent rules over explicitly supplied synthetic evidence."""

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from enum import StrEnum

from nowa_customer_intelligence.data.synthetic.billing import (
    BillingValidationError,
    InvoiceFact,
    validate_invoice_relationships,
)
from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord
from nowa_customer_intelligence.data.synthetic.episodes import (
    EpisodeValidationError,
    SubscriptionEpisode,
    build_episode_population,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import (
    OutcomeEvidenceError,
    OutcomeRecord,
    validate_outcomes,
)
from nowa_customer_intelligence.data.synthetic.observations import (
    ObservationError,
    SnapshotRecord,
    UsageRecord,
    validate_snapshots,
    validate_usage,
)


class ValidationStatus(StrEnum):
    """Internal outcomes distinct from pipeline execution status."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"
    BLOCKED_BY_UNRESOLVED_POLICY = "BLOCKED_BY_UNRESOLVED_POLICY"


@dataclass(frozen=True, slots=True)
class EvidenceFinding:
    """A rule outcome with a fixed diagnostic category and optional decision IDs."""

    rule: str
    status: ValidationStatus
    reason: str
    decisions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ReactivationEvidence:
    """Explicit historical separation evidence supplied by the fixture author."""

    prior_subscription_id: str
    next_subscription_id: str
    terminated_at: datetime
    established_at: datetime


def _aware(value: datetime) -> bool:
    return type(value) is datetime and value.utcoffset() is not None


def _evaluate(rule: str, reason: str, check: Callable[[], object]) -> EvidenceFinding:
    try:
        check()
    except (EpisodeValidationError, BillingValidationError, OutcomeEvidenceError, ObservationError):
        return EvidenceFinding(rule, ValidationStatus.FAILED, reason)
    return EvidenceFinding(rule, ValidationStatus.PASSED, "verified_supplied_facts")


def _not_evaluated(rule: str) -> EvidenceFinding:
    return EvidenceFinding(rule, ValidationStatus.NOT_EVALUATED, "required_evidence_unavailable")


def _check_binding(
    rule: str, declared: Mapping[str, str] | None, actual: Mapping[str, str]
) -> EvidenceFinding:
    if declared is None or not actual:
        if declared:
            return EvidenceFinding(rule, ValidationStatus.FAILED, "unknown_source_fact")
        return _not_evaluated(rule)
    if any(key not in actual or actual[key] != value for key, value in declared.items()):
        return EvidenceFinding(rule, ValidationStatus.FAILED, "contradictory_source_attribution")
    if declared.keys() != actual.keys():
        return _not_evaluated(rule)
    return EvidenceFinding(rule, ValidationStatus.PASSED, "verified_explicit_attribution")


def _history(
    episodes: Mapping[str, SubscriptionEpisode],
    links: tuple[ReactivationEvidence, ...],
    cutoff: date,
) -> EvidenceFinding:
    rule = "historical_episode_separation"
    if not links:
        return _not_evaluated(rule)
    seen: set[str] = set()
    for link in links:
        if type(link) is not ReactivationEvidence or any(
            type(identifier) is not str
            for identifier in (link.prior_subscription_id, link.next_subscription_id)
        ):
            return EvidenceFinding(rule, ValidationStatus.FAILED, "invalid_lineage_evidence")
        prior = episodes.get(link.prior_subscription_id)
        successor = episodes.get(link.next_subscription_id)
        if (
            prior is None
            or successor is None
            or prior is successor
            or prior.customer_id != successor.customer_id
            or successor.subscription_id in seen
            or not _aware(link.terminated_at)
            or not _aware(link.established_at)
        ):
            return EvidenceFinding(rule, ValidationStatus.FAILED, "contradictory_episode_lineage")
        termination = link.terminated_at.astimezone(UTC)
        establishment = link.established_at.astimezone(UTC)
        # The prior master end date is not treated as evidence of termination.
        if (
            termination >= establishment
            or termination.date() < prior.start_date
            or successor.start_date < termination.date()
            or establishment.date() < successor.start_date
            or establishment.date() > cutoff
            or (
                prior.establishment is not None
                and prior.establishment.occurred_at.astimezone(UTC) > termination
            )
            or (
                successor.establishment is not None
                and successor.establishment.occurred_at.astimezone(UTC) != establishment
            )
        ):
            return EvidenceFinding(
                rule, ValidationStatus.FAILED, "contradictory_episode_chronology"
            )
        seen.add(successor.subscription_id)
    predecessors = {link.next_subscription_id: link.prior_subscription_id for link in links}
    checked: set[str] = set()
    for successor in predecessors:
        visited = set()
        while successor in predecessors and successor not in visited and successor not in checked:
            visited.add(successor)
            successor = predecessors[successor]
        if successor in visited:
            return EvidenceFinding(rule, ValidationStatus.FAILED, "cyclic_episode_lineage")
        checked.update(visited)
    return EvidenceFinding(rule, ValidationStatus.PASSED, "verified_explicit_history")


def _feature_availability(
    usage: tuple[UsageRecord, ...] | None,
    snapshots: tuple[SnapshotRecord, ...] | None,
    observation_at: datetime | None,
    cutoff: date,
) -> EvidenceFinding:
    rule = "feature_availability"
    if observation_at is None:
        return _not_evaluated(rule)
    if not _aware(observation_at) or observation_at.astimezone(UTC).date() > cutoff:
        return EvidenceFinding(rule, ValidationStatus.FAILED, "invalid_observation_cutoff")
    observation = observation_at.astimezone(UTC)
    if any(
        stamp.astimezone(UTC) > observation
        for row in snapshots or ()
        for stamp in (row.observed_at, row.occurred_at, row.effective_at, row.available_at)
    ) or any(
        datetime.combine(row.period_end, time.max, tzinfo=UTC) > observation
        or (row.available_at is not None and row.available_at.astimezone(UTC) > observation)
        for row in usage or ()
    ):
        return EvidenceFinding(rule, ValidationStatus.FAILED, "future_feature_evidence")
    if not (usage or snapshots) or any(row.available_at is None for row in usage or ()):
        return _not_evaluated(rule)
    return EvidenceFinding(rule, ValidationStatus.PASSED, "verified_supplied_availability")


_POLICY_FINDINGS = (
    EvidenceFinding(
        "canonical_identity",
        ValidationStatus.BLOCKED_BY_UNRESOLVED_POLICY,
        "policy_required",
        ("BDR-013", "DD-EP-003"),
    ),
    EvidenceFinding(
        "lifecycle_replay",
        ValidationStatus.BLOCKED_BY_UNRESOLVED_POLICY,
        "policy_required",
        ("BDR-014",),
    ),
    EvidenceFinding(
        "billing_schedule",
        ValidationStatus.BLOCKED_BY_UNRESOLVED_POLICY,
        "policy_required",
        ("BDR-012", "DD-EP-011"),
    ),
    EvidenceFinding(
        "monthly_temporal_conventions",
        ValidationStatus.BLOCKED_BY_UNRESOLVED_POLICY,
        "policy_required",
        ("BDR-010", "BDR-011", "BDR-015", "CGQ-020"),
    ),
    EvidenceFinding(
        "target_and_eligibility",
        ValidationStatus.BLOCKED_BY_UNRESOLVED_POLICY,
        "policy_required",
        ("CGQ-006", "CGQ-007", "CGQ-011", "CGQ-012", "CGQ-016"),
    ),
)


def validate_synthetic_evidence(
    customers: Iterable[CustomerRecord],
    episodes: Iterable[SubscriptionEpisode],
    *,
    cutoff: date,
    observation_at: datetime | None = None,
    usage: Iterable[UsageRecord] | None = None,
    snapshots: Iterable[SnapshotRecord] | None = None,
    invoices: Iterable[InvoiceFact] | None = None,
    outcomes: Iterable[OutcomeRecord] | None = None,
    episode_owners: Mapping[str, str] | None = None,
    event_owners: Mapping[str, str] | None = None,
    invoice_owners: Mapping[str, str] | None = None,
    reactivations: Iterable[ReactivationEvidence] = (),
) -> tuple[EvidenceFinding, ...]:
    """Evaluate declared facts independently, without inferring any absent policy.

    When observation_at is supplied, usage and snapshot rows are feature candidates
    for that observation. Outcome evidence has its own ascertainment boundary.
    """
    if type(cutoff) is not date:
        raise ValueError("Expected an explicit extraction cutoff date.")
    customers, episodes = tuple(customers), tuple(episodes)
    usage = tuple(usage) if usage is not None else None
    snapshots = tuple(snapshots) if snapshots is not None else None
    invoices = tuple(invoices) if invoices is not None else None
    outcomes = tuple(outcomes) if outcomes is not None else None

    ownership = (
        _evaluate(
            "episode_population",
            "invalid_episode_ownership_or_identity",
            lambda: build_episode_population(customers, episodes),
        )
        if episodes
        else _not_evaluated("episode_population")
    )
    findings = [ownership]
    if ownership.status is ValidationStatus.PASSED:
        by_id = {row.subscription_id: row for row in episodes}
        events = {
            row.establishment.event_id: row.subscription_id
            for row in episodes
            if row.establishment is not None
        }
        findings.append(
            _check_binding(
                "customer_episode_attribution",
                episode_owners,
                {row.subscription_id: row.customer_id for row in episodes},
            )
        )
        findings.append(_check_binding("event_attribution", event_owners, events))
        findings.append(_history(by_id, tuple(reactivations), cutoff))
        observed_events = [row.establishment for row in episodes if row.establishment is not None]
        event_rule = "establishment_chronology"
        future = any(row.start_date > cutoff for row in episodes) or any(
            stamp.astimezone(UTC).date() > cutoff
            for event in observed_events
            for stamp in (event.occurred_at, event.effective_at, event.recorded_at)
            if stamp is not None
        )
        if future:
            findings.append(
                EvidenceFinding(
                    event_rule, ValidationStatus.FAILED, "event_exceeds_extraction_cutoff"
                )
            )
        elif observed_events:
            findings.append(
                EvidenceFinding(
                    event_rule, ValidationStatus.PASSED, "verified_supplied_event_times"
                )
            )
        else:
            findings.append(_not_evaluated(event_rule))
    else:
        findings.extend(
            _not_evaluated(rule)
            for rule in (
                "customer_episode_attribution",
                "event_attribution",
                "historical_episode_separation",
                "establishment_chronology",
            )
        )

    for rule, rows, check in (
        ("usage_facts", usage, lambda: validate_usage(usage or (), episodes, cutoff=cutoff)),
        (
            "snapshot_facts",
            snapshots,
            lambda: validate_snapshots(snapshots or (), episodes, cutoff=cutoff),
        ),
        (
            "invoice_facts",
            invoices,
            lambda: validate_invoice_relationships(episodes, invoices or ()),
        ),
        ("outcome_facts", outcomes, lambda: validate_outcomes(outcomes or (), episodes)),
    ):
        findings.append(
            _evaluate(rule, "invalid_supplied_facts", check) if rows else _not_evaluated(rule)
        )
    fact_statuses = {result.rule: result.status for result in findings}
    invoices_valid = fact_statuses["invoice_facts"] is ValidationStatus.PASSED
    findings.append(
        _check_binding(
            "invoice_attribution",
            invoice_owners,
            {row.invoice_id: row.subscription_id for row in invoices or ()},
        )
        if invoices_valid
        else _not_evaluated("invoice_attribution")
    )
    observation_rules = {"usage_facts", "snapshot_facts"}
    invalid_observations = any(
        result.rule in observation_rules and result.status is ValidationStatus.FAILED
        for result in findings
    )
    findings.append(
        _not_evaluated("feature_availability")
        if invalid_observations
        else _feature_availability(usage, snapshots, observation_at, cutoff)
    )
    if fact_statuses["outcome_facts"] is ValidationStatus.PASSED:
        future_outcome = any(
            row.ascertainment_cutoff.astimezone(UTC).date() > cutoff for row in outcomes or ()
        )
        findings.append(
            EvidenceFinding(
                "outcome_extraction_cutoff",
                ValidationStatus.FAILED if future_outcome else ValidationStatus.PASSED,
                "outcome_exceeds_extraction_cutoff"
                if future_outcome
                else "verified_supplied_cutoff",
            )
        )
    else:
        findings.append(_not_evaluated("outcome_extraction_cutoff"))
    return (*findings, *_POLICY_FINDINGS)
