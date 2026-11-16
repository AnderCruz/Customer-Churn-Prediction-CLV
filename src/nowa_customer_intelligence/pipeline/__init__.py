"""Pipeline execution summary models."""

from nowa_customer_intelligence.pipeline.aggregation import determine_pipeline_overall_status
from nowa_customer_intelligence.pipeline.discovery import (
    DatasetDiscoveryError,
    DatasetDiscoveryResult,
    discover_datasets,
)
from nowa_customer_intelligence.pipeline.execution import (
    PipelineOperationalInputError,
    execute_pipeline,
)
from nowa_customer_intelligence.pipeline.finalization import build_final_pipeline_result
from nowa_customer_intelligence.pipeline.models import (
    DatasetStageResult,
    PipelineExecutionRequest,
    PipelineExecutionSummary,
    PipelineOrchestrationResult,
    PipelineOverallStatus,
    PipelineWorkflow,
    StageExecutionResult,
    StageExecutionStatus,
    StageRequirement,
)
from nowa_customer_intelligence.pipeline.quality import (
    QualityOrchestrationResult,
    orchestrate_referential_integrity_and_data_quality,
)
from nowa_customer_intelligence.pipeline.reporting import build_pipeline_execution_summary
from nowa_customer_intelligence.pipeline.technical import (
    TechnicalPipelineResult,
    run_technical_pipeline,
)

__all__ = [
    "DatasetStageResult",
    "DatasetDiscoveryError",
    "DatasetDiscoveryResult",
    "PipelineExecutionSummary",
    "PipelineOperationalInputError",
    "PipelineExecutionRequest",
    "PipelineOrchestrationResult",
    "PipelineOverallStatus",
    "PipelineWorkflow",
    "QualityOrchestrationResult",
    "StageExecutionResult",
    "StageExecutionStatus",
    "StageRequirement",
    "TechnicalPipelineResult",
    "build_pipeline_execution_summary",
    "build_final_pipeline_result",
    "determine_pipeline_overall_status",
    "discover_datasets",
    "execute_pipeline",
    "orchestrate_referential_integrity_and_data_quality",
    "run_technical_pipeline",
]
