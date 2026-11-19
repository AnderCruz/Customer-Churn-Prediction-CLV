"""In-memory evidence and acceptance for local synthetic development exports."""

import csv
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from importlib.metadata import version
from io import StringIO
from pathlib import Path
from platform import python_version
from uuid import uuid4

from nowa_customer_intelligence.data.ingestion import DATASET_FILENAMES
from nowa_customer_intelligence.data.synthetic.development import (
    SCENARIO_VERSION,
    DevelopmentGenerationRequest,
    DevelopmentPopulation,
    DevelopmentScenario,
    generate_development_population,
)
from nowa_customer_intelligence.data.synthetic.projection import ProjectedDataset
from nowa_customer_intelligence.data.synthetic.random_streams import STREAM_ALGORITHM
from nowa_customer_intelligence.data.synthetic.run_context import SourceMetadata
from nowa_customer_intelligence.data.synthetic.semantic_validation import (
    EvidenceFinding,
)
from nowa_customer_intelligence.data.validation.models import RuleExecutionResult
from nowa_customer_intelligence.pipeline import (
    PipelineOverallStatus,
    PipelineWorkflow,
    StageExecutionStatus,
)

_SCHEMA_VERSION = "development-provenance-v1"
_SCOPE = "fictional_development"
_PIPELINE_STAGES = (
    "dataset_discovery",
    "header_inspection",
    "csv_ingestion",
    "type_normalization",
    "schema_validation",
    "referential_integrity",
    "data_quality",
)
_DQ_RULES = ("RI-001", "RI-002", "RI-003", "RI-004", "TC-001", "TC-002")
_SEMANTIC_RULES = (
    "episode_population",
    "customer_episode_attribution",
    "event_attribution",
    "invoice_facts",
    "invoice_attribution",
    "baseline_lifecycle",
    "baseline_billing",
)
_TEMPORAL_RULES = (
    "establishment_chronology",
    "usage_facts",
    "snapshot_facts",
    "feature_availability",
    "baseline_monthly_evidence",
)


class GateStatus(StrEnum):
    """Evaluation states for the development acceptance boundary."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    NOT_EVALUATED = "NOT_EVALUATED"
    BLOCKED_BY_UNRESOLVED_POLICY = "BLOCKED_BY_UNRESOLVED_POLICY"
    INAPPLICABLE = "INAPPLICABLE"


@dataclass(frozen=True, slots=True)
class GateFinding:
    """One scoped gate and whether it is required for acceptance."""

    gate: str
    status: GateStatus
    required: bool = True


@dataclass(frozen=True, slots=True)
class DatasetInventory:
    """Declared record count and pipeline evidence references for one dataset."""

    dataset: str
    records: int
    validation_refs: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DatasetIntegrity:
    """Actual file evidence with a fixed failure category when unavailable or invalid."""

    dataset: str
    present: bool
    records: int | None = None
    size_bytes: int | None = None
    sha256_hex: str | None = None
    validation_refs: tuple[str, ...] = ()
    problem: str | None = None


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    """Development evidence of exactly the expected CSV file inventory."""

    files: tuple[DatasetIntegrity, ...]
    unexpected_files: int
    directory_problem: str | None = None

    @property
    def passed(self) -> bool:
        """Only a complete report with actual clean file evidence passes."""
        return (
            self.directory_problem is None
            and self.unexpected_files == 0
            and bool(self.files)
            and all(
                row.present
                and row.records is not None
                and row.size_bytes is not None
                and row.sha256_hex is not None
                and row.problem is None
                for row in self.files
            )
        )


@dataclass(frozen=True, slots=True)
class PipelineEvidence:
    """Actual stage and finding statuses without client names or diagnostic payloads."""

    workflow: PipelineWorkflow
    reference: str
    overall: PipelineOverallStatus
    datasets: tuple[str, ...]
    stages: tuple[tuple[str, StageExecutionStatus], ...]
    rules: tuple[tuple[str, RuleExecutionResult], ...]


@dataclass(frozen=True, slots=True)
class GenerationParameters:
    """Allowlisted generation state. This record has no canonical fingerprint."""

    scenario_id: str
    scenario_version: int
    configuration_schema_version: int
    customer_count: int
    episode_bounds: tuple[int, int]
    history: tuple[str, str]
    observation_cutoff: datetime
    seed_reference: str
    scenario: DevelopmentScenario


@dataclass(frozen=True, slots=True)
class DevelopmentProvenance:
    """In-memory generation, validation and integrity evidence for one local run."""

    version: str
    run_id: str
    scope: str
    started_at: datetime
    completed_at: datetime
    parameters: GenerationParameters
    stream_algorithm: str
    policy_references: tuple[str, ...]
    source_revision: str | None
    dependencies: tuple[tuple[str, str], ...]
    registry_context: str
    registry_episode_count: int
    expected_inventory: tuple[str, ...]
    inventory: tuple[DatasetInventory, ...]
    pipeline: tuple[PipelineEvidence, ...]
    findings: tuple[EvidenceFinding, ...]
    integrity: IntegrityReport | None
    configuration_status: GateStatus
    generation_status: GateStatus
    certification: str = "NOT_CERTIFIED"
    publication: str = "OUTSIDE_SCOPE"


@dataclass(frozen=True, slots=True)
class ProvenancedDevelopment:
    """The original development output and its separate provenance."""

    population: DevelopmentPopulation
    provenance: DevelopmentProvenance


@dataclass(frozen=True, slots=True)
class DevelopmentAcceptance:
    """Evaluation of implemented evidence, restricted to fictional development."""

    gates: tuple[GateFinding, ...]

    @property
    def accepted(self) -> bool:
        """Require a pass for each required gate."""
        required = [gate for gate in self.gates if gate.required]
        return bool(required) and all(gate.status is GateStatus.PASSED for gate in required)


def _file_bytes(directory: Path, dataset: str) -> tuple[bytes | None, str | None]:
    path = directory / DATASET_FILENAMES[dataset]
    if path.is_symlink():
        return None, "unsupported_file"
    if not path.exists():
        return None, "missing_file"
    if not path.is_file():
        return None, "unsupported_file"
    try:
        return path.read_bytes(), None
    except OSError:
        return None, "unreadable_file"


def _record_rows(data: bytes) -> tuple[tuple[str, ...], ...]:
    return tuple(
        tuple(row) for row in csv.reader(StringIO(data.decode("utf-8"), newline=""), strict=True)
    )


def _directory_state(directory: Path, datasets: tuple[str, ...]) -> tuple[int, str | None]:
    names = {DATASET_FILENAMES[key] for key in datasets if key in DATASET_FILENAMES}
    if len(names) != len(datasets) or not names:
        return 0, "invalid_inventory"
    try:
        if not directory.is_dir() or directory.is_symlink():
            return 0, "invalid_directory"
        return sum(path.name not in names for path in directory.iterdir()), None
    except OSError:
        return 0, "unreadable_directory"


def capture_development_integrity(
    directory: Path,
    tables: Iterable[ProjectedDataset],
    *,
    inventory: tuple[DatasetInventory, ...] = (),
) -> IntegrityReport:
    """Capture actual bytes and verify each CSV against its projected rows."""
    tables = tuple(tables)
    datasets = tuple(table.dataset for table in tables)
    refs = {item.dataset: item.validation_refs for item in inventory}
    unexpected, problem = _directory_state(directory, datasets)
    if problem is not None:
        return IntegrityReport((), unexpected, problem)
    evidence = []
    for table in tables:
        data, problem = _file_bytes(directory, table.dataset)
        validation_refs = refs.get(table.dataset, ())
        if data is None:
            evidence.append(
                DatasetIntegrity(
                    table.dataset,
                    problem != "missing_file",
                    validation_refs=validation_refs,
                    problem=problem,
                )
            )
            continue
        try:
            rows = _record_rows(data)
        except (UnicodeError, csv.Error):
            rows = ()
            problem = "invalid_csv"
        if problem is None and (not rows or rows[0] != table.columns or rows[1:] != table.rows):
            problem = "projection_mismatch"
        evidence.append(
            DatasetIntegrity(
                table.dataset,
                True,
                max(0, len(rows) - 1),
                len(data),
                sha256(data).hexdigest(),
                validation_refs,
                problem,
            )
        )
    return IntegrityReport(tuple(evidence), unexpected)


def verify_development_integrity(directory: Path, recorded: IntegrityReport) -> IntegrityReport:
    """Recheck actual size, row count and checksum without writing or repairing files."""
    datasets = tuple(item.dataset for item in recorded.files)
    unexpected, directory_problem = _directory_state(directory, datasets)
    if directory_problem is not None:
        return IntegrityReport((), unexpected, directory_problem)
    evidence = []
    for item in recorded.files:
        data, problem = _file_bytes(directory, item.dataset)
        if data is None:
            evidence.append(
                DatasetIntegrity(
                    item.dataset,
                    problem != "missing_file",
                    validation_refs=item.validation_refs,
                    problem=problem,
                )
            )
            continue
        try:
            count = max(0, len(_record_rows(data)) - 1)
        except (UnicodeError, csv.Error):
            count = None
        observed = DatasetIntegrity(
            item.dataset, True, count, len(data), sha256(data).hexdigest(), item.validation_refs
        )
        problem = item.problem
        if problem is None:
            if observed.size_bytes != item.size_bytes:
                problem = "size_mismatch"
            elif observed.sha256_hex != item.sha256_hex:
                problem = "checksum_mismatch"
            elif observed.records != item.records:
                problem = "record_count_mismatch"
        evidence.append(replace(observed, problem=problem))
    return IntegrityReport(tuple(evidence), unexpected, recorded.directory_problem)


def _pipeline_evidence(population: DevelopmentPopulation) -> tuple[PipelineEvidence, ...]:
    workflow_ids = {
        f"development-validation-{workflow.value.lower()}": workflow
        for workflow in PipelineWorkflow
    }
    evidence = []
    for result in population.validation:
        summary = result.summary
        workflow = workflow_ids.get(summary.run_id)
        if workflow is None:
            continue
        evidence.append(
            PipelineEvidence(
                workflow,
                summary.run_id,
                summary.overall_status,
                tuple(key for key, present in summary.dataset_presence.items() if present),
                tuple(
                    (stage.stage_id, stage.status)
                    for stage in summary.stages
                    if stage.stage_id in _PIPELINE_STAGES
                ),
                tuple(
                    (row.rule_id, row.result)
                    for row in result.dq_report.findings
                    if row.rule_id in _DQ_RULES
                )
                if result.dq_report is not None
                else (),
            )
        )
    return tuple(evidence)


def run_development_with_provenance(
    request: DevelopmentGenerationRequest, *, source_metadata: SourceMetadata | None = None
) -> ProvenancedDevelopment:
    """Run the existing generator and retain allowlisted evidence in memory."""
    if source_metadata is not None and type(source_metadata) is not SourceMetadata:
        raise ValueError("Expected typed source revision metadata.")
    started_at = datetime.now(UTC)
    run_id = f"gen-{uuid4()}"
    before_validation = None

    def observe_export(directory: Path, tables: tuple[ProjectedDataset, ...]) -> None:
        nonlocal before_validation
        before_validation = capture_development_integrity(directory, tables)

    population = generate_development_population(
        request, observe_export=observe_export if request.export_directory is not None else None
    )
    pipeline = _pipeline_evidence(population)
    inventory = tuple(
        DatasetInventory(
            table.dataset,
            len(table.rows),
            tuple(
                evidence.reference for evidence in pipeline if table.dataset in evidence.datasets
            ),
        )
        for table in population.tables
    )
    integrity = None
    if request.export_directory is not None and population.exported_files:
        integrity = capture_development_integrity(request.export_directory, population.tables)
        if before_validation is None or before_validation != integrity:
            integrity = replace(integrity, directory_problem="validation_window_mismatch")
        refs = {row.dataset: row.validation_refs for row in inventory}
        integrity = replace(
            integrity,
            files=tuple(replace(row, validation_refs=refs[row.dataset]) for row in integrity.files),
        )
        exported = set(population.exported_files)
        expected = {request.export_directory / DATASET_FILENAMES[row.dataset] for row in inventory}
        if exported != expected or len(exported) != len(population.exported_files):
            integrity = replace(integrity, directory_problem="export_inventory_mismatch")
    effective = request.effective
    parameters = GenerationParameters(
        effective.scenario_id,
        effective.scenario_version,
        effective.config_schema_version,
        effective.population.customer_count,
        (effective.population.episode_count_min, effective.population.episode_count_max),
        (effective.history.start_date, effective.history.cutoff_date),
        request.observation_cutoff.astimezone(UTC),
        sha256(
            b"nowa.synthetic.seed-reference.v1\0" + effective.master_seed.to_bytes(8, "big")
        ).hexdigest(),
        request.scenario,
    )
    expected_inventory = tuple(
        key for key, name in DATASET_FILENAMES.items() if name in effective.requested_outputs
    )
    provenance = DevelopmentProvenance(
        _SCHEMA_VERSION,
        run_id,
        _SCOPE,
        started_at,
        datetime.now(UTC),
        parameters,
        STREAM_ALGORITHM,
        (
            SCENARIO_VERSION,
            f"contract-v{effective.policy_refs.contract_version}",
            f"business-model-v{effective.policy_refs.business_model_version}",
            "PD-006",
        ),
        source_metadata.revision if source_metadata is not None else None,
        (
            ("python", python_version()),
            *(
                (name, version(name))
                for name in ("numpy", "pandas", "pandera", "pydantic", "PyYAML")
            ),
        ),
        "caller_located_sqlite_recorded_uuid4_mapping",
        len(population.episodes),
        expected_inventory,
        inventory,
        pipeline,
        population.findings,
        integrity,
        GateStatus.PASSED,
        GateStatus.PASSED,
    )
    return ProvenancedDevelopment(population, provenance)


def _combine(statuses: Iterable[GateStatus]) -> GateStatus:
    checks = tuple(statuses)
    for status in (
        GateStatus.FAILED,
        GateStatus.BLOCKED_BY_UNRESOLVED_POLICY,
        GateStatus.NOT_EVALUATED,
        GateStatus.INAPPLICABLE,
    ):
        if status in checks:
            return status
    return GateStatus.PASSED if checks else GateStatus.NOT_EVALUATED


def _pipeline_gate(workflows: dict[PipelineWorkflow, PipelineEvidence], name: str) -> GateStatus:
    statuses = []
    for workflow in PipelineWorkflow:
        evidence = workflows.get(workflow)
        status = dict(evidence.stages).get(name) if evidence is not None else None
        if status is StageExecutionStatus.SUCCEEDED:
            statuses.append(GateStatus.PASSED)
        elif status in (
            StageExecutionStatus.FAILED,
            StageExecutionStatus.PARTIAL,
            StageExecutionStatus.BLOCKED,
        ):
            statuses.append(GateStatus.FAILED)
        elif status is StageExecutionStatus.NOT_APPLICABLE:
            statuses.append(GateStatus.INAPPLICABLE)
        else:
            statuses.append(GateStatus.NOT_EVALUATED)
    return _combine(statuses)


def _existing_data_quality(workflows: dict[PipelineWorkflow, PipelineEvidence]) -> GateStatus:
    states = []
    for workflow in PipelineWorkflow:
        evidence = workflows.get(workflow)
        rules = dict(evidence.rules) if evidence is not None else {}
        for name in _DQ_RULES:
            actual = rules.get(name)
            if actual is RuleExecutionResult.FAIL:
                states.append(GateStatus.FAILED)
            elif actual is RuleExecutionResult.PASS:
                states.append(GateStatus.PASSED)
            elif actual is RuleExecutionResult.NOT_APPLICABLE and (
                name in ("TC-001", "TC-002")
                or (name == "RI-002" and workflow is PipelineWorkflow.BASIC)
            ):
                states.append(GateStatus.PASSED)
            else:
                states.append(GateStatus.NOT_EVALUATED)
    return _combine(states)


def evaluate_development_acceptance(
    provenance: DevelopmentProvenance, *, directory: Path | None = None
) -> DevelopmentAcceptance:
    """Require current integrity, both pipeline workflows and scoped development evidence."""
    workflows = {row.workflow: row for row in provenance.pipeline}
    findings = {row.rule: GateStatus(row.status.value) for row in provenance.findings}
    defaults = GateStatus.NOT_EVALUATED
    required_inventory = set(DATASET_FILENAMES)

    def finding_status(names: tuple[str, ...]) -> GateStatus:
        return _combine(findings.get(name, defaults) for name in names)

    registry = findings.get("registry_reuse", defaults)
    if registry is GateStatus.PASSED and (
        provenance.registry_episode_count != provenance.parameters.scenario.episode_target
    ):
        registry = GateStatus.FAILED

    inventory = {row.dataset: row for row in provenance.inventory}
    inventory_ok = (
        set(provenance.expected_inventory) == required_inventory
        and len(provenance.expected_inventory) == len(required_inventory)
        and set(inventory) == required_inventory
        and len(inventory) == len(provenance.inventory)
        and all(row.records >= 0 for row in inventory.values())
        and all(
            inventory[key].records > 0
            for key in ("customers", "subscriptions", "subscription_snapshots")
        )
        and inventory["customers"].records == provenance.parameters.customer_count
        and inventory["subscriptions"].records == provenance.registry_episode_count
    )
    pipeline_status = defaults
    if len(workflows) != len(provenance.pipeline):
        pipeline_status = GateStatus.FAILED
    elif any(row.overall is not PipelineOverallStatus.SUCCEEDED for row in workflows.values()):
        pipeline_status = GateStatus.FAILED
    elif set(workflows) == set(PipelineWorkflow):
        pipeline_status = GateStatus.PASSED
        for workflow, evidence in workflows.items():
            expected = (
                required_inventory - {"subscription_snapshots"}
                if (workflow is PipelineWorkflow.BASIC)
                else required_inventory
            )
            if set(evidence.datasets) != expected:
                pipeline_status = GateStatus.FAILED

    if pipeline_status is GateStatus.PASSED:
        pipeline_status = _combine(_pipeline_gate(workflows, stage) for stage in _PIPELINE_STAGES)

    report = provenance.integrity
    integrity = defaults
    if report is not None:
        files = {row.dataset: row for row in report.files}
        if (
            report.directory_problem is not None
            or report.unexpected_files
            or any(not row.present or row.problem is not None for row in report.files)
        ):
            integrity = GateStatus.FAILED
        elif not report.passed or set(files) != required_inventory:
            integrity = defaults
        elif (
            len(files) != len(report.files)
            or not inventory_ok
            or any(
                file.records != inventory[key].records
                or file.validation_refs != inventory[key].validation_refs
                or inventory[key].validation_refs
                != tuple(row.reference for row in provenance.pipeline if key in row.datasets)
                for key, file in files.items()
            )
        ):
            integrity = GateStatus.FAILED
        elif directory is not None:
            integrity = (
                GateStatus.PASSED
                if verify_development_integrity(directory, report).passed
                else GateStatus.FAILED
            )

    reactivations_expected = provenance.parameters.scenario.episode_target > (
        provenance.parameters.customer_count
    )
    history = (
        findings.get("historical_episode_separation", defaults)
        if reactivations_expected
        else GateStatus.INAPPLICABLE
    )
    gates = (
        GateFinding("configuration", provenance.configuration_status),
        GateFinding("generation", provenance.generation_status),
        GateFinding("registry_consistency", registry),
        GateFinding(
            "dataset_inventory",
            GateStatus.PASSED if inventory_ok else GateStatus.FAILED if inventory else defaults,
        ),
        GateFinding("pipeline_workflows", pipeline_status),
        GateFinding("schema_validation", _pipeline_gate(workflows, "schema_validation")),
        GateFinding("referential_integrity", _pipeline_gate(workflows, "referential_integrity")),
        GateFinding(
            "existing_data_quality",
            _combine(
                (_pipeline_gate(workflows, "data_quality"), _existing_data_quality(workflows))
            ),
        ),
        GateFinding("supported_semantic_validation", finding_status(_SEMANTIC_RULES)),
        GateFinding("historical_episode_separation", history, reactivations_expected),
        GateFinding("supported_temporal_validation", finding_status(_TEMPORAL_RULES)),
        GateFinding("output_integrity", integrity),
        GateFinding(
            "development_scope",
            GateStatus.PASSED
            if (
                provenance.version == _SCHEMA_VERSION
                and provenance.scope == _SCOPE
                and provenance.certification == "NOT_CERTIFIED"
                and provenance.publication == "OUTSIDE_SCOPE"
            )
            else GateStatus.FAILED,
        ),
    )
    outside = tuple(
        GateFinding(row.rule, GateStatus(row.status.value), False)
        for row in provenance.findings
        if row.rule
        in (
            "canonical_identity",
            "lifecycle_replay",
            "billing_schedule",
            "monthly_temporal_conventions",
            "target_and_eligibility",
            "outcome_facts",
            "outcome_extraction_cutoff",
        )
    )
    return DevelopmentAcceptance(
        (*gates, *outside, GateFinding("publication_approval", GateStatus.INAPPLICABLE, False))
    )
