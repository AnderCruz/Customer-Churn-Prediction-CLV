"""Assemble and split the in-memory fictional subscription churn dataset."""

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

from nowa_customer_intelligence.data.synthetic.billing import ScheduledCharge
from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    POLICY_ID,
    POLICY_VERSION,
    ChurnExperiment,
    ExperimentEvidenceError,
    ExperimentObservation,
    FollowUpEvidence,
    IneligibilityReason,
    OutcomeClassification,
    TerminationEvidence,
    classify_outcome,
    utc_instant,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import OutcomeState
from nowa_customer_intelligence.data.synthetic.historical_features import (
    HistoricalFeatureResult,
    build_historical_features,
)
from nowa_customer_intelligence.data.synthetic.lifecycle import (
    GeneratedEpisode,
    LifecycleKind,
    validate_lifecycle,
)
from nowa_customer_intelligence.data.synthetic.observations import SnapshotRecord, UsageRecord
from nowa_customer_intelligence.data.synthetic.provenance import (
    ProvenancedDevelopment,
    evaluate_development_acceptance,
)


@dataclass(frozen=True, slots=True)
class ObservationCandidate:
    """An explicit subscription-level observation and adjudication cutoff."""

    subscription_id: str
    window: ExperimentObservation
    excluded: bool = False

    def __post_init__(self) -> None:
        if type(self.subscription_id) is not str or type(self.excluded) is not bool:
            raise ExperimentEvidenceError("Expected a typed observation identity and exclusion.")
        if type(self.window) is not ExperimentObservation:
            raise ExperimentEvidenceError("Expected explicit observation cutoffs.")


@dataclass(frozen=True, slots=True)
class SimulationFollowUp:
    """Explicit attestation that the fictional event ledger is exhaustively recorded.

    The caller supplies the authoritative coverage boundary and recording lag.
    Mere presence of records through the extraction date does not attest coverage.
    """

    source_ref: str
    complete_through: datetime
    recording_lag_days: int = 0

    def __post_init__(self) -> None:
        utc_instant(self.complete_through)
        if type(self.source_ref) is not str or not self.source_ref.strip():
            raise ExperimentEvidenceError("Expected an explicit simulation coverage reference.")
        if type(self.recording_lag_days) is not int or self.recording_lag_days < 0:
            raise ExperimentEvidenceError("Expected a non-negative follow-up recording lag.")

    def evidence_for(
        self, subscription_id: str, observation: ExperimentObservation, experiment: ChurnExperiment
    ) -> FollowUpEvidence | None:
        """Construct coverage only through a point known by this observation's cutoff."""
        _, t, horizon, a = observation.bounds(experiment)
        if self.recording_lag_days > (a - t).days:
            return None
        lag = timedelta(days=self.recording_lag_days)
        through = min(utc_instant(self.complete_through), horizon, a - lag)
        if through < t:
            return None
        return FollowUpEvidence(subscription_id, self.source_ref, through, through + lag)


@dataclass(frozen=True, slots=True)
class ModellingObservation:
    """An internal observation with separate predictor and target evidence."""

    subscription_id: str
    customer_id: str | None
    observed_at: datetime
    ascertainment_cutoff: datetime
    horizon_end: datetime
    features: HistoricalFeatureResult | None
    outcome: OutcomeClassification
    policy_id: str = POLICY_ID
    policy_version: int = POLICY_VERSION


@dataclass(frozen=True, slots=True)
class ModellingDataset:
    """Deterministically ordered outputs for each eligibility class."""

    labelled: tuple[ModellingObservation, ...]
    right_censored: tuple[ModellingObservation, ...]
    pending: tuple[ModellingObservation, ...]
    ineligible: tuple[ModellingObservation, ...]

    @property
    def counts(self) -> dict[str, int]:
        """Count each outcome state without discarding exclusions."""
        counts = Counter(row.outcome.state.value for row in self.labelled)
        return {
            OutcomeState.CONFIRMED_POSITIVE.value: counts[OutcomeState.CONFIRMED_POSITIVE.value],
            OutcomeState.CONFIRMED_NEGATIVE.value: counts[OutcomeState.CONFIRMED_NEGATIVE.value],
            OutcomeState.RIGHT_CENSORED.value: len(self.right_censored),
            OutcomeState.PENDING_ASCERTAINMENT.value: len(self.pending),
            OutcomeState.INELIGIBLE.value: len(self.ineligible),
        }

    @property
    def reasons(self) -> dict[str, int]:
        """Count unresolved and excluded observations by structured reason."""
        return dict(
            sorted(
                Counter(
                    row.outcome.reason
                    for row in (*self.right_censored, *self.pending, *self.ineligible)
                ).items()
            )
        )


def _termination_facts(row: GeneratedEpisode) -> tuple[TerminationEvidence, ...]:
    identifier = row.episode.subscription_id
    return tuple(
        TerminationEvidence(
            identifier,
            f"simulated-termination:{row.identity.source_key}",
            fact.occurred_at,
            fact.effective_at,
            fact.available_at,
            max(fact.occurred_at, fact.effective_at, fact.available_at),
            True,
        )
        for fact in row.facts
        if fact.kind is LifecycleKind.TERMINATED
    )


def build_modelling_dataset(
    run: ProvenancedDevelopment,
    directory: Path,
    experiment: ChurnExperiment,
    candidates: Iterable[ObservationCandidate],
    *,
    simulation_follow_up: SimulationFollowUp | None = None,
) -> ModellingDataset:
    """Build internal observations from a currently verified fictional export."""
    if not evaluate_development_acceptance(run.provenance, directory=directory).accepted:
        raise ExperimentEvidenceError(
            "The development population lacks current acceptance evidence."
        )
    history_start, extracted_day = map(date.fromisoformat, run.provenance.parameters.history)
    extraction = utc_instant(experiment.extraction_cutoff)
    if (
        not datetime.combine(history_start, time.min, UTC)
        <= extraction
        <= datetime.combine(extracted_day, time.max, UTC)
    ):
        raise ExperimentEvidenceError("The experiment exceeds the generated extraction boundary.")
    if (
        simulation_follow_up is not None
        and utc_instant(simulation_follow_up.complete_through) > extraction
    ):
        raise ExperimentEvidenceError("Simulation follow-up exceeds the experiment extraction.")

    population = run.population
    validate_lifecycle(population.episodes, cutoff=extracted_day)
    episodes = {row.episode.subscription_id: row for row in population.episodes}
    usage: dict[str, list[UsageRecord]] = defaultdict(list)
    snapshots: dict[str, list[SnapshotRecord]] = defaultdict(list)
    billing: dict[str, list[ScheduledCharge]] = defaultdict(list)
    for row in population.usage:
        usage[row.subscription_id].append(row)
    for row in population.snapshots:
        snapshots[row.subscription_id].append(row)
    for charge in population.charges:
        billing[charge.invoice.subscription_id].append(charge)
    terminations = {identifier: _termination_facts(row) for identifier, row in episodes.items()}

    keys: set[tuple[str, datetime]] = set()
    outcomes: dict[OutcomeState, list[ModellingObservation]] = defaultdict(list)
    for candidate in candidates:
        _, t, horizon, a = candidate.window.bounds(experiment)
        if t > run.provenance.parameters.observation_cutoff:
            raise ExperimentEvidenceError("Observation exceeds the generated feature boundary.")
        identifier = candidate.subscription_id
        key = (identifier.lower(), t)
        if key in keys:
            raise ExperimentEvidenceError("Duplicate modelling observation.")
        keys.add(key)
        source = episodes.get(identifier)
        features = None
        follow_up = None
        if source is None:
            exclusion = IneligibilityReason.INVALID_IDENTITY
        elif candidate.excluded:
            exclusion = IneligibilityReason.EXPLICIT_EXCLUSION
        else:
            features = build_historical_features(
                identifier,
                candidate.window,
                experiment,
                history_start=history_start,
                lifecycle=source.facts,
                snapshots=tuple(snapshots[identifier]),
                usage=tuple(usage[identifier]),
                billing=tuple(billing[identifier]),
            )
            exclusion = features.exclusion
            if simulation_follow_up is not None:
                follow_up = simulation_follow_up.evidence_for(
                    identifier, candidate.window, experiment
                )
        outcome = classify_outcome(
            identifier,
            candidate.window,
            experiment,
            terminations=terminations.get(identifier, ()),
            follow_up=follow_up,
            exclusion=exclusion,
        )
        outcomes[outcome.state].append(
            ModellingObservation(
                identifier,
                source.episode.customer_id if source else None,
                t,
                a,
                horizon,
                features,
                outcome,
            )
        )

    def ordered(rows: Iterable[ModellingObservation]) -> tuple[ModellingObservation, ...]:
        return tuple(sorted(rows, key=lambda row: (row.observed_at, row.subscription_id)))

    return ModellingDataset(
        ordered(
            (*outcomes[OutcomeState.CONFIRMED_POSITIVE], *outcomes[OutcomeState.CONFIRMED_NEGATIVE])
        ),
        ordered(outcomes[OutcomeState.RIGHT_CENSORED]),
        ordered(outcomes[OutcomeState.PENDING_ASCERTAINMENT]),
        ordered(outcomes[OutcomeState.INELIGIBLE]),
    )


@dataclass(frozen=True, slots=True)
class SplitBoundaries:
    """Exclusive right boundaries for forward partitions."""

    training_end: datetime
    validation_end: datetime
    test_end: datetime
    customer_disjoint: bool = False

    def __post_init__(self) -> None:
        if not (
            utc_instant(self.training_end)
            < utc_instant(self.validation_end)
            < utc_instant(self.test_end)
        ):
            raise ExperimentEvidenceError("Split boundaries must be strictly chronological.")
        if type(self.customer_disjoint) is not bool:
            raise ExperimentEvidenceError("Expected an explicit grouping mode.")


@dataclass(frozen=True, slots=True)
class SplitExclusion:
    """A labelled observation excluded from a modelling partition."""

    observation: ModellingObservation
    reason: str


@dataclass(frozen=True, slots=True)
class ModellingSplit:
    """Forward partitions and all labelled rows excluded by split rules."""

    training: tuple[ModellingObservation, ...]
    validation: tuple[ModellingObservation, ...]
    test: tuple[ModellingObservation, ...]
    excluded: tuple[SplitExclusion, ...]


def split_modelling_dataset(
    dataset: ModellingDataset, boundaries: SplitBoundaries
) -> ModellingSplit:
    """Assign groups to their earliest mature partition and record conflicts."""
    limits = tuple(
        utc_instant(value)
        for value in (
            boundaries.training_end,
            boundaries.validation_end,
            boundaries.test_end,
        )
    )
    groups: dict[str, int] = {}
    partitions: list[list[ModellingObservation]] = [[], [], []]
    excluded = []
    for row in sorted(dataset.labelled, key=lambda item: (item.observed_at, item.subscription_id)):
        if (
            row.outcome.binary_target is None
            or row.features is None
            or row.customer_id is None
            or row.features.exclusion is not None
        ):
            raise ExperimentEvidenceError(
                "The labelled split input contains an ineligible observation."
            )
        observed = utc_instant(row.observed_at)
        horizon = utc_instant(row.horizon_end)
        ascertainment = utc_instant(row.ascertainment_cutoff)
        if horizon <= observed or ascertainment < observed:
            raise ExperimentEvidenceError("A labelled observation has contradictory time bounds.")
        latest = row.features.latest_evidence_at
        if latest is None or utc_instant(latest) > observed:
            raise ExperimentEvidenceError(
                "The labelled split input contains future or missing evidence."
            )
        partition = next((index for index, limit in enumerate(limits) if observed < limit), None)
        if partition is None:
            excluded.append(SplitExclusion(row, "outside_split_window"))
            continue
        limit = limits[partition]
        if horizon >= limit:
            excluded.append(SplitExclusion(row, "outcome_horizon_crosses_boundary"))
            continue
        if ascertainment >= limit:
            excluded.append(SplitExclusion(row, "ascertainment_crosses_boundary"))
            continue
        key = row.customer_id if boundaries.customer_disjoint else row.subscription_id.lower()
        if groups.setdefault(key, partition) != partition:
            excluded.append(SplitExclusion(row, "group_assigned_to_earlier_partition"))
            continue
        partitions[partition].append(row)
    return ModellingSplit(*(tuple(rows) for rows in partitions), tuple(excluded))
