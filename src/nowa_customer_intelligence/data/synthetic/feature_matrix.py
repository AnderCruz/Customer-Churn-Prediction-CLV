"""Versioned Fieldwise feature rows and as-known extraction for Phase 05."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256
from json import dumps
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import NamedTuple

from .billing import (
    BillingFrequency,
    BillingValidationError,
    ScheduledCharge,
    calculate_catalogue_charge,
)
from .churn_experiment import (
    ChurnExperiment,
    ExperimentEvidenceError,
    ExperimentObservation,
    IneligibilityReason,
    OutcomeClassification,
    utc_instant,
)
from .historical_features import (
    _completed_months,
    _month_end,
    build_historical_features,
)
from .lifecycle import GeneratedEpisode, LifecycleFact, LifecycleKind
from .modelling_dataset import (
    ObservationCandidate,
    SimulationFollowUp,
    build_modelling_dataset,
)
from .observations import SnapshotRecord, UsageRecord
from .provenance import (
    DatasetIntegrity,
    GenerationParameters,
    ProvenancedDevelopment,
    evaluate_development_acceptance,
)

FEATURE_SPEC_VERSION = "fieldwise-episode-features-v1"
FEATURE_BUNDLE_VERSION = 2


class FeatureSpec(NamedTuple):
    """Individual feature definition. Shared rules are documented per evidence group."""

    name: str
    category: str
    dtype: type
    nullable: bool
    calculation: str
    signed: bool = False


FEATURE_SPECS = (
    FeatureSpec("episode_age_days", "episode", int, False, "Whole UTC days since establishment."),
    FeatureSpec(
        "prior_completed_episodes",
        "customer_history",
        int,
        False,
        "Earlier episodes with established and terminated facts known by observation.",
    ),
    FeatureSpec("plan_id", "commercial", str, False, "Latest usable snapshot plan."),
    FeatureSpec("billing_frequency", "commercial", str, False, "Latest usable snapshot cadence."),
    FeatureSpec(
        "monthly_recurring_gbp",
        "commercial",
        Decimal,
        False,
        "Latest usable snapshot monthly-normalised GBP.",
    ),
    FeatureSpec(
        "issued_invoice_count", "billing", int, False, "Count of available issued charges."
    ),
    FeatureSpec(
        "issued_amount_gbp",
        "billing",
        Decimal,
        True,
        "Sum of available issued amounts, missing if none.",
    ),
    FeatureSpec(
        "mean_invoice_gbp",
        "billing",
        Decimal,
        True,
        "Mean available issued amount rounded to pennies, missing if none.",
    ),
    FeatureSpec(
        "days_since_last_invoice",
        "billing",
        int,
        True,
        "Whole UTC days since latest available issue date, missing if none.",
    ),
    FeatureSpec("expected_usage_months", "coverage", int, False, "Whole UTC months in scope."),
    FeatureSpec("observed_usage_months", "coverage", int, False, "In-scope available usage rows."),
    FeatureSpec(
        "unobserved_usage_months", "coverage", int, False, "Expected minus observed months."
    ),
    FeatureSpec(
        "usage_coverage_ratio",
        "coverage",
        float,
        True,
        "Observed divided by expected, missing for zero expected months.",
    ),
    FeatureSpec(
        "active_user_months", "coverage", int, False, "Available months with an active-user value."
    ),
    FeatureSpec(
        "zero_active_user_months", "usage", int, False, "Observed months with zero active users."
    ),
    FeatureSpec(
        "latest_active_users", "usage", int, True, "Latest available row's active-user count."
    ),
    FeatureSpec("mean_active_users", "usage", float, True, "Mean over known active-user values."),
    FeatureSpec("max_active_users", "usage", int, True, "Maximum known active-user count."),
    FeatureSpec("latest_sessions", "usage", int, True, "Latest available row's session count."),
    FeatureSpec("mean_sessions", "usage", float, True, "Mean over known session values."),
    FeatureSpec("latest_events", "usage", int, True, "Latest available row's event count."),
    FeatureSpec("mean_events", "usage", float, True, "Mean over known event values."),
    FeatureSpec(
        "active_users_change",
        "trend",
        int,
        True,
        "Difference across the latest two available consecutive months.",
        True,
    ),
    FeatureSpec(
        "sessions_change",
        "trend",
        int,
        True,
        "Difference across the latest two available consecutive months.",
        True,
    ),
    FeatureSpec(
        "events_change",
        "trend",
        int,
        True,
        "Difference across the latest two available consecutive months.",
        True,
    ),
)

Predictor = int | float | Decimal | str | None


@dataclass(frozen=True, slots=True)
class ObservationKey:
    subscription_id: str
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class FeatureObservation:
    key: ObservationKey
    customer_id: str
    latest_evidence_at: datetime


@dataclass(frozen=True, slots=True)
class PredictionEligibility:
    key: ObservationKey
    exclusion: IneligibilityReason | None


class PredictionIneligible(ExperimentEvidenceError):
    """An as-known risk-set exclusion, distinct from invalid source evidence."""

    def __init__(self, reason: IneligibilityReason) -> None:
        self.reason = reason
        super().__init__(reason.value)


@dataclass(frozen=True, slots=True)
class OutcomeRow:
    key: ObservationKey
    ascertainment_cutoff: datetime
    horizon_end: datetime
    outcome: OutcomeClassification
    retrospective_training_eligible: bool


@dataclass(frozen=True, slots=True)
class FeatureRunConfiguration:
    experiment: ChurnExperiment
    simulation_follow_up: SimulationFollowUp | None
    generation: GenerationParameters
    source_revision: str | None
    dependencies: tuple[tuple[str, str], ...]
    stream_algorithm: str


@dataclass(frozen=True, slots=True)
class FeatureMatrix:
    """Ordered, aligned identities and predictors plus all candidate outcomes."""

    observations: tuple[FeatureObservation, ...]
    predictors: tuple[tuple[Predictor, ...], ...]
    eligibility: tuple[PredictionEligibility, ...]
    outcomes: tuple[OutcomeRow, ...] | None
    inputs: tuple[DatasetIntegrity, ...]
    evidence_sha256: str
    configuration: FeatureRunConfiguration


def _known_at(fact: LifecycleFact) -> datetime:
    return max(map(utc_instant, (fact.occurred_at, fact.effective_at, fact.available_at)))


def _available_invoices(
    charges: Iterable[ScheduledCharge], start: datetime, observed: datetime
) -> list[tuple[datetime, datetime, Decimal]]:
    available = []
    keys = set()
    for charge in charges:
        invoice, evidence = charge.invoice, charge.payment_event
        issued = datetime.combine(invoice.invoice_date, time.min, UTC)
        if not start <= issued <= observed:
            continue
        attested = max(
            map(
                utc_instant,
                (
                    evidence.occurred_at,
                    evidence.effective_at,
                    evidence.available_at,
                ),
            )
        )
        if attested > observed:
            continue
        if (
            evidence.invoice_id != invoice.invoice_id
            or evidence.occurred_at < issued
            or invoice.invoice_id in keys
        ):
            raise ExperimentEvidenceError("Invalid available invoice attribution.")
        keys.add(invoice.invoice_id)
        available.append((issued, attested, invoice.amount))
    return available


def _available_usage(
    rows: Iterable[UsageRecord], expected: set[date], observed: datetime
) -> list[UsageRecord]:
    available: dict[date, UsageRecord] = {}
    for row in rows:
        if row.period_start not in expected or row.available_at is None:
            continue
        if utc_instant(row.available_at) > observed:
            continue
        if row.period_end != _month_end(row.period_start):
            continue
        if (
            row.usage_month != row.period_start
            or row.period_start in available
            or utc_instant(row.available_at) < datetime.combine(row.period_end, time.max, UTC)
        ):
            raise ExperimentEvidenceError("Invalid available usage evidence.")
        available[row.period_start] = row
    return [available[month] for month in sorted(available)]


def _usage_predictors(rows: list[UsageRecord], expected: set[date]) -> tuple[Predictor, ...]:
    active = [row.active_users for row in rows if row.active_users is not None]
    sessions = [row.sessions_count for row in rows if row.sessions_count is not None]
    events = [row.events_count for row in rows if row.events_count is not None]
    latest = rows[-1] if rows else None
    changes: list[int | None] = [None, None, None]
    if len(rows) >= 2 and rows[-2].period_end + timedelta(days=1) == rows[-1].period_start:
        for index, field in enumerate(("active_users", "sessions_count", "events_count")):
            old, new = getattr(rows[-2], field), getattr(rows[-1], field)
            if old is not None and new is not None:
                changes[index] = new - old
    return (
        len(expected),
        len(rows),
        len(expected) - len(rows),
        len(rows) / len(expected) if expected else None,
        len(active),
        active.count(0),
        latest.active_users if latest else None,
        float(mean(active)) if active else None,
        max(active) if active else None,
        latest.sessions_count if latest else None,
        float(mean(sessions)) if sessions else None,
        latest.events_count if latest else None,
        float(mean(events)) if events else None,
        *changes,
    )


def extract_feature_row(
    episode: GeneratedEpisode,
    observation: ExperimentObservation,
    experiment: ChurnExperiment,
    *,
    history_start: date,
    snapshots: tuple[SnapshotRecord, ...],
    usage: tuple[UsageRecord, ...],
    billing: tuple[ScheduledCharge, ...],
    customer_episodes: tuple[GeneratedEpisode, ...] = (),
) -> tuple[FeatureObservation, tuple[Predictor, ...]]:
    """Extract only available evidence, independently of the adjudicated outcome."""
    observed = utc_instant(observation.observed_at)
    observation = ExperimentObservation(observed, observed)
    start, _, _, _ = observation.bounds(experiment)
    identifier = episode.episode.subscription_id
    owner = episode.episode.customer_id
    baseline = build_historical_features(
        identifier,
        observation,
        experiment,
        history_start=history_start,
        lifecycle=episode.facts,
        snapshots=snapshots,
        usage=(),
        billing=(),
    )
    if baseline.exclusion is not None:
        raise PredictionIneligible(baseline.exclusion)
    if baseline.latest_evidence_at is None:
        raise ExperimentEvidenceError("Eligible historical state has no evidence timestamp.")
    if any(
        fact.kind is LifecycleKind.TERMINATED and _known_at(fact) <= observed
        for fact in episode.facts
    ):
        raise PredictionIneligible(IneligibilityReason.NOT_ACTIVE)
    if any(row.subscription_id != identifier for row in usage) or any(
        row.invoice.subscription_id != identifier for row in billing
    ):
        raise ExperimentEvidenceError("Historical facts belong to a different episode.")
    starts = [
        fact
        for fact in episode.facts
        if fact.kind is LifecycleKind.ESTABLISHED and _known_at(fact) <= observed
    ]
    if not starts:
        raise PredictionIneligible(IneligibilityReason.MISSING_HISTORICAL_STATE)
    if len(starts) != 1:
        raise ExperimentEvidenceError("Expected one available establishment fact.")
    established = utc_instant(starts[0].effective_at)
    activation = next(
        fact
        for fact in episode.facts
        if fact.kind is LifecycleKind.ACTIVATED and _known_at(fact) <= observed
    )
    evidence = [baseline.latest_evidence_at, _known_at(starts[0]), _known_at(activation)]
    prior = set()
    for other in customer_episodes:
        if other.episode.customer_id != owner:
            raise ExperimentEvidenceError("Customer history has inconsistent ownership.")
        other_id = other.episode.subscription_id
        if other_id == identifier:
            continue
        opening = [
            fact
            for fact in other.facts
            if fact.kind is LifecycleKind.ESTABLISHED
            and _known_at(fact) <= observed
            and utc_instant(fact.effective_at) < established
        ]
        completion = [
            fact
            for fact in other.facts
            if fact.kind is LifecycleKind.TERMINATED
            and _known_at(fact) <= observed
            and utc_instant(fact.effective_at) <= established
        ]
        if opening and completion:
            prior.add(other_id)
            evidence.extend(map(_known_at, (*opening, *completion)))
    expected = _completed_months(max(start, utc_instant(activation.effective_at)), observed)
    available_usage = _available_usage(usage, expected, observed)
    available_invoices = _available_invoices(billing, start, observed)
    evidence.extend(
        utc_instant(row.available_at) for row in available_usage if row.available_at is not None
    )
    evidence.extend(at for _, at, _ in available_invoices)
    amounts = [amount for _, _, amount in available_invoices]
    total = sum(amounts, Decimal(0)) if amounts else None
    last = max((issued for issued, _, _ in available_invoices), default=None)
    return FeatureObservation(ObservationKey(identifier, observed), owner, max(evidence)), (
        (observed - established).days,
        len(prior),
        baseline.predictors.plan_id,
        baseline.predictors.billing_frequency,
        baseline.predictors.recurring_revenue,
        len(amounts),
        total,
        (total / len(amounts)).quantize(Decimal("0.01")) if total is not None else None,
        (observed - last).days if last is not None else None,
        *_usage_predictors(available_usage, expected),
    )


def build_feature_matrix(
    run: ProvenancedDevelopment,
    directory: Path,
    experiment: ChurnExperiment,
    candidates: Iterable[ObservationCandidate],
    *,
    simulation_follow_up: SimulationFollowUp | None = None,
    include_outcomes: bool = True,
) -> FeatureMatrix:
    """Build an as-known prediction roster, with optional retrospective adjudication."""
    if not evaluate_development_acceptance(run.provenance, directory=directory).accepted:
        raise ExperimentEvidenceError(
            "The development population lacks current acceptance evidence."
        )
    if not include_outcomes and simulation_follow_up is not None:
        raise ExperimentEvidenceError("Inference-only builds cannot take outcome follow-up.")
    candidates = tuple(
        sorted(
            candidates, key=lambda row: (utc_instant(row.window.observed_at), row.subscription_id)
        )
    )
    population = run.population
    episodes = {row.episode.subscription_id: row for row in population.episodes}
    customers = defaultdict(list)
    snapshots = defaultdict(list)
    usage = defaultdict(list)
    billing = defaultdict(list)
    for row in population.episodes:
        customers[row.episode.customer_id].append(row)
    for row in population.snapshots:
        snapshots[row.subscription_id].append(row)
    for row in population.usage:
        usage[row.subscription_id].append(row)
    for charge in population.charges:
        billing[charge.invoice.subscription_id].append(charge)
    history_start = date.fromisoformat(run.provenance.parameters.history[0])
    observations, predictors, eligibility = [], [], []
    seen = set()
    for candidate in candidates:
        identifier = candidate.subscription_id
        observed = utc_instant(candidate.window.observed_at)
        key = ObservationKey(identifier, observed)
        dedup_key = (identifier.lower(), observed)
        if dedup_key in seen:
            raise ExperimentEvidenceError("Duplicate modelling observation.")
        seen.add(dedup_key)
        if observed > utc_instant(run.provenance.parameters.observation_cutoff):
            raise ExperimentEvidenceError("Observation exceeds the generated feature boundary.")
        episode = episodes.get(identifier)
        if episode is None:
            eligibility.append(PredictionEligibility(key, IneligibilityReason.INVALID_IDENTITY))
            continue
        if candidate.excluded:
            eligibility.append(PredictionEligibility(key, IneligibilityReason.EXPLICIT_EXCLUSION))
            continue
        try:
            identity, values = extract_feature_row(
                episode,
                ExperimentObservation(observed, observed),
                experiment,
                history_start=history_start,
                snapshots=tuple(snapshots[identifier]),
                usage=tuple(usage[identifier]),
                billing=tuple(billing[identifier]),
                customer_episodes=tuple(customers[episode.episode.customer_id]),
            )
        except PredictionIneligible as exc:
            eligibility.append(PredictionEligibility(key, exc.reason))
        else:
            eligibility.append(PredictionEligibility(key, None))
            observations.append(identity)
            predictors.append(values)

    outcomes = None
    if include_outcomes:
        data = build_modelling_dataset(
            run, directory, experiment, candidates, simulation_follow_up=simulation_follow_up
        )
        prediction_keys = {row.key for row in observations}
        outcomes = tuple(
            OutcomeRow(
                key,
                row.ascertainment_cutoff,
                row.horizon_end,
                row.outcome,
                key in prediction_keys and row.outcome.binary_target is not None,
            )
            for row in sorted(
                (*data.labelled, *data.pending, *data.right_censored, *data.ineligible),
                key=lambda row: (row.observed_at, row.subscription_id),
            )
            for key in (ObservationKey(row.subscription_id, row.observed_at),)
        )
    integrity = run.provenance.integrity
    if integrity is None:
        raise ExperimentEvidenceError("Verified source integrity is missing.")
    digest = sha256()
    for group in (population.episodes, population.snapshots, population.usage, population.charges):
        for fact in group:
            digest.update(dumps(asdict(fact), sort_keys=True, default=str).encode())
            digest.update(b"\n")
    provenance = run.provenance
    return FeatureMatrix(
        tuple(observations),
        tuple(predictors),
        tuple(eligibility),
        outcomes,
        integrity.files,
        digest.hexdigest(),
        FeatureRunConfiguration(
            experiment,
            simulation_follow_up,
            provenance.parameters,
            provenance.source_revision,
            provenance.dependencies,
            provenance.stream_algorithm,
        ),
    )


def assess_feature_quality(matrix: FeatureMatrix) -> dict:
    """Fail closed on broken alignment or schema and report observed distributions."""
    keys = [row.key for row in matrix.observations]
    candidate_keys = [row.key for row in matrix.eligibility]
    eligible = [row.key for row in matrix.eligibility if row.exclusion is None]
    eligible_keys = set(eligible)
    if (
        len(keys) != len(matrix.predictors)
        or len(set(candidate_keys)) != len(candidate_keys)
        or keys != eligible
        or candidate_keys
        != sorted(candidate_keys, key=lambda key: (key.observed_at, key.subscription_id))
        or matrix.outcomes is not None
        and (
            [row.key for row in matrix.outcomes] != candidate_keys
            or any(
                row.retrospective_training_eligible
                != (row.key in eligible_keys and row.outcome.binary_target is not None)
                for row in matrix.outcomes
            )
        )
        or any(row.latest_evidence_at > row.key.observed_at for row in matrix.observations)
        or any(len(row) != len(FEATURE_SPECS) for row in matrix.predictors)
    ):
        raise ExperimentEvidenceError("Feature matrix integrity or observation alignment failed.")
    inventory = {}
    for index, spec in enumerate(FEATURE_SPECS):
        values = [row[index] for row in matrix.predictors if row[index] is not None]
        missing = len(keys) - len(values)
        if missing and not spec.nullable:
            raise ExperimentEvidenceError(f"Unexpected missing feature: {spec.name}.")
        for value in values:
            if (
                type(value) is not spec.dtype
                or isinstance(value, (float, Decimal))
                and not isfinite(value)
                or isinstance(value, (int, float, Decimal))
                and not spec.signed
                and value < 0
                or spec.name == "usage_coverage_ratio"
                and value > 1
                or spec.name == "billing_frequency"
                and value not in tuple(BillingFrequency)
            ):
                raise ExperimentEvidenceError(f"Invalid feature value: {spec.name}.")
        summary = (
            dict(min=min(values), max=max(values), mean=mean(values))
            if values and spec.dtype is not str
            else dict(Counter(values))
        )
        inventory[spec.name] = {
            "category": spec.category,
            "dtype": spec.dtype.__name__,
            "missing": missing,
            "present": len(values),
            "missing_pct": 100 * missing / len(keys) if keys else None,
            "status": "passed",
            "distribution": summary,
        }
    names = tuple(spec.name for spec in FEATURE_SPECS)
    for row in matrix.predictors:
        values = dict(zip(names, row, strict=True))

        try:
            recurring = calculate_catalogue_charge(
                values["plan_id"], BillingFrequency(values["billing_frequency"])
            ).recurring_revenue
        except (BillingValidationError, ValueError):
            raise ExperimentEvidenceError("Unsupported historical catalogue state.") from None
        expected, observed = values["expected_usage_months"], values["observed_usage_months"]
        invoices = values["issued_invoice_count"]
        amount = values["issued_amount_gbp"]
        average = values["mean_invoice_gbp"]
        recency = values["days_since_last_invoice"]
        if (
            not 0 <= values["zero_active_user_months"] <= values["active_user_months"] <= observed
            or not observed <= expected
            or values["unobserved_usage_months"] != expected - observed
            or values["usage_coverage_ratio"] != (observed / expected if expected else None)
            or values["monthly_recurring_gbp"] != recurring
            or (invoices == 0) != (amount is None)
            or (invoices == 0) != (average is None)
            or (invoices == 0) != (recency is None)
        ):
            raise ExperimentEvidenceError("Feature relationships are inconsistent.")
    return {
        "rows": len(keys),
        "input_observations": len(candidate_keys),
        "features": len(FEATURE_SPECS),
        "duplicate_keys": 0,
        "invalid_values": 0,
        "prediction_exclusions": dict(
            Counter(row.exclusion.value for row in matrix.eligibility if row.exclusion is not None)
        ),
        "outcomes": (
            dict(Counter(row.outcome.state.value for row in matrix.outcomes))
            if matrix.outcomes is not None
            else None
        ),
        "retrospective_training_rows": (
            sum(row.retrospective_training_eligible for row in matrix.outcomes)
            if matrix.outcomes is not None
            else None
        ),
        "first_observation": keys[0].observed_at if keys else None,
        "last_observation": keys[-1].observed_at if keys else None,
        "inventory": inventory,
    }
