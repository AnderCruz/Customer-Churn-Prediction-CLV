"""Public entry point for one complete MVP pipeline execution."""

from nowa_customer_intelligence.pipeline.discovery import (
    DatasetDiscoveryError,
    DatasetDiscoveryResult,
    discover_datasets,
)
from nowa_customer_intelligence.pipeline.finalization import build_final_pipeline_result
from nowa_customer_intelligence.pipeline.models import (
    PipelineExecutionRequest,
    PipelineOrchestrationResult,
    PipelineWorkflow,
)
from nowa_customer_intelligence.pipeline.quality import (
    orchestrate_referential_integrity_and_data_quality,
)
from nowa_customer_intelligence.pipeline.technical import (
    TechnicalPipelineResult,
    run_technical_pipeline,
)

_REQUIRED_BY_WORKFLOW = {
    PipelineWorkflow.BASIC: frozenset({"customers", "subscriptions"}),
    PipelineWorkflow.TEMPORAL: frozenset({"customers", "subscriptions", "subscription_snapshots"}),
}


class PipelineOperationalInputError(ValueError):
    """Raised when supplied, schema-valid data cannot satisfy workflow row requirements.

    The exception retains discovery and technical results so callers can inspect what
    completed without receiving a misleading successful Pipeline Execution Summary.
    """

    def __init__(
        self,
        *,
        request: PipelineExecutionRequest,
        dataset: str,
        discovery: DatasetDiscoveryResult,
        technical_result: TechnicalPipelineResult,
    ) -> None:
        self.request = request
        self.dataset = dataset
        self.error_code = "REQUIRED_DATASET_EMPTY"
        self.discovery = discovery
        self.technical_result = technical_result
        super().__init__(
            f"Required dataset {dataset!r} is present but empty for the declared workflow."
        )


def execute_pipeline(request: PipelineExecutionRequest) -> PipelineOrchestrationResult:
    """Execute discovery, technical validation, RI/DQ, and final summary construction.

    Existing component errors are allowed to propagate according to their public
    contracts. In particular, invalid source paths raise ``DatasetDiscoveryError``;
    processing and quality outcomes after discovery are preserved in the returned PES.
    """
    if type(request) is not PipelineExecutionRequest:
        raise TypeError("request must be a PipelineExecutionRequest")

    discovery = discover_datasets(request)
    technical_result = run_technical_pipeline(request, discovery)
    required = _REQUIRED_BY_WORKFLOW[request.workflow]
    for dataset in ("customers", "subscriptions", "subscription_snapshots"):
        if (
            dataset in required
            and discovery.dataset_presence[dataset]
            and dataset in technical_result.schema_validated_datasets
            and technical_result.schema_validated_datasets[dataset].empty
        ):
            raise PipelineOperationalInputError(
                request=request,
                dataset=dataset,
                discovery=discovery,
                technical_result=technical_result,
            )

    quality_result = orchestrate_referential_integrity_and_data_quality(request, technical_result)
    return build_final_pipeline_result(
        request,
        discovery,
        technical_result,
        quality_result,
    )


__all__ = ["DatasetDiscoveryError", "PipelineOperationalInputError", "execute_pipeline"]
