"""Discover supplied datasets and apply the declared workflow's availability policy."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from nowa_customer_intelligence.data.ingestion.csv_ingestion import DATASET_FILENAMES
from nowa_customer_intelligence.pipeline.models import (
    DatasetStageResult,
    PipelineExecutionRequest,
    PipelineWorkflow,
    StageExecutionResult,
    StageExecutionStatus,
    StageRequirement,
)

_SUPPORTED_DATASETS = tuple(DATASET_FILENAMES)
_REQUIRED_DATASETS = {
    PipelineWorkflow.BASIC: frozenset({"customers", "subscriptions"}),
    PipelineWorkflow.TEMPORAL: frozenset({"customers", "subscriptions", "subscription_snapshots"}),
}


class DatasetDiscoveryError(ValueError):
    """Raised when a supplied dataset name or source path is invalid."""


def _freeze_presence(values: Mapping[str, bool]) -> Mapping[str, bool]:
    copied = dict(values)
    if set(copied) != set(_SUPPORTED_DATASETS):
        raise ValueError("dataset_presence must include every supported dataset")
    if any(not isinstance(value, bool) for value in copied.values()):
        raise TypeError("dataset_presence values must be booleans")
    return MappingProxyType(copied)


@dataclass(frozen=True)
class DatasetDiscoveryResult:
    """Immutable presence map and consolidated outcome for dataset discovery."""

    dataset_presence: Mapping[str, bool]
    stage_result: StageExecutionResult

    def __post_init__(self) -> None:
        object.__setattr__(self, "dataset_presence", _freeze_presence(self.dataset_presence))
        if type(self.stage_result) is not StageExecutionResult:
            raise TypeError("stage_result must be a StageExecutionResult")
        if self.stage_result.stage_id != "dataset_discovery":
            raise ValueError("stage_result.stage_id must be 'dataset_discovery'")


def discover_datasets(request: PipelineExecutionRequest) -> DatasetDiscoveryResult:
    """Inspect supplied source paths and apply BASIC or TEMPORAL availability rules.

    Discovery checks only source-name support and whether each supplied path identifies a
    regular file. It does not open files or inspect headers, records, or content. A dataset
    omitted from ``request.dataset_sources`` is absent; a supplied path that does not name
    a regular file is an invalid request source and raises :class:`DatasetDiscoveryError`.
    Missing required datasets produce a ``BLOCKED`` discovery stage. Missing optional
    datasets are represented as absent without a failed per-dataset outcome.
    """
    if type(request) is not PipelineExecutionRequest:
        raise TypeError("request must be a PipelineExecutionRequest")

    unsupported = [name for name in request.dataset_sources if name not in _SUPPORTED_DATASETS]
    if unsupported:
        raise DatasetDiscoveryError(f"unsupported dataset name: {unsupported[0]!r}")

    for dataset, source in request.dataset_sources.items():
        path = Path(source)
        try:
            is_file = path.is_file()
        except (OSError, ValueError) as exc:
            raise DatasetDiscoveryError(
                f"source path for dataset {dataset!r} cannot be inspected"
            ) from exc
        if not is_file:
            raise DatasetDiscoveryError(
                f"source path for dataset {dataset!r} is missing or is not a regular file"
            )

    required = _REQUIRED_DATASETS[request.workflow]
    presence = {dataset: dataset in request.dataset_sources for dataset in _SUPPORTED_DATASETS}
    outcomes = []
    missing_required = False

    for dataset in _SUPPORTED_DATASETS:
        if presence[dataset]:
            outcomes.append(
                DatasetStageResult(
                    dataset=dataset,
                    status=StageExecutionStatus.SUCCEEDED,
                    requirement=(
                        StageRequirement.REQUIRED
                        if dataset in required
                        else StageRequirement.OPTIONAL
                    ),
                )
            )
        elif dataset in required:
            missing_required = True
            outcomes.append(
                DatasetStageResult(
                    dataset=dataset,
                    status=StageExecutionStatus.BLOCKED,
                    requirement=StageRequirement.REQUIRED,
                    message=f"Required dataset {dataset!r} was not supplied.",
                )
            )

    stage_result = StageExecutionResult(
        stage_id="dataset_discovery",
        status=(
            StageExecutionStatus.BLOCKED if missing_required else StageExecutionStatus.SUCCEEDED
        ),
        requirement=StageRequirement.REQUIRED,
        dataset_results=tuple(outcomes),
    )
    return DatasetDiscoveryResult(dataset_presence=presence, stage_result=stage_result)
