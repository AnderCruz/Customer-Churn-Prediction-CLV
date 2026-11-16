"""Immutable models for Data Quality Validation results."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from types import MappingProxyType


class DataQualitySeverity(Enum):
    """Severity assigned to a Data Quality rule."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class RuleImplementationStatus(Enum):
    """Implementation lifecycle state of a rule."""

    ALREADY_IMPLEMENTED = "ALREADY IMPLEMENTED"
    PROPOSED = "PROPOSED"
    PENDING_DECISION = "PENDING DECISION"
    DEFERRED = "DEFERRED"
    IMPLEMENTED_IN_DQ = "IMPLEMENTED IN DATA QUALITY"


class RuleExecutionResult(Enum):
    """Runtime outcome from executing a rule."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_EVALUATED = "NOT_EVALUATED"


class DataQualityValidationError(ValueError):
    """Invalid invocation precondition for Data Quality Validation."""


def _require_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    return value


def _require_non_whitespace_string(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise DataQualityValidationError(f"{field_name} must be a non-empty string")
    text = value
    if not text.strip():
        raise DataQualityValidationError(f"{field_name} must contain a non-whitespace character")


def _require_enum(value: object, enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{field_name} must be a {enum_type.__name__}")


def _immutable_tuple[SequenceItem](
    values: object,
    *,
    field_name: str,
    item_type: type[SequenceItem],
) -> tuple[SequenceItem, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise TypeError(f"{field_name} must be a sequence")

    copied = tuple(values)
    if any(not isinstance(item, item_type) for item in copied):
        raise TypeError(f"{field_name} must contain only {item_type.__name__} values")
    return copied


def _require_count(value: object, field_name: str) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
        raise ValueError(f"{field_name} must be a non-negative integer or None")


def _immutable_count_mapping[EnumKey: Enum](
    values: object,
    *,
    field_name: str,
    key_type: type[EnumKey],
) -> Mapping[EnumKey, int]:
    if not isinstance(values, Mapping):
        raise TypeError(f"{field_name} must be a mapping")

    copied = dict(values)
    for key, value in copied.items():
        _require_enum(key, key_type, f"{field_name} key")
        _require_count(value, f"{field_name} value")
        if value is None:
            raise TypeError(f"{field_name} values must be integers")
    return MappingProxyType(copied)


def _immutable_presence_mapping(values: object) -> Mapping[str, bool]:
    if not isinstance(values, Mapping):
        raise TypeError("dataset_presence must be a mapping")

    copied = dict(values)
    for key, value in copied.items():
        _require_string(key, "dataset_presence key")
        if not isinstance(value, bool):
            raise TypeError("dataset_presence values must be booleans")
    return MappingProxyType(copied)


@dataclass(frozen=True)
class DataQualityFinding:
    """Immutable result record for one Data Quality rule."""

    rule_id: str
    implementation_status: RuleImplementationStatus
    severity: DataQualitySeverity
    result: RuleExecutionResult
    datasets: tuple[str, ...]
    description: str
    records_evaluated: int | None
    records_affected: int | None
    blocking_datasets: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_string(self.rule_id, "rule_id")
        _require_enum(self.implementation_status, RuleImplementationStatus, "implementation_status")
        _require_enum(self.severity, DataQualitySeverity, "severity")
        _require_enum(self.result, RuleExecutionResult, "result")
        _require_string(self.description, "description")
        _require_count(self.records_evaluated, "records_evaluated")
        _require_count(self.records_affected, "records_affected")
        object.__setattr__(
            self,
            "datasets",
            _immutable_tuple(self.datasets, field_name="datasets", item_type=str),
        )
        object.__setattr__(
            self,
            "blocking_datasets",
            _immutable_tuple(
                self.blocking_datasets,
                field_name="blocking_datasets",
                item_type=str,
            ),
        )


@dataclass(frozen=True)
class DataQualitySummary:
    """Immutable aggregate of Data Quality rule results and blocking outcome."""

    severity_counts: Mapping[DataQualitySeverity, int]
    result_counts: Mapping[RuleExecutionResult, int]
    blocked: bool
    blocked_datasets: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "severity_counts",
            _immutable_count_mapping(
                self.severity_counts,
                field_name="severity_counts",
                key_type=DataQualitySeverity,
            ),
        )
        object.__setattr__(
            self,
            "result_counts",
            _immutable_count_mapping(
                self.result_counts,
                field_name="result_counts",
                key_type=RuleExecutionResult,
            ),
        )
        if not isinstance(self.blocked, bool):
            raise TypeError("blocked must be a boolean")
        object.__setattr__(
            self,
            "blocked_datasets",
            _immutable_tuple(
                self.blocked_datasets,
                field_name="blocked_datasets",
                item_type=str,
            ),
        )


@dataclass(frozen=True)
class DataQualityReport:
    """Immutable, client-scoped Data Quality report."""

    report_id: str
    run_id: str
    client_scope: str
    created_at_utc: datetime
    contract_version: str
    specification_version: str
    pipeline_stage: str
    dataset_presence: Mapping[str, bool]
    summary: DataQualitySummary
    findings: tuple[DataQualityFinding, ...]

    def __post_init__(self) -> None:
        _require_string(self.report_id, "report_id")
        _require_non_whitespace_string(self.run_id, "run_id")
        _require_non_whitespace_string(self.client_scope, "client_scope")
        _require_string(self.contract_version, "contract_version")
        _require_string(self.specification_version, "specification_version")
        _require_string(self.pipeline_stage, "pipeline_stage")
        if self.pipeline_stage != "data_quality_validation":
            raise ValueError("pipeline_stage must be 'data_quality_validation'")
        if type(self.summary) is not DataQualitySummary:
            raise TypeError("summary must be a DataQualitySummary")

        if not isinstance(self.created_at_utc, datetime):
            raise DataQualityValidationError("created_at_utc must be a timezone-aware datetime")
        try:
            if self.created_at_utc.utcoffset() is None:
                raise DataQualityValidationError("created_at_utc must be a timezone-aware datetime")
            utc_timestamp = self.created_at_utc.astimezone(UTC)
        except (OverflowError, ValueError) as exc:
            raise DataQualityValidationError(
                "created_at_utc must be a valid timezone-aware datetime"
            ) from exc
        object.__setattr__(self, "created_at_utc", utc_timestamp)

        object.__setattr__(
            self, "dataset_presence", _immutable_presence_mapping(self.dataset_presence)
        )
        findings = _immutable_tuple(
            self.findings,
            field_name="findings",
            item_type=DataQualityFinding,
        )
        if any(type(finding) is not DataQualityFinding for finding in findings):
            raise TypeError("findings must contain immutable DataQualityFinding instances")
        object.__setattr__(self, "findings", findings)
