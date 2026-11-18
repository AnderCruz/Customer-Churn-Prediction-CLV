"""Create configuration-only run evidence for the synthetic generator."""

import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from graphlib import CycleError, TopologicalSorter
from platform import python_version
from re import fullmatch
from typing import Literal
from uuid import UUID, uuid4

from nowa_customer_intelligence.data.synthetic.configuration import (
    EffectiveConfiguration,
    required_filenames,
)


class RunContextError(ValueError):
    """The supplied run metadata or configuration is invalid."""


@dataclass(frozen=True, slots=True)
class SourceMetadata:
    """Caller-supplied source state, with None representing unknown values."""

    revision: str | None = None
    dirty: bool | None = None

    def __post_init__(self) -> None:
        if self.revision is not None and (
            type(self.revision) is not str or not fullmatch(r"[0-9a-fA-F]{7,64}", self.revision)
        ):
            raise RunContextError("Expected a hexadecimal source revision.")
        if self.dirty is not None and type(self.dirty) is not bool:
            raise RunContextError("Expected a Boolean dirty-state indicator.")


@dataclass(frozen=True, slots=True)
class GateDeclaration:
    """Applicability within the current scope, without an evaluation result."""

    gate_id: str
    applicability: Literal["required", "outside_scope"]


_GATES = (
    GateDeclaration("configuration_validation", "required"),
    GateDeclaration("context_preparation", "required"),
    GateDeclaration("generation", "outside_scope"),
    GateDeclaration("contract_schema", "outside_scope"),
    GateDeclaration("referential_integrity", "outside_scope"),
    GateDeclaration("semantic_attribution", "outside_scope"),
    GateDeclaration("temporal_validation", "outside_scope"),
    GateDeclaration("outcome_eligibility", "outside_scope"),
    GateDeclaration("publication_authorisation", "outside_scope"),
)


class StageId(StrEnum):
    """Stage identifiers available to the configuration-only caller."""

    CONFIGURATION_VALIDATION = "configuration_validation"
    CONTEXT_PREPARATION = "context_preparation"
    INVENTORY_REVIEW = "inventory_review"
    SCOPE_REVIEW = "scope_review"
    DIAGNOSTICS_PREPARATION = "diagnostics_preparation"


class StageStatus(StrEnum):
    """Generator-local status, independent of pipeline statuses."""

    NOT_RUN = "NOT_RUN"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class StageDiagnostic(StrEnum):
    """Fixed references that can safely appear in stage evidence."""

    EXECUTION_FAILED = "STAGE_EXECUTION_FAILED"
    DEPENDENCY_FAILED = "STAGE_DEPENDENCY_FAILED"


@dataclass(frozen=True, slots=True)
class StageOutcome:
    """Immutable outcome for a declared stage."""

    stage_id: StageId
    status: StageStatus = StageStatus.NOT_RUN
    dependencies: tuple[StageId, ...] = ()
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    diagnostic: StageDiagnostic | None = None
    blocked_by: StageId | None = None


@dataclass(frozen=True, slots=True)
class RunContext:
    """Immutable in-memory provenance and scope for a configuration-only attempt."""

    run_id: str
    started_at_utc: datetime
    effective_configuration: EffectiveConfiguration
    python_version: str
    source_metadata: SourceMetadata
    required_inputs: tuple[str, ...]
    gates: tuple[GateDeclaration, ...]
    stage_outcomes: tuple[StageOutcome, ...] = ()

    @property
    def planned_inventory(self) -> tuple[str, ...]:
        """Return the declared filenames for future output."""
        return self.effective_configuration.requested_outputs

    @property
    def generated_inventory(self) -> tuple[str, ...]:
        """A configuration-only attempt has no generated files."""
        return ()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise RunContextError("Expected a timezone-aware execution timestamp.")
    return value.astimezone(UTC)


def create_run_context(
    effective: EffectiveConfiguration,
    *,
    clock: Callable[[], datetime] = _utc_now,
    run_id_factory: Callable[[], UUID] = uuid4,
    source_metadata: SourceMetadata | None = None,
) -> RunContext:
    """Create a configuration-only context from a fully resolved configuration."""
    if type(effective) is not EffectiveConfiguration:
        raise RunContextError("Expected a resolved effective configuration.")
    if source_metadata is None:
        source_metadata = SourceMetadata()
    elif type(source_metadata) is not SourceMetadata:
        raise RunContextError("Expected typed source metadata.")
    started_at = _as_utc(clock())
    identifier = run_id_factory()
    if type(identifier) is not UUID or identifier.version != 4:
        raise RunContextError("Expected a UUID4 run identifier.")
    return RunContext(
        run_id=f"gen-{identifier}",
        started_at_utc=started_at,
        effective_configuration=effective,
        python_version=python_version(),
        source_metadata=source_metadata,
        required_inputs=required_filenames(effective.workflow),
        gates=_GATES,
        stage_outcomes=(
            StageOutcome(StageId.CONFIGURATION_VALIDATION, StageStatus.SUCCEEDED),
            StageOutcome(
                StageId.CONTEXT_PREPARATION,
                StageStatus.SUCCEEDED,
                dependencies=(StageId.CONFIGURATION_VALIDATION,),
                started_at_utc=started_at,
            ),
        ),
    )


_DEFAULT_STAGES = {
    StageId.INVENTORY_REVIEW: (StageId.CONTEXT_PREPARATION,),
    StageId.SCOPE_REVIEW: (StageId.INVENTORY_REVIEW,),
    StageId.DIAGNOSTICS_PREPARATION: (StageId.CONTEXT_PREPARATION,),
}
_LOGGER = logging.getLogger(__name__)


class StageTransitionError(ValueError):
    """A stage plan or requested transition is invalid."""


class StageExecutionError(RuntimeError):
    """A stage failed, with a safe code and immutable outcome evidence."""

    def __init__(self, stage_id: StageId, outcomes: tuple[StageOutcome, ...]) -> None:
        self.code = StageDiagnostic.EXECUTION_FAILED
        self.stage_id = stage_id
        self.outcomes = outcomes
        super().__init__(f"{self.code}: The generator stage failed.")


class StageTracker:
    """Record transitions for one run. The caller controls execution order."""

    def __init__(
        self,
        context: RunContext,
        *,
        stages: Mapping[StageId, tuple[StageId, ...]] | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._context = context
        self._clock = clock
        self._records = {record.stage_id: record for record in context.stage_outcomes}
        declared = _DEFAULT_STAGES if stages is None else stages
        all_ids = self._records.keys() | declared.keys()
        for stage_id, dependencies in declared.items():
            if type(stage_id) is not StageId or stage_id in self._records:
                raise StageTransitionError("Invalid or already recorded stage identifier.")
            if type(dependencies) is not tuple or any(
                type(item) is not StageId or item not in all_ids for item in dependencies
            ):
                raise StageTransitionError("Invalid stage dependency.")
            if len(set(dependencies)) != len(dependencies):
                raise StageTransitionError("Duplicate stage dependency.")
        try:
            order = tuple(TopologicalSorter(declared).static_order())
        except CycleError:
            cycle = True
        else:
            cycle = False
        if cycle:
            raise StageTransitionError("Stage dependencies contain a cycle.")
        for stage_id in order:
            if stage_id in declared:
                self._records[stage_id] = StageOutcome(stage_id, dependencies=declared[stage_id])
        self._block_dependants()

    def snapshot(self) -> RunContext:
        """Return immutable run metadata and current stage evidence."""
        return replace(self._context, stage_outcomes=tuple(self._records.values()))

    def _expect(self, stage_id: StageId, expected: StageStatus) -> StageOutcome:
        if type(stage_id) is not StageId or stage_id not in self._records:
            raise StageTransitionError("Unknown stage identifier.")
        record = self._records[stage_id]
        if record.status is not expected:
            raise StageTransitionError("Invalid stage transition.")
        return record

    def _record(self, outcome: StageOutcome, event: str, level: int) -> None:
        self._records[outcome.stage_id] = outcome
        if (
            level == logging.INFO
            and self._context.effective_configuration.diagnostics.level != "INFO"
        ):
            return
        _LOGGER.log(
            level,
            event,
            extra={
                "generator_run_id": self._context.run_id,
                "generator_stage_id": outcome.stage_id.value,
                "generator_stage_status": outcome.status.value,
                "generator_diagnostic_code": outcome.diagnostic,
            },
        )

    def start(self, stage_id: StageId, *, at: datetime | None = None) -> None:
        """Start a declared stage after its prerequisites succeed."""
        record = self._expect(stage_id, StageStatus.NOT_RUN)
        dependencies = tuple(self._records[item] for item in record.dependencies)
        if any(item.status is not StageStatus.SUCCEEDED for item in dependencies):
            raise StageTransitionError("Stage prerequisites have not succeeded.")
        started_at = _as_utc(self._clock() if at is None else at)
        if started_at < self._context.started_at_utc or any(
            item.completed_at_utc is not None and started_at < item.completed_at_utc
            for item in dependencies
        ):
            raise StageTransitionError("Stage starts before its run or prerequisite completed.")
        self._record(
            replace(record, status=StageStatus.RUNNING, started_at_utc=started_at),
            "generator_stage_started",
            logging.INFO,
        )

    def _complete(
        self, stage_id: StageId, status: StageStatus, at: datetime | None
    ) -> StageOutcome:
        record = self._expect(stage_id, StageStatus.RUNNING)
        completed_at = _as_utc(self._clock() if at is None else at)
        if record.started_at_utc is None or completed_at < record.started_at_utc:
            raise StageTransitionError("Stage completion precedes its start.")
        return replace(record, status=status, completed_at_utc=completed_at)

    def succeed(self, stage_id: StageId, *, at: datetime | None = None) -> None:
        """Record a successfully completed stage."""
        self._record(
            self._complete(stage_id, StageStatus.SUCCEEDED, at),
            "generator_stage_succeeded",
            logging.INFO,
        )

    def _block_dependants(self) -> None:
        # Records are in dependency order, so each block can propagate in one pass.
        for record in tuple(self._records.values()):
            if record.status is not StageStatus.NOT_RUN:
                continue
            for dependency in record.dependencies:
                if self._records[dependency].status in (StageStatus.FAILED, StageStatus.BLOCKED):
                    self._record(
                        replace(
                            record,
                            status=StageStatus.BLOCKED,
                            diagnostic=StageDiagnostic.DEPENDENCY_FAILED,
                            blocked_by=dependency,
                        ),
                        "generator_stage_blocked",
                        logging.WARNING,
                    )
                    break

    def fail(self, stage_id: StageId, *, at: datetime | None = None) -> StageExecutionError:
        """Record failure and return a safe exception for the controlling caller to raise."""
        outcome = self._complete(stage_id, StageStatus.FAILED, at)
        return self._record_failure(outcome)

    def _record_failure(self, outcome: StageOutcome) -> StageExecutionError:
        self._record(
            replace(outcome, diagnostic=StageDiagnostic.EXECUTION_FAILED),
            "generator_stage_failed",
            logging.WARNING,
        )
        self._block_dependants()
        return StageExecutionError(outcome.stage_id, self.snapshot().stage_outcomes)

    def run_stage[T](self, stage_id: StageId, operation: Callable[[], T]) -> T:
        """Run one caller-selected operation and propagate a sanitised stage failure."""
        self.start(stage_id)
        try:
            result = operation()
        except Exception:
            failed = True
        else:
            failed = False
        if failed:
            try:
                outcome = self._complete(stage_id, StageStatus.FAILED, None)
            except Exception:
                # Keep the operation failure visible if the clock cannot supply an end time.
                record = self._expect(stage_id, StageStatus.RUNNING)
                outcome = replace(record, status=StageStatus.FAILED)
            raise self._record_failure(outcome)
        self.succeed(stage_id)
        return result
