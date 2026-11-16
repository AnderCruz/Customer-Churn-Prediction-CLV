"""Consolidate completed pipeline stages into a Pipeline Execution Summary."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from nowa_customer_intelligence.pipeline.aggregation import determine_pipeline_overall_status
from nowa_customer_intelligence.pipeline.discovery import DatasetDiscoveryResult
from nowa_customer_intelligence.pipeline.models import (
    PipelineExecutionRequest,
    PipelineOrchestrationResult,
    StageExecutionResult,
)
from nowa_customer_intelligence.pipeline.quality import QualityOrchestrationResult
from nowa_customer_intelligence.pipeline.reporting import build_pipeline_execution_summary
from nowa_customer_intelligence.pipeline.technical import TechnicalPipelineResult

_DATASETS = (
    "customers",
    "subscriptions",
    "subscription_snapshots",
    "usage_monthly",
    "invoices",
)
_EXPECTED_STAGE_IDS = (
    "dataset_discovery",
    "header_inspection",
    "csv_ingestion",
    "type_normalization",
    "schema_validation",
    "referential_integrity",
    "data_quality",
)


def _validate_context(
    request: PipelineExecutionRequest,
    discovery: DatasetDiscoveryResult,
    technical_result: TechnicalPipelineResult,
    quality_result: QualityOrchestrationResult,
) -> None:
    if type(request) is not PipelineExecutionRequest:
        raise TypeError("request must be a PipelineExecutionRequest")
    if type(discovery) is not DatasetDiscoveryResult:
        raise TypeError("discovery must be a DatasetDiscoveryResult")
    if type(technical_result) is not TechnicalPipelineResult:
        raise TypeError("technical_result must be a TechnicalPipelineResult")
    if type(quality_result) is not QualityOrchestrationResult:
        raise TypeError("quality_result must be a QualityOrchestrationResult")

    expected_presence = {name: name in request.dataset_sources for name in _DATASETS}
    if dict(discovery.dataset_presence) != expected_presence:
        raise ValueError("discovery dataset presence does not match the request")
    if technical_result.discovery is not discovery:
        raise ValueError("technical_result does not reference the supplied discovery result")
    if quality_result.request.run_id != request.run_id:
        raise ValueError("quality_result run_id does not match the request")
    if quality_result.request.client_scope != request.client_scope:
        raise ValueError("quality_result client_scope does not match the request")
    if quality_result.request is not request:
        raise ValueError("quality_result does not reference the supplied request")
    if quality_result.technical_result is not technical_result:
        raise ValueError("quality_result does not reference the supplied technical result")


def _consolidated_stages(
    discovery: DatasetDiscoveryResult,
    technical_result: TechnicalPipelineResult,
    quality_result: QualityOrchestrationResult,
) -> tuple[StageExecutionResult, ...]:
    stages = (
        discovery.stage_result,
        *technical_result.stage_results,
        quality_result.referential_integrity_stage,
        quality_result.data_quality_stage,
    )
    if any(type(stage) is not StageExecutionResult for stage in stages):
        raise TypeError("all upstream stage outcomes must be StageExecutionResult values")
    stage_ids = tuple(stage.stage_id for stage in stages)
    if len(stage_ids) != len(set(stage_ids)):
        raise ValueError("upstream stage results contain duplicate stage IDs")
    if stage_ids != _EXPECTED_STAGE_IDS:
        raise ValueError("upstream stage results are missing, unexpected, or out of order")
    return stages


def build_final_pipeline_result(
    request: PipelineExecutionRequest,
    discovery: DatasetDiscoveryResult,
    technical_result: TechnicalPipelineResult,
    quality_result: QualityOrchestrationResult,
) -> PipelineOrchestrationResult:
    """Build the final PES from existing outputs without rerunning any pipeline stage.

    Summary identifiers use UUIDv4, and summary timestamps use the existing UTC-now
    convention. Registry Consistency and Semantic Attribution are not added or assigned
    applicability here: the current request keeps ``execution_intent`` opaque, and no
    upstream result carries either stage.
    """
    _validate_context(request, discovery, technical_result, quality_result)
    stages = _consolidated_stages(discovery, technical_result, quality_result)
    dataset_presence = dict(discovery.dataset_presence)
    overall_status = determine_pipeline_overall_status(stages)
    report = quality_result.dq_report

    if not quality_result.gate_passed and report is not None:
        raise ValueError("a schema-gate-blocked execution cannot reference a DQ Report")
    if report is not None:
        if report.run_id != request.run_id:
            raise ValueError("DQ Report run_id does not match the request")
        if report.client_scope != request.client_scope:
            raise ValueError("DQ Report client_scope does not match the request")

    summary = build_pipeline_execution_summary(
        summary_id=str(uuid4()),
        run_id=request.run_id,
        client_scope=request.client_scope,
        created_at_utc=datetime.now(UTC),
        overall_status=overall_status,
        stages=stages,
        dataset_presence=dataset_presence,
        dq_report_id=report.report_id if report is not None else None,
    )
    return PipelineOrchestrationResult(summary=summary, dq_report=report)
