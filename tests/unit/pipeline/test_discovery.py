"""Tests for workflow-aware dataset source discovery."""

from pathlib import Path
from types import MappingProxyType

import pytest

from nowa_customer_intelligence.pipeline import (
    DatasetDiscoveryError,
    PipelineExecutionRequest,
    PipelineWorkflow,
    StageExecutionStatus,
    StageRequirement,
    discover_datasets,
)

SUPPORTED_DATASETS = (
    "customers",
    "subscriptions",
    "subscription_snapshots",
    "usage_monthly",
    "invoices",
)


def make_sources(tmp_path: Path, *datasets: str) -> dict[str, Path]:
    sources = {}
    for dataset in datasets:
        path = tmp_path / f"{dataset}.csv"
        path.write_text("placeholder", encoding="utf-8")
        sources[dataset] = path
    return sources


def make_request(
    workflow: PipelineWorkflow,
    dataset_sources: dict[str, str | Path],
) -> PipelineExecutionRequest:
    return PipelineExecutionRequest(
        run_id="run-discovery-1",
        client_scope="client-pseudonym-1",
        workflow=workflow,
        dataset_sources=dataset_sources,
        execution_intent="technical_validation",
    )


def test_basic_succeeds_with_required_sources_and_absent_optional_snapshots(
    tmp_path: Path,
) -> None:
    request = make_request(
        PipelineWorkflow.BASIC,
        make_sources(tmp_path, "customers", "subscriptions"),
    )

    result = discover_datasets(request)

    assert result.dataset_presence["customers"] is True
    assert result.dataset_presence["subscriptions"] is True
    assert result.dataset_presence["subscription_snapshots"] is False
    assert result.stage_result.status is StageExecutionStatus.SUCCEEDED
    assert [outcome.dataset for outcome in result.stage_result.dataset_results] == [
        "customers",
        "subscriptions",
    ]
    assert all(
        outcome.status is StageExecutionStatus.SUCCEEDED
        for outcome in result.stage_result.dataset_results
    )
    assert result.stage_result.dataset_results[0].requirement is StageRequirement.REQUIRED
    assert result.stage_result.dataset_results[1].requirement is StageRequirement.REQUIRED


def test_basic_accepts_present_optional_snapshot_source(tmp_path: Path) -> None:
    request = make_request(
        PipelineWorkflow.BASIC,
        make_sources(tmp_path, "customers", "subscriptions", "subscription_snapshots"),
    )

    result = discover_datasets(request)

    assert result.stage_result.status is StageExecutionStatus.SUCCEEDED
    snapshot_result = result.stage_result.dataset_results[2]
    assert snapshot_result.dataset == "subscription_snapshots"
    assert snapshot_result.requirement is StageRequirement.OPTIONAL


def test_temporal_succeeds_with_all_required_sources(tmp_path: Path) -> None:
    request = make_request(
        PipelineWorkflow.TEMPORAL,
        make_sources(tmp_path, "customers", "subscriptions", "subscription_snapshots"),
    )

    result = discover_datasets(request)

    assert result.stage_result.status is StageExecutionStatus.SUCCEEDED
    assert result.dataset_presence["subscription_snapshots"] is True
    assert result.stage_result.dataset_results[2].requirement is StageRequirement.REQUIRED


def test_temporal_missing_snapshots_blocks_and_preserves_missing_outcome(
    tmp_path: Path,
) -> None:
    request = make_request(
        PipelineWorkflow.TEMPORAL,
        make_sources(tmp_path, "customers", "subscriptions"),
    )

    result = discover_datasets(request)

    assert result.dataset_presence["subscription_snapshots"] is False
    assert result.stage_result.status is StageExecutionStatus.BLOCKED
    snapshot_result = result.stage_result.dataset_results[2]
    assert snapshot_result.dataset == "subscription_snapshots"
    assert snapshot_result.status is StageExecutionStatus.BLOCKED
    assert snapshot_result.requirement is StageRequirement.REQUIRED
    assert snapshot_result.message == "Required dataset 'subscription_snapshots' was not supplied."


@pytest.mark.parametrize("missing", ["customers", "subscriptions"])
def test_basic_missing_required_source_blocks_and_records_dataset(
    tmp_path: Path, missing: str
) -> None:
    supplied = {"customers", "subscriptions"} - {missing}
    request = make_request(PipelineWorkflow.BASIC, make_sources(tmp_path, *sorted(supplied)))

    result = discover_datasets(request)

    assert result.stage_result.status is StageExecutionStatus.BLOCKED
    missing_result = next(
        outcome for outcome in result.stage_result.dataset_results if outcome.dataset == missing
    )
    assert missing_result.status is StageExecutionStatus.BLOCKED
    assert missing_result.requirement is StageRequirement.REQUIRED


def test_missing_optional_usage_and_invoice_sources_are_absent_not_failures(
    tmp_path: Path,
) -> None:
    request = make_request(
        PipelineWorkflow.BASIC,
        make_sources(tmp_path, "customers", "subscriptions"),
    )

    result = discover_datasets(request)

    assert result.stage_result.status is StageExecutionStatus.SUCCEEDED
    assert result.dataset_presence["usage_monthly"] is False
    assert result.dataset_presence["invoices"] is False
    assert "usage_monthly" not in {
        outcome.dataset for outcome in result.stage_result.dataset_results
    }
    assert "invoices" not in {outcome.dataset for outcome in result.stage_result.dataset_results}


def test_present_optional_sources_are_reported_as_optional_outcomes(tmp_path: Path) -> None:
    request = make_request(
        PipelineWorkflow.BASIC,
        make_sources(
            tmp_path,
            "customers",
            "subscriptions",
            "usage_monthly",
            "invoices",
        ),
    )

    result = discover_datasets(request)

    optional = {
        outcome.dataset: outcome.requirement
        for outcome in result.stage_result.dataset_results
        if outcome.dataset in {"usage_monthly", "invoices"}
    }
    assert optional == {
        "usage_monthly": StageRequirement.OPTIONAL,
        "invoices": StageRequirement.OPTIONAL,
    }


def test_unsupported_dataset_name_has_safe_error(tmp_path: Path) -> None:
    source = tmp_path / "private.csv"
    source.touch()
    request = make_request(PipelineWorkflow.BASIC, {"unknown_dataset": source})

    with pytest.raises(
        DatasetDiscoveryError, match="unsupported dataset name: 'unknown_dataset'"
    ) as error:
        discover_datasets(request)

    assert str(tmp_path) not in str(error.value)


def test_missing_supplied_source_path_has_safe_error(tmp_path: Path) -> None:
    missing = tmp_path / "private" / "customers.csv"
    request = make_request(PipelineWorkflow.BASIC, {"customers": missing})

    with pytest.raises(DatasetDiscoveryError, match="source path for dataset 'customers'") as error:
        discover_datasets(request)

    assert str(missing) not in str(error.value)


def test_directory_source_is_rejected_without_exposing_path(tmp_path: Path) -> None:
    request = make_request(PipelineWorkflow.BASIC, {"customers": tmp_path})

    with pytest.raises(DatasetDiscoveryError, match="not a regular file") as error:
        discover_datasets(request)

    assert str(tmp_path) not in str(error.value)


def test_discovery_does_not_infer_workflow_from_dataset_presence(tmp_path: Path) -> None:
    request = make_request(
        PipelineWorkflow.BASIC,
        make_sources(tmp_path, "customers", "subscriptions", "subscription_snapshots"),
    )

    result = discover_datasets(request)

    assert request.workflow is PipelineWorkflow.BASIC
    assert result.stage_result.dataset_results[2].requirement is StageRequirement.OPTIONAL


def test_discovery_output_is_immutable(tmp_path: Path) -> None:
    sources = make_sources(tmp_path, "customers", "subscriptions")
    request = make_request(PipelineWorkflow.BASIC, sources)

    result = discover_datasets(request)
    sources.clear()

    assert isinstance(result.dataset_presence, MappingProxyType)
    assert len(result.dataset_presence) == len(SUPPORTED_DATASETS)
    with pytest.raises(TypeError):
        result.dataset_presence["customers"] = False  # type: ignore[index]
    with pytest.raises(AttributeError):
        result.stage_result.dataset_results.append(object())  # type: ignore[attr-defined]


def test_discovery_preserves_one_dataset_outcome_per_supplied_source(tmp_path: Path) -> None:
    request = make_request(
        PipelineWorkflow.BASIC,
        make_sources(tmp_path, "customers", "subscriptions", "invoices"),
    )

    result = discover_datasets(request)

    outcomes = {outcome.dataset: outcome for outcome in result.stage_result.dataset_results}
    assert set(outcomes) == {"customers", "subscriptions", "invoices"}
    assert outcomes["invoices"].requirement is StageRequirement.OPTIONAL
    assert outcomes["invoices"].status is StageExecutionStatus.SUCCEEDED


def test_discovery_does_not_open_or_inspect_source_contents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "customers.csv"
    source.write_bytes(b"\xff,invalid header and content")
    request = make_request(PipelineWorkflow.BASIC, {"customers": source})

    def fail_if_opened(*args: object, **kwargs: object) -> None:
        raise AssertionError("discovery must not read source contents")

    monkeypatch.setattr(Path, "open", fail_if_opened)

    result = discover_datasets(request)

    assert result.dataset_presence["customers"] is True
    assert result.stage_result.status is StageExecutionStatus.BLOCKED
