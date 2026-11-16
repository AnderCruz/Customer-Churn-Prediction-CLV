"""Calculate overall execution status from consolidated pipeline stage outcomes."""

from collections.abc import Sequence

from nowa_customer_intelligence.pipeline.models import (
    PipelineOverallStatus,
    StageExecutionResult,
    StageExecutionStatus,
    StageRequirement,
)


def determine_pipeline_overall_status(
    stages: Sequence[StageExecutionResult],
) -> PipelineOverallStatus:
    """Determine the overall status from already-consolidated stage results.

    Optional and not-applicable stages are neutral. Required stage outcomes use the
    approved precedence FAILED, BLOCKED, PARTIAL, then SUCCEEDED. An empty sequence is
    BLOCKED because no execution outcome is available.
    """
    if isinstance(stages, (str, bytes)) or not isinstance(stages, Sequence):
        raise TypeError("stages must be a sequence of StageExecutionResult values")

    required_statuses: list[StageExecutionStatus] = []
    seen_stage_ids: set[str] = set()
    for stage in stages:
        if type(stage) is not StageExecutionResult:
            raise TypeError("stages must contain only StageExecutionResult values")
        if stage.stage_id in seen_stage_ids:
            raise ValueError("stage IDs must be unique; consolidate attempts before aggregation")
        seen_stage_ids.add(stage.stage_id)
        if not isinstance(stage.status, StageExecutionStatus):
            raise TypeError("stage status must be a StageExecutionStatus")
        if not isinstance(stage.requirement, StageRequirement):
            raise TypeError("stage requirement must be a StageRequirement")
        if (stage.requirement is StageRequirement.NOT_APPLICABLE) != (
            stage.status is StageExecutionStatus.NOT_APPLICABLE
        ):
            raise ValueError("stage requirement and status have an invalid combination")
        if stage.requirement is StageRequirement.REQUIRED:
            required_statuses.append(stage.status)

    if not stages:
        return PipelineOverallStatus.BLOCKED
    if not required_statuses:
        return PipelineOverallStatus.SUCCEEDED
    if StageExecutionStatus.FAILED in required_statuses:
        return PipelineOverallStatus.FAILED
    if any(
        status in {StageExecutionStatus.BLOCKED, StageExecutionStatus.NOT_IMPLEMENTED}
        for status in required_statuses
    ):
        return PipelineOverallStatus.BLOCKED
    if any(
        status in {StageExecutionStatus.PARTIAL, StageExecutionStatus.SKIPPED}
        for status in required_statuses
    ):
        return PipelineOverallStatus.PARTIAL
    return PipelineOverallStatus.SUCCEEDED
