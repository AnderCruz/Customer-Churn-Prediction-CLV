"""Run the technical CSV-to-schema stages for discovered datasets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import pandas as pd
import pandera as pa

from nowa_customer_intelligence.data.ingestion import CSVHeaderError, CSVIngestionError
from nowa_customer_intelligence.data.ingestion.csv_ingestion import ingest_csv_dataset
from nowa_customer_intelligence.data.preprocessing.type_normalization import (
    DataTypeNormalizationError,
    normalize_dataset_types,
)
from nowa_customer_intelligence.data.schemas import (
    CUSTOMER_SCHEMA,
    INVOICE_SCHEMA,
    SUBSCRIPTION_SCHEMA,
    SUBSCRIPTION_SNAPSHOT_SCHEMA,
    USAGE_MONTHLY_SCHEMA,
)
from nowa_customer_intelligence.pipeline.discovery import DatasetDiscoveryResult
from nowa_customer_intelligence.pipeline.models import (
    DatasetStageResult,
    PipelineExecutionRequest,
    PipelineWorkflow,
    StageExecutionResult,
    StageExecutionStatus,
    StageRequirement,
)

_SCHEMAS = {
    "customers": CUSTOMER_SCHEMA,
    "subscriptions": SUBSCRIPTION_SCHEMA,
    "subscription_snapshots": SUBSCRIPTION_SNAPSHOT_SCHEMA,
    "usage_monthly": USAGE_MONTHLY_SCHEMA,
    "invoices": INVOICE_SCHEMA,
}
_REQUIRED_BY_WORKFLOW = {
    PipelineWorkflow.BASIC: frozenset({"customers", "subscriptions"}),
    PipelineWorkflow.TEMPORAL: frozenset({"customers", "subscriptions", "subscription_snapshots"}),
}
_STAGE_IDS = (
    "header_inspection",
    "csv_ingestion",
    "type_normalization",
    "schema_validation",
)


def _freeze_frames(value: object, field_name: str) -> Mapping[str, pd.DataFrame]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be a mapping of dataset names to DataFrames")
    copied = dict(value)
    if any(not isinstance(key, str) or key not in _SCHEMAS for key in copied):
        raise ValueError(f"{field_name} contains an unsupported dataset name")
    if any(not isinstance(frame, pd.DataFrame) for frame in copied.values()):
        raise TypeError(f"{field_name} values must be pandas DataFrames")
    return MappingProxyType(copied)


@dataclass(frozen=True)
class TechnicalPipelineResult:
    """Immutable technical outcomes and frame mappings for future pipeline stages.

    The mappings and stage outcomes are immutable snapshots. DataFrame objects are not
    copied and remain mutable; callers must treat them as read-only after this result is
    constructed.
    """

    discovery: DatasetDiscoveryResult
    stage_results: tuple[StageExecutionResult, ...]
    normalized_datasets: Mapping[str, pd.DataFrame]
    schema_validated_datasets: Mapping[str, pd.DataFrame]

    def __post_init__(self) -> None:
        if type(self.discovery) is not DatasetDiscoveryResult:
            raise TypeError("discovery must be a DatasetDiscoveryResult")
        stages = tuple(self.stage_results)
        if len(stages) != len(_STAGE_IDS) or any(
            type(stage) is not StageExecutionResult for stage in stages
        ):
            raise TypeError("stage_results must contain the four technical StageExecutionResults")
        if tuple(stage.stage_id for stage in stages) != _STAGE_IDS:
            raise ValueError("stage_results must be in technical pipeline order")
        object.__setattr__(self, "stage_results", stages)
        normalized = _freeze_frames(self.normalized_datasets, "normalized_datasets")
        validated = _freeze_frames(self.schema_validated_datasets, "schema_validated_datasets")
        if not set(validated).issubset(normalized):
            raise ValueError("schema_validated_datasets must be a subset of normalized_datasets")
        supplied = set(self.discovery.dataset_presence)
        if not set(normalized).issubset(supplied):
            raise ValueError("result datasets must be present in discovery")
        if any(not self.discovery.dataset_presence[name] for name in normalized):
            raise ValueError("result datasets must be present in discovery")
        object.__setattr__(self, "normalized_datasets", normalized)
        object.__setattr__(self, "schema_validated_datasets", validated)


def _requirement(dataset: str, required: frozenset[str]) -> StageRequirement:
    return StageRequirement.REQUIRED if dataset in required else StageRequirement.OPTIONAL


def _outcome(
    dataset: str,
    status: StageExecutionStatus,
    requirement: StageRequirement,
    *,
    error_code: str | None = None,
    message: str | None = None,
    rows: int | None = None,
) -> DatasetStageResult:
    return DatasetStageResult(
        dataset=dataset,
        status=status,
        requirement=requirement,
        records_received=rows,
        records_processed=rows if status is StageExecutionStatus.SUCCEEDED else None,
        error_code=error_code,
        message=message,
    )


def _consolidate(
    outcomes: list[DatasetStageResult],
    required: frozenset[str],
    missing_required: bool,
) -> StageExecutionStatus:
    """Apply PES-017 precedence while preserving all individual outcomes.

    A failed required dataset takes precedence over a block when both occur. An absent
    required dataset is represented by discovery and makes this consolidated stage
    BLOCKED; it is not fabricated as a supplied dataset outcome here.
    """
    if any(
        outcome.dataset in required and outcome.status is StageExecutionStatus.FAILED
        for outcome in outcomes
    ):
        return StageExecutionStatus.FAILED
    if missing_required or any(
        outcome.dataset in required and outcome.status is StageExecutionStatus.BLOCKED
        for outcome in outcomes
    ):
        return StageExecutionStatus.BLOCKED
    if any(
        outcome.dataset not in required and outcome.status is not StageExecutionStatus.SUCCEEDED
        for outcome in outcomes
    ):
        return StageExecutionStatus.PARTIAL
    return StageExecutionStatus.SUCCEEDED


def _make_stage(
    stage_id: str,
    outcomes: list[DatasetStageResult],
    required: frozenset[str],
    missing_required: bool,
) -> StageExecutionResult:
    return StageExecutionResult(
        stage_id=stage_id,
        status=_consolidate(outcomes, required, missing_required),
        requirement=StageRequirement.REQUIRED,
        dataset_results=tuple(outcomes),
    )


def run_technical_pipeline(
    request: PipelineExecutionRequest,
    discovery: DatasetDiscoveryResult,
) -> TechnicalPipelineResult:
    """Ingest, normalize, and schema-validate each supplied dataset exactly once.

    Header inspection is integrated into ``ingest_csv_dataset`` and is not called a
    second time here. Error messages are sanitized to a dataset name and exception type;
    exception text may contain paths or source values and is intentionally not exposed.
    """
    if type(request) is not PipelineExecutionRequest:
        raise TypeError("request must be a PipelineExecutionRequest")
    if type(discovery) is not DatasetDiscoveryResult:
        raise TypeError("discovery must be a DatasetDiscoveryResult")
    if dict(discovery.dataset_presence) != {
        name: name in request.dataset_sources for name in _SCHEMAS
    }:
        raise ValueError("discovery dataset presence does not match request sources")

    required = _REQUIRED_BY_WORKFLOW[request.workflow]
    missing_required = any(not discovery.dataset_presence[name] for name in required)
    stage_outcomes: dict[str, list[DatasetStageResult]] = {name: [] for name in _STAGE_IDS}
    normalized: dict[str, pd.DataFrame] = {}
    validated: dict[str, pd.DataFrame] = {}

    for dataset in _SCHEMAS:
        if not discovery.dataset_presence[dataset]:
            continue
        requirement = _requirement(dataset, required)
        source = request.dataset_sources[dataset]
        try:
            ingested = ingest_csv_dataset(source, dataset)
        except CSVHeaderError as exc:
            reason = type(exc).__name__
            stage_outcomes["header_inspection"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.FAILED,
                    requirement,
                    error_code="CSV_HEADER_INVALID",
                    message=f"Header inspection failed for {dataset!r} ({reason}).",
                )
            )
            stage_outcomes["csv_ingestion"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.BLOCKED,
                    requirement,
                    error_code="HEADER_INSPECTION_FAILED",
                    message=f"CSV ingestion was blocked for {dataset!r} after header failure.",
                )
            )
            stage_outcomes["type_normalization"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.BLOCKED,
                    requirement,
                    error_code="CSV_INGESTION_FAILED",
                    message=f"Type normalization was blocked for {dataset!r}.",
                )
            )
            stage_outcomes["schema_validation"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.BLOCKED,
                    requirement,
                    error_code="TYPE_NORMALIZATION_BLOCKED",
                    message=f"Schema validation was blocked for {dataset!r}.",
                )
            )
            continue
        except CSVIngestionError as exc:
            stage_outcomes["header_inspection"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.SUCCEEDED,
                    requirement,
                    rows=None,
                )
            )
            stage_outcomes["csv_ingestion"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.FAILED,
                    requirement,
                    error_code="CSV_INGESTION_FAILED",
                    message=f"CSV ingestion failed for {dataset!r} ({type(exc).__name__}).",
                )
            )
            stage_outcomes["type_normalization"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.BLOCKED,
                    requirement,
                    error_code="CSV_INGESTION_FAILED",
                    message=f"Type normalization was blocked for {dataset!r}.",
                )
            )
            stage_outcomes["schema_validation"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.BLOCKED,
                    requirement,
                    error_code="TYPE_NORMALIZATION_BLOCKED",
                    message=f"Schema validation was blocked for {dataset!r}.",
                )
            )
            continue

        row_count = len(ingested)
        stage_outcomes["header_inspection"].append(
            _outcome(dataset, StageExecutionStatus.SUCCEEDED, requirement, rows=row_count)
        )
        stage_outcomes["csv_ingestion"].append(
            _outcome(dataset, StageExecutionStatus.SUCCEEDED, requirement, rows=row_count)
        )

        try:
            normalized_frame = normalize_dataset_types(ingested, dataset)
        except DataTypeNormalizationError as exc:
            stage_outcomes["type_normalization"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.FAILED,
                    requirement,
                    error_code="TYPE_NORMALIZATION_FAILED",
                    message=f"Type normalization failed for {dataset!r} ({type(exc).__name__}).",
                    rows=row_count,
                )
            )
            stage_outcomes["schema_validation"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.BLOCKED,
                    requirement,
                    error_code="TYPE_NORMALIZATION_FAILED",
                    message=f"Schema validation was blocked for {dataset!r}.",
                    rows=row_count,
                )
            )
            continue

        normalized[dataset] = normalized_frame
        stage_outcomes["type_normalization"].append(
            _outcome(dataset, StageExecutionStatus.SUCCEEDED, requirement, rows=row_count)
        )
        try:
            validated_frame = _SCHEMAS[dataset].validate(normalized_frame)
        except pa.errors.SchemaError as exc:
            stage_outcomes["schema_validation"].append(
                _outcome(
                    dataset,
                    StageExecutionStatus.FAILED,
                    requirement,
                    error_code="SCHEMA_VALIDATION_FAILED",
                    message=f"Schema validation failed for {dataset!r} ({type(exc).__name__}).",
                    rows=row_count,
                )
            )
            continue

        validated[dataset] = validated_frame
        stage_outcomes["schema_validation"].append(
            _outcome(dataset, StageExecutionStatus.SUCCEEDED, requirement, rows=row_count)
        )

    stages = tuple(
        _make_stage(stage_id, stage_outcomes[stage_id], required, missing_required)
        for stage_id in _STAGE_IDS
    )
    return TechnicalPipelineResult(
        discovery=discovery,
        stage_results=stages,
        normalized_datasets=normalized,
        schema_validated_datasets=validated,
    )
