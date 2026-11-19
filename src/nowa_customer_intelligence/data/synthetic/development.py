"""Run the Fieldwise Cloud synthetic development baseline without changing WP-01 scope."""

from calendar import monthrange
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from nowa_customer_intelligence.data.ingestion import DATASET_FILENAMES
from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    InvoiceStatus,
    PlanChange,
    ScheduledCharge,
    billing_anniversary,
    calculate_catalogue_charge,
    schedule_episode_billing,
)
from nowa_customer_intelligence.data.synthetic.configuration import EffectiveConfiguration
from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord, generate_customers
from nowa_customer_intelligence.data.synthetic.identity_registry import EpisodeIdentityRegistry
from nowa_customer_intelligence.data.synthetic.lifecycle import (
    GeneratedEpisode,
    LifecycleFact,
    LifecycleKind,
    generate_episodes,
    validate_lifecycle,
)
from nowa_customer_intelligence.data.synthetic.observations import (
    SnapshotRecord,
    UsageAssumptions,
    UsageRecord,
    generate_episode_observations,
)
from nowa_customer_intelligence.data.synthetic.projection import (
    ProjectedDataset,
    export_development_csvs,
    project_development_population,
)
from nowa_customer_intelligence.data.synthetic.random_streams import create_random_stream
from nowa_customer_intelligence.data.synthetic.semantic_validation import (
    EvidenceFinding,
    ReactivationEvidence,
    ValidationStatus,
    validate_synthetic_evidence,
)
from nowa_customer_intelligence.pipeline import (
    PipelineExecutionRequest,
    PipelineOrchestrationResult,
    PipelineWorkflow,
    execute_pipeline,
)

SCENARIO_VERSION = "fieldwise-development-v1"


class DevelopmentGenerationError(ValueError):
    """The requested development run exceeds the supported fictional scenario."""


@dataclass(frozen=True, slots=True)
class DevelopmentScenario:
    """Explicit generation assumptions for the Fieldwise fictional baseline."""

    episode_target: int
    plan_id: str
    annual_percent: int
    subsequent_payment: InvoiceStatus
    usage: UsageAssumptions
    plan_change: PlanChange | None = None
    activation_evidence_lag_days: int = 0

    def __post_init__(self) -> None:
        calculate_catalogue_charge(self.plan_id, BillingFrequency.MONTHLY)
        if type(self.episode_target) is not int or self.episode_target < 1:
            raise DevelopmentGenerationError("Expected a positive episode target.")
        if type(self.annual_percent) is not int or not 0 <= self.annual_percent <= 100:
            raise DevelopmentGenerationError("Expected an annual billing percentage from 0 to 100.")
        if type(self.subsequent_payment) is not InvoiceStatus or self.subsequent_payment not in (
            InvoiceStatus.PAID,
            InvoiceStatus.PENDING,
            InvoiceStatus.FAILED,
        ):
            raise DevelopmentGenerationError("Expected an explicit supported payment state.")
        if type(self.usage) is not UsageAssumptions:
            raise DevelopmentGenerationError("Expected explicit fictional usage assumptions.")
        if (
            type(self.activation_evidence_lag_days) is not int
            or self.activation_evidence_lag_days < 0
        ):
            raise DevelopmentGenerationError("Expected a non-negative activation evidence lag.")
        if self.plan_change is not None:
            if (
                type(self.plan_change) is not PlanChange
                or type(self.plan_change.requested_on) is not date
            ):
                raise DevelopmentGenerationError("Expected a dated plan change.")
            calculate_catalogue_charge(self.plan_change.plan_id, BillingFrequency.MONTHLY)


@dataclass(frozen=True, slots=True)
class DevelopmentGenerationRequest:
    """Explicitly authorise a local development generation and optional fixture export."""

    effective: EffectiveConfiguration
    scenario: DevelopmentScenario
    registry_path: Path
    client: str
    source_namespace: str
    observation_cutoff: datetime
    export_directory: Path | None = None
    validation_workflows: tuple[PipelineWorkflow, ...] = (
        PipelineWorkflow.BASIC,
        PipelineWorkflow.TEMPORAL,
    )

    def __post_init__(self) -> None:
        if (
            type(self.effective) is not EffectiveConfiguration
            or type(self.scenario) is not DevelopmentScenario
        ):
            raise DevelopmentGenerationError(
                "Expected effective configuration and a typed scenario."
            )
        if set(self.effective.requested_outputs) != set(DATASET_FILENAMES.values()):
            raise DevelopmentGenerationError("The development baseline requires all five datasets.")
        history_start = date.fromisoformat(self.effective.history.start_date)
        extraction = date.fromisoformat(self.effective.history.cutoff_date)
        if (
            type(self.observation_cutoff) is not datetime
            or self.observation_cutoff.utcoffset() is None
            or not history_start <= self.observation_cutoff.astimezone(UTC).date() <= extraction
        ):
            raise DevelopmentGenerationError(
                "The observation cutoff is outside configured history."
            )
        if (
            type(self.validation_workflows) is not tuple
            or any(type(value) is not PipelineWorkflow for value in self.validation_workflows)
            or len(set(self.validation_workflows)) != len(self.validation_workflows)
        ):
            raise DevelopmentGenerationError("Expected distinct pipeline validation workflows.")
        if (
            any(
                type(value) is not str or not value or value != value.strip()
                for value in (self.client, self.source_namespace)
            )
            or len(self.client) > 256
            or len(self.source_namespace) + len(SCENARIO_VERSION) >= 256
        ):
            raise DevelopmentGenerationError(
                "Expected explicit bounded development identity scopes."
            )
        if not isinstance(self.registry_path, Path):
            raise DevelopmentGenerationError("Expected an explicit registry path.")
        if self.export_directory is not None and (
            not isinstance(self.export_directory, Path)
            or not self.export_directory.is_dir()
            or self.export_directory.is_symlink()
            or any(self.export_directory.iterdir())
            or self.registry_path.resolve().is_relative_to(self.export_directory.resolve())
        ):
            raise DevelopmentGenerationError(
                "Expected an empty development export separate from the registry."
            )


@dataclass(frozen=True, slots=True)
class DevelopmentPopulation:
    """Development records, internal evidence and actual downstream results."""

    customers: tuple[CustomerRecord, ...]
    episodes: tuple[GeneratedEpisode, ...]
    charges: tuple[ScheduledCharge, ...]
    usage: tuple[UsageRecord, ...]
    snapshots: tuple[SnapshotRecord, ...]
    tables: tuple[ProjectedDataset, ...]
    findings: tuple[EvidenceFinding, ...]
    validation: tuple[PipelineOrchestrationResult, ...]
    exported_files: tuple[Path, ...]
    elapsed_seconds: float


def _bill_episode(
    request: DevelopmentGenerationRequest, row: GeneratedEpisode, cutoff: date
) -> tuple[GeneratedEpisode, tuple[ScheduledCharge, ...]]:
    scenario = request.scenario
    stream = create_random_stream(
        request.effective.master_seed,
        "billing.frequency",
        namespace=f"episode-{row.identity.source_key}",
    )
    frequency = (
        BillingFrequency.ANNUAL
        if int(stream.integers(0, 100)) < scenario.annual_percent
        else BillingFrequency.MONTHLY
    )
    change = scenario.plan_change
    changes = ()
    if (
        change is not None
        and row.paid_activation <= change.requested_on <= cutoff
        and (row.episode.end_date is None or change.requested_on < row.episode.end_date)
    ):
        changes = (change,)
    charges = schedule_episode_billing(
        row.episode,
        paid_activation=row.paid_activation,
        cutoff=cutoff,
        plan_id=scenario.plan_id,
        frequency=frequency,
        subsequent_payment=scenario.subsequent_payment,
        plan_changes=changes,
    )
    last = charges[-1]
    commercial = replace(
        row.episode,
        plan_id=last.plan_id,
        billing_frequency=frequency.value,
        recurring_revenue=last.recurring_revenue,
        currency="GBP",
    )
    renewals = []
    for charge in charges[1:]:
        # The fictional scenario explicitly continues service at each agreed boundary.
        # Payment status is independent of that renewal.
        at = datetime.combine(charge.invoice.invoice_date, time.min, tzinfo=UTC)
        renewals.append(
            LifecycleFact(row.episode.subscription_id, LifecycleKind.RENEWED, at, at, at)
        )
    facts = tuple(
        sorted(
            (*row.facts, *renewals),
            key=lambda fact: fact.effective_at,
        )
    )
    return replace(row, episode=commercial, facts=facts), charges


def _validate_charges(
    row: GeneratedEpisode, charges: tuple[ScheduledCharge, ...], cutoff: date
) -> None:
    renewal_days = [
        fact.effective_at.date() for fact in row.facts if fact.kind is LifecycleKind.RENEWED
    ]
    if (
        not charges
        or charges[0].invoice.invoice_date != row.paid_activation
        or renewal_days != [charge.invoice.invoice_date for charge in charges[1:]]
    ):
        raise DevelopmentGenerationError(
            "Charge boundaries contradict activation or renewal facts."
        )
    for index, charge in enumerate(charges):
        invoice = charge.invoice
        expected = calculate_catalogue_charge(charge.plan_id, charge.frequency)
        boundary = billing_anniversary(row.paid_activation, index, charges[0].frequency)
        next_boundary = billing_anniversary(row.paid_activation, index + 1, charges[0].frequency)
        if row.episode.end_date is not None:
            next_boundary = min(next_boundary, row.episode.end_date)
        if (
            invoice.subscription_id != row.episode.subscription_id
            or charge.frequency is not charges[0].frequency
            or invoice.invoice_date != boundary
            or charge.period_end != next_boundary
            or charge.payment_event.occurred_at.date() != boundary
            or charge.payment_event.effective_at.date() != boundary
            or charge.payment_event.available_at < charge.payment_event.occurred_at
            or (
                invoice.invoice_status is InvoiceStatus.PAID
                and invoice.paid_date != invoice.invoice_date
            )
            or (invoice.invoice_status is not InvoiceStatus.PAID and invoice.paid_date is not None)
            or not row.paid_activation <= invoice.invoice_date <= cutoff
            or invoice.invoice_date >= charge.period_end
            or (row.episode.end_date is not None and charge.period_end > row.episode.end_date)
            or invoice.amount != expected.invoice_amount
            or charge.recurring_revenue != expected.recurring_revenue
            or invoice.currency != expected.currency
            or charge.payment_event.invoice_id != invoice.invoice_id
            or charge.payment_event.status is not invoice.invoice_status
            or (index and charges[index - 1].period_end != invoice.invoice_date)
        ):
            raise DevelopmentGenerationError("Invalid explicit billing or payment facts.")


def _validate_monthly_evidence(
    row: GeneratedEpisode,
    usage: tuple[UsageRecord, ...],
    snapshots: tuple[SnapshotRecord, ...],
    observation: datetime,
) -> None:
    end = row.episode.end_date
    if any(
        fact.period_start != fact.usage_month
        or fact.period_start.day != 1
        or (fact.period_start.year, fact.period_start.month)
        != (fact.period_end.year, fact.period_end.month)
        or fact.period_end.day != monthrange(fact.period_end.year, fact.period_end.month)[1]
        or fact.period_start < row.paid_activation
        or (end is not None and fact.period_end >= end)
        or fact.available_at is None
        or fact.available_at > observation
        for fact in usage
    ):
        raise DevelopmentGenerationError("Usage contradicts the completed calendar-month baseline.")
    if any(
        fact.snapshot_date.day != monthrange(fact.snapshot_date.year, fact.snapshot_date.month)[1]
        or fact.observed_at.astimezone(UTC).time() != time.max
        or fact.observed_at > observation
        or (end is not None and fact.snapshot_date >= end)
        for fact in snapshots
    ):
        raise DevelopmentGenerationError("A snapshot contradicts the UTC month-end baseline.")


def _export_and_validate(
    request: DevelopmentGenerationRequest,
    tables: tuple[ProjectedDataset, ...],
    observe_export: Callable[[Path, tuple[ProjectedDataset, ...]], None] | None,
) -> tuple[tuple[Path, ...], tuple[PipelineOrchestrationResult, ...]]:
    if request.export_directory is None and not request.validation_workflows:
        return (), ()

    def execute(
        directory: Path,
    ) -> tuple[tuple[Path, ...], tuple[PipelineOrchestrationResult, ...]]:
        sources = export_development_csvs(directory, tables)
        if observe_export is not None:
            observe_export(directory, tables)
        results = []
        for workflow in request.validation_workflows:
            inputs = {
                key: value
                for key, value in sources.items()
                if workflow is PipelineWorkflow.TEMPORAL or key != "subscription_snapshots"
            }
            results.append(
                execute_pipeline(
                    PipelineExecutionRequest(
                        run_id=f"development-validation-{workflow.value.lower()}",
                        client_scope=request.client,
                        workflow=workflow,
                        dataset_sources=inputs,
                        execution_intent="validate synthetic development fixtures",
                    )
                )
            )
        return tuple(sources.values()), tuple(results)

    if request.export_directory is not None:
        return execute(request.export_directory)
    with TemporaryDirectory(prefix="fieldwise-validation-") as directory:
        _, results = execute(Path(directory))
        return (), results


def generate_development_population(
    request: DevelopmentGenerationRequest,
    *,
    observe_export: Callable[[Path, tuple[ProjectedDataset, ...]], None] | None = None,
) -> DevelopmentPopulation:
    """Run the explicitly requested development scenario and preserve its evidence."""
    if type(request) is not DevelopmentGenerationRequest:
        raise DevelopmentGenerationError("Expected an explicitly authorised development request.")
    started = perf_counter()
    effective, scenario = request.effective, request.scenario
    cutoff = date.fromisoformat(effective.history.cutoff_date)
    customers = generate_customers(effective)
    registry = EpisodeIdentityRegistry(request.registry_path)
    generated = generate_episodes(
        effective,
        customers,
        registry,
        client=request.client,
        namespace=f"{SCENARIO_VERSION}:{request.source_namespace}",
        target=scenario.episode_target,
        activation_evidence_lag_days=scenario.activation_evidence_lag_days,
    )
    validate_lifecycle(generated, cutoff=cutoff)
    episodes, all_charges, all_usage, all_snapshots = [], [], [], []
    invoice_owners = {}
    for planned in generated:
        row, charges = _bill_episode(request, planned, cutoff)
        _validate_charges(row, charges, cutoff)
        usage, snapshots = generate_episode_observations(
            row.episode,
            charges,
            row.facts[1].available_at,
            observation_cutoff=request.observation_cutoff,
            assumptions=scenario.usage,
            stream=create_random_stream(
                effective.master_seed,
                "usage.monthly",
                namespace=f"episode-{row.identity.source_key}",
            ),
        )
        _validate_monthly_evidence(row, usage, snapshots, request.observation_cutoff)
        episodes.append(row)
        all_charges.extend(charges)
        invoice_owners.update(
            (charge.invoice.invoice_id, row.episode.subscription_id) for charge in charges
        )
        all_usage.extend(usage)
        all_snapshots.extend(snapshots)

    generated = tuple(episodes)
    validate_lifecycle(generated, cutoff=cutoff)
    registry.verify_many((row.identity, row.episode.subscription_id) for row in generated)
    masters = tuple(row.episode for row in generated)
    invoices = tuple(charge.invoice for charge in all_charges)
    by_id = {row.episode.subscription_id: row for row in generated}
    reactivations = tuple(
        ReactivationEvidence(
            row.prior_subscription_id,
            row.episode.subscription_id,
            datetime.combine(
                by_id[row.prior_subscription_id].episode.end_date, time.min, tzinfo=UTC
            ),
            row.facts[0].occurred_at,
        )
        for row in generated
        if row.prior_subscription_id is not None
    )
    findings = validate_synthetic_evidence(
        customers,
        masters,
        cutoff=cutoff,
        observation_at=request.observation_cutoff,
        usage=all_usage,
        snapshots=all_snapshots,
        invoices=invoices,
        event_owners={
            row.identity.establishment_ref: row.episode.subscription_id for row in generated
        },
        episode_owners={row.episode.subscription_id: row.episode.customer_id for row in generated},
        invoice_owners=invoice_owners,
        reactivations=reactivations,
    )
    if any(finding.status is ValidationStatus.FAILED for finding in findings):
        raise DevelopmentGenerationError("Synthetic semantic or temporal evidence failed.")
    # These findings are scoped to the explicitly authorised development baseline.
    findings += tuple(
        EvidenceFinding(name, ValidationStatus.PASSED, "verified_development_baseline")
        for name in (
            "registry_reuse",
            "baseline_lifecycle",
            "baseline_billing",
            "baseline_monthly_evidence",
        )
    )
    tables = project_development_population(
        effective, customers, masters, snapshots=all_snapshots, usage=all_usage, invoices=invoices
    )
    files, results = _export_and_validate(request, tables, observe_export)
    return DevelopmentPopulation(
        customers,
        generated,
        tuple(all_charges),
        tuple(all_usage),
        tuple(all_snapshots),
        tables,
        findings,
        results,
        files,
        perf_counter() - started,
    )
