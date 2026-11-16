"""Construct Pipeline Execution Summaries from consolidated stage outcomes."""

from collections.abc import Mapping, Sequence
from datetime import datetime

from nowa_customer_intelligence.pipeline.models import (
    PipelineExecutionSummary,
    PipelineOverallStatus,
    StageExecutionResult,
)


def build_pipeline_execution_summary(
    *,
    summary_id: str,
    run_id: str,
    client_scope: str,
    created_at_utc: datetime,
    overall_status: PipelineOverallStatus,
    stages: Sequence[StageExecutionResult],
    dataset_presence: Mapping[str, bool],
    dq_report_id: str | None = None,
) -> PipelineExecutionSummary:
    """Build a summary from supplied metadata and consolidated stage results.

    Model validation is delegated to :class:`PipelineExecutionSummary`. This function
    does not execute or rerun validation, infer overall status, inspect a DQ report, or
    consolidate stage attempts.
    """
    return PipelineExecutionSummary(
        summary_id=summary_id,
        run_id=run_id,
        client_scope=client_scope,
        created_at_utc=created_at_utc,
        overall_status=overall_status,
        stages=stages,
        dataset_presence=dataset_presence,
        dq_report_id=dq_report_id,
    )
