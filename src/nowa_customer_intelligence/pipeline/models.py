"""Immutable data models for Pipeline Execution Summaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType

from nowa_customer_intelligence.data.validation.models import DataQualityReport


class StageExecutionStatus(Enum):
    """Execution outcome reported by one pipeline stage."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class PipelineOverallStatus(Enum):
    """Overall pipeline execution outcome supplied by an aggregation component."""

    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class StageRequirement(Enum):
    """Requirement classification for a stage in a declared workflow."""

    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class PipelineWorkflow(Enum):
    """Explicit workflow selected by the caller for a pipeline execution."""

    BASIC = "BASIC"
    TEMPORAL = "TEMPORAL"


def _require_string(value: object, field_name: str, *, non_whitespace: bool = False) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if non_whitespace and not value.strip():
        raise ValueError(f"{field_name} must contain a non-whitespace character")


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be a {enum_type.__name__}")


def _normalize_utc(value: object, field_name: str, *, optional: bool = False) -> datetime | None:
    if value is None and optional:
        return None
    if not isinstance(value, datetime):
        suffix = " or None" if optional else ""
        raise TypeError(f"{field_name} must be a timezone-aware datetime{suffix}")

    try:
        if value.utcoffset() is None:
            raise ValueError(f"{field_name} must be a timezone-aware datetime")
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a valid timezone-aware datetime") from exc


def _require_count(value: object, field_name: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise ValueError(f"{field_name} must be a non-negative integer or None")


def _immutable_stages(values: object) -> tuple[StageExecutionResult, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("stages must be a sequence of StageExecutionResult values")

    copied = tuple(values)
    if any(type(stage) is not StageExecutionResult for stage in copied):
        raise TypeError("stages must contain only StageExecutionResult values")
    return copied


def _immutable_dataset_results(values: object) -> tuple[DatasetStageResult, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError("dataset_results must be a sequence of DatasetStageResult values")

    copied = tuple(values)
    if any(type(result) is not DatasetStageResult for result in copied):
        raise TypeError("dataset_results must contain only DatasetStageResult values")
    dataset_names = [result.dataset for result in copied]
    if len(dataset_names) != len(set(dataset_names)):
        raise ValueError("dataset names must be unique within a stage result")
    return copied


def _immutable_dataset_presence(values: object) -> Mapping[str, bool]:
    if not isinstance(values, Mapping):
        raise TypeError("dataset_presence must be a mapping")

    copied = dict(values)
    for key, value in copied.items():
        _require_string(key, "dataset_presence key")
        if not isinstance(value, bool):
            raise TypeError("dataset_presence values must be booleans")
    return MappingProxyType(copied)


def _immutable_dataset_sources(values: object) -> Mapping[str, str | Path]:
    if not isinstance(values, Mapping):
        raise TypeError("dataset_sources must be a mapping of dataset names to file paths")

    copied = dict(values)
    for dataset, source in copied.items():
        _require_string(dataset, "dataset_sources key", non_whitespace=True)
        if isinstance(source, str):
            _require_string(source, f"dataset_sources[{dataset!r}]", non_whitespace=True)
        elif not isinstance(source, Path):
            raise TypeError("dataset_sources values must be strings or pathlib.Path values")
    return MappingProxyType(copied)


@dataclass(frozen=True)
class DatasetStageResult:
    """Immutable outcome and safe counts for one dataset processed by a stage."""

    dataset: str
    status: StageExecutionStatus
    requirement: StageRequirement
    records_received: int | None = None
    records_processed: int | None = None
    records_rejected: int | None = None
    error_code: str | None = None
    message: str | None = None

    def __post_init__(self) -> None:
        _require_string(self.dataset, "dataset", non_whitespace=True)
        _require_enum(self.status, StageExecutionStatus, "status")
        _require_enum(self.requirement, StageRequirement, "requirement")

        for field_name in ("records_received", "records_processed", "records_rejected"):
            _require_count(getattr(self, field_name), field_name)

        if (self.requirement is StageRequirement.NOT_APPLICABLE) != (
            self.status is StageExecutionStatus.NOT_APPLICABLE
        ):
            raise ValueError("requirement and status must both be NOT_APPLICABLE or neither may be")

        for field_name in ("error_code", "message"):
            value = getattr(self, field_name)
            if value is not None:
                _require_string(value, field_name)


@dataclass(frozen=True)
class StageExecutionResult:
    """Immutable outcome and metadata reported by one consolidated pipeline stage.

    ``dataset_results`` defaults to an empty tuple for existing callers. Dataset-processing
    stages in the orchestrator must populate it for every dataset they process.
    """

    stage_id: str
    status: StageExecutionStatus
    requirement: StageRequirement
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    records_received: int | None = None
    records_processed: int | None = None
    records_rejected: int | None = None
    error_code: str | None = None
    message: str | None = None
    dataset_results: tuple[DatasetStageResult, ...] = ()

    def __post_init__(self) -> None:
        _require_string(self.stage_id, "stage_id", non_whitespace=True)
        _require_enum(self.status, StageExecutionStatus, "status")
        _require_enum(self.requirement, StageRequirement, "requirement")

        started_at = _normalize_utc(self.started_at_utc, "started_at_utc", optional=True)
        completed_at = _normalize_utc(self.completed_at_utc, "completed_at_utc", optional=True)
        if started_at is not None and completed_at is not None and completed_at < started_at:
            raise ValueError("completed_at_utc cannot precede started_at_utc")
        object.__setattr__(self, "started_at_utc", started_at)
        object.__setattr__(self, "completed_at_utc", completed_at)

        for field_name in ("records_received", "records_processed", "records_rejected"):
            _require_count(getattr(self, field_name), field_name)

        if (self.requirement is StageRequirement.NOT_APPLICABLE) != (
            self.status is StageExecutionStatus.NOT_APPLICABLE
        ):
            raise ValueError("requirement and status must both be NOT_APPLICABLE or neither may be")

        for field_name in ("error_code", "message"):
            value = getattr(self, field_name)
            if value is not None:
                _require_string(value, field_name)

        object.__setattr__(
            self, "dataset_results", _immutable_dataset_results(self.dataset_results)
        )


@dataclass(frozen=True)
class PipelineExecutionSummary:
    """Immutable consolidated stage outcomes for one pipeline execution."""

    summary_id: str
    run_id: str
    client_scope: str
    created_at_utc: datetime
    overall_status: PipelineOverallStatus
    stages: tuple[StageExecutionResult, ...]
    dataset_presence: Mapping[str, bool]
    dq_report_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("summary_id", "run_id", "client_scope"):
            _require_string(getattr(self, field_name), field_name, non_whitespace=True)

        created_at = _normalize_utc(self.created_at_utc, "created_at_utc")
        assert created_at is not None
        object.__setattr__(self, "created_at_utc", created_at)
        _require_enum(self.overall_status, PipelineOverallStatus, "overall_status")

        stages = _immutable_stages(self.stages)
        stage_ids = [stage.stage_id for stage in stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("stage IDs must be unique within a summary")
        object.__setattr__(self, "stages", stages)

        presence = _immutable_dataset_presence(self.dataset_presence)
        object.__setattr__(self, "dataset_presence", presence)

        if self.dq_report_id is not None:
            _require_string(self.dq_report_id, "dq_report_id", non_whitespace=True)


@dataclass(frozen=True)
class PipelineExecutionRequest:
    """Immutable caller-supplied metadata and per-dataset CSV source paths.

    ``execution_intent`` is an opaque, non-empty caller declaration. This model assigns no
    capability semantics to it and never infers the workflow from the supplied datasets.
    """

    run_id: str
    client_scope: str
    workflow: PipelineWorkflow
    dataset_sources: Mapping[str, str | Path]
    execution_intent: str

    def __post_init__(self) -> None:
        _require_string(self.run_id, "run_id", non_whitespace=True)
        _require_string(self.client_scope, "client_scope", non_whitespace=True)
        _require_enum(self.workflow, PipelineWorkflow, "workflow")
        _require_string(self.execution_intent, "execution_intent", non_whitespace=True)
        object.__setattr__(
            self, "dataset_sources", _immutable_dataset_sources(self.dataset_sources)
        )


@dataclass(frozen=True)
class PipelineOrchestrationResult:
    """Immutable orchestration output containing the PES and optional DQ report."""

    summary: PipelineExecutionSummary
    dq_report: DataQualityReport | None = None

    def __post_init__(self) -> None:
        if type(self.summary) is not PipelineExecutionSummary:
            raise TypeError("summary must be a PipelineExecutionSummary")
        if self.dq_report is not None:
            if type(self.dq_report) is not DataQualityReport:
                raise TypeError("dq_report must be a DataQualityReport or None")
            if self.summary.dq_report_id != self.dq_report.report_id:
                raise ValueError("dq_report.report_id must match summary.dq_report_id")
            if self.summary.run_id != self.dq_report.run_id:
                raise ValueError("dq_report.run_id must match summary.run_id")
            if self.summary.client_scope != self.dq_report.client_scope:
                raise ValueError("dq_report.client_scope must match summary.client_scope")
