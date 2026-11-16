"""Unit tests for technical pipeline integration."""

from pathlib import Path

import pytest

from nowa_customer_intelligence.data.ingestion import csv_ingestion
from nowa_customer_intelligence.pipeline import (
    PipelineExecutionRequest,
    PipelineWorkflow,
    StageExecutionStatus,
    StageRequirement,
    discover_datasets,
    run_technical_pipeline,
)

_CSV = {
    "customers": "customer_id,created_at\nC1,2025-01-01\n",
    "subscriptions": "subscription_id,customer_id,start_date,subscription_status\n"
    "S1,C1,2025-01-01,active\n",
    "subscription_snapshots": "subscription_id,snapshot_date,subscription_status\n"
    "S1,2025-02-01,active\n",
    "usage_monthly": "subscription_id,usage_month,active_users,total_users\nS1,2025-02-01,1,2\n",
    "invoices": "invoice_id,subscription_id,invoice_date,amount,currency,invoice_status\n"
    "I1,S1,2025-02-01,10.00,USD,paid\n",
}


def _write_sources(tmp_path: Path, datasets: set[str]) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    sources: dict[str, Path] = {}
    for name in datasets:
        path = tmp_path / f"{name}.csv"
        path.write_text(_CSV[name], encoding="utf-8")
        sources[name] = path
    return sources


def _run(
    tmp_path: Path,
    datasets: set[str] | None = None,
    *,
    workflow: PipelineWorkflow = PipelineWorkflow.BASIC,
) -> tuple[PipelineExecutionRequest, object]:
    source_map = _write_sources(
        tmp_path,
        datasets if datasets is not None else {"customers", "subscriptions"},
    )
    request = PipelineExecutionRequest(
        run_id="run-1",
        client_scope="client-pseudonym-1",
        workflow=workflow,
        dataset_sources=source_map,
        execution_intent="technical_validation",
    )
    discovery = discover_datasets(request)
    return request, run_technical_pipeline(request, discovery)


def _stage(result: object, stage_id: str):
    return next(stage for stage in result.stage_results if stage.stage_id == stage_id)  # type: ignore[attr-defined]


def _dataset_result(result: object, stage_id: str, dataset: str):
    stage = _stage(result, stage_id)
    return next(outcome for outcome in stage.dataset_results if outcome.dataset == dataset)


def test_valid_datasets_pass_all_four_technical_stages(tmp_path: Path) -> None:
    _, result = _run(tmp_path, set(_CSV), workflow=PipelineWorkflow.TEMPORAL)

    assert [stage.stage_id for stage in result.stage_results] == [
        "header_inspection",
        "csv_ingestion",
        "type_normalization",
        "schema_validation",
    ]
    assert all(stage.status is StageExecutionStatus.SUCCEEDED for stage in result.stage_results)
    assert set(result.normalized_datasets) == set(_CSV)
    assert set(result.schema_validated_datasets) == set(_CSV)
    assert all(len(stage.dataset_results) == len(_CSV) for stage in result.stage_results)


def test_ingestion_invokes_integrated_header_inspection_once_per_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inspected: list[str] = []
    original = csv_ingestion.inspect_csv_header

    def record(path: str | Path, dataset: str) -> tuple[str, ...]:
        inspected.append(dataset)
        return original(path, dataset)

    monkeypatch.setattr(csv_ingestion, "inspect_csv_header", record)
    _run(tmp_path)

    assert inspected == ["customers", "subscriptions"]


def test_header_failure_blocks_ingestion_and_downstream_for_that_dataset(
    tmp_path: Path,
) -> None:
    sources = _write_sources(tmp_path, {"customers", "subscriptions"})
    sources["customers"].write_text("wrong,header\nC1,2025-01-01\n", encoding="utf-8")
    request = PipelineExecutionRequest(
        "run-1", "client-1", PipelineWorkflow.BASIC, sources, "validate"
    )

    result = run_technical_pipeline(request, discover_datasets(request))

    assert (
        _dataset_result(result, "header_inspection", "customers").status
        is StageExecutionStatus.FAILED
    )
    assert (
        _dataset_result(result, "csv_ingestion", "customers").status is StageExecutionStatus.BLOCKED
    )
    assert (
        _dataset_result(result, "type_normalization", "customers").status
        is StageExecutionStatus.BLOCKED
    )
    assert (
        _dataset_result(result, "schema_validation", "customers").status
        is StageExecutionStatus.BLOCKED
    )
    assert (
        _dataset_result(result, "schema_validation", "subscriptions").status
        is StageExecutionStatus.SUCCEEDED
    )
    assert _stage(result, "schema_validation").status is StageExecutionStatus.BLOCKED
    assert "customers.csv" not in str(result.stage_results)
    assert "wrong,header" not in str(result.stage_results)


def test_ingestion_failure_keeps_header_success_and_blocks_later_stages(
    tmp_path: Path,
) -> None:
    sources = _write_sources(tmp_path, {"customers", "subscriptions"})
    sources["customers"].write_text(
        "customer_id,created_at\nC1,2025-01-01,extra\n", encoding="utf-8"
    )
    request = PipelineExecutionRequest(
        "run-1", "client-1", PipelineWorkflow.BASIC, sources, "validate"
    )

    result = run_technical_pipeline(request, discover_datasets(request))

    assert (
        _dataset_result(result, "header_inspection", "customers").status
        is StageExecutionStatus.SUCCEEDED
    )
    assert (
        _dataset_result(result, "csv_ingestion", "customers").status is StageExecutionStatus.FAILED
    )
    assert (
        _dataset_result(result, "type_normalization", "customers").status
        is StageExecutionStatus.BLOCKED
    )
    assert _stage(result, "csv_ingestion").status is StageExecutionStatus.FAILED
    assert "customers.csv" not in str(result.stage_results)


def test_normalization_failure_blocks_schema_and_optional_failure_is_partial(
    tmp_path: Path,
) -> None:
    sources = _write_sources(tmp_path, {"customers", "subscriptions", "usage_monthly"})
    sources["usage_monthly"].write_text(
        "subscription_id,usage_month,active_users\nS1,2025-02-01,1.5\n", encoding="utf-8"
    )
    request = PipelineExecutionRequest(
        "run-1", "client-1", PipelineWorkflow.BASIC, sources, "validate"
    )

    result = run_technical_pipeline(request, discover_datasets(request))

    assert (
        _dataset_result(result, "type_normalization", "usage_monthly").status
        is StageExecutionStatus.FAILED
    )
    assert (
        _dataset_result(result, "schema_validation", "usage_monthly").status
        is StageExecutionStatus.BLOCKED
    )
    assert _stage(result, "type_normalization").status is StageExecutionStatus.PARTIAL
    assert _stage(result, "schema_validation").status is StageExecutionStatus.PARTIAL
    assert "usage_monthly" not in result.schema_validated_datasets
    assert {"customers", "subscriptions"}.issubset(result.schema_validated_datasets)


def test_schema_failure_is_retained_and_successful_datasets_remain_available(
    tmp_path: Path,
) -> None:
    sources = _write_sources(tmp_path, {"customers", "subscriptions", "usage_monthly"})
    sources["usage_monthly"].write_text(
        "subscription_id,usage_month,active_users\nS1,2025-02-01,-1\n", encoding="utf-8"
    )
    request = PipelineExecutionRequest(
        "run-1", "client-1", PipelineWorkflow.BASIC, sources, "validate"
    )

    result = run_technical_pipeline(request, discover_datasets(request))

    assert (
        _dataset_result(result, "schema_validation", "usage_monthly").status
        is StageExecutionStatus.FAILED
    )
    assert _stage(result, "schema_validation").status is StageExecutionStatus.PARTIAL
    assert "usage_monthly" in result.normalized_datasets
    assert "usage_monthly" not in result.schema_validated_datasets
    assert {"customers", "subscriptions"}.issubset(result.schema_validated_datasets)


def test_required_schema_failure_consolidates_as_failed(tmp_path: Path) -> None:
    sources = _write_sources(tmp_path, {"customers", "subscriptions"})
    sources["customers"].write_text(
        "customer_id,created_at\nC1,2025-01-01\nC1,2025-01-02\n", encoding="utf-8"
    )
    request = PipelineExecutionRequest(
        "run-1", "client-1", PipelineWorkflow.BASIC, sources, "validate"
    )

    result = run_technical_pipeline(request, discover_datasets(request))

    assert _stage(result, "schema_validation").status is StageExecutionStatus.FAILED
    assert (
        _dataset_result(result, "schema_validation", "customers").status
        is StageExecutionStatus.FAILED
    )
    assert (
        _dataset_result(result, "schema_validation", "subscriptions").status
        is StageExecutionStatus.SUCCEEDED
    )


def test_basic_snapshots_are_optional_and_temporal_snapshots_are_required(
    tmp_path: Path,
) -> None:
    _, basic_result = _run(
        tmp_path / "basic",
        {"customers", "subscriptions", "subscription_snapshots"},
        workflow=PipelineWorkflow.BASIC,
    )
    assert (
        _dataset_result(basic_result, "schema_validation", "subscription_snapshots").requirement
        is StageRequirement.OPTIONAL
    )

    temporal_dir = tmp_path / "temporal"
    temporal_dir.mkdir()
    _, temporal_result = _run(
        temporal_dir,
        {"customers", "subscriptions", "subscription_snapshots"},
        workflow=PipelineWorkflow.TEMPORAL,
    )
    assert (
        _dataset_result(temporal_result, "schema_validation", "subscription_snapshots").requirement
        is StageRequirement.REQUIRED
    )


def test_missing_temporal_snapshot_remains_in_discovery_not_supplied_outcomes(
    tmp_path: Path,
) -> None:
    request, result = _run(
        tmp_path, {"customers", "subscriptions"}, workflow=PipelineWorkflow.TEMPORAL
    )

    assert result.discovery.dataset_presence["subscription_snapshots"] is False
    missing = next(
        item
        for item in result.discovery.stage_result.dataset_results
        if item.dataset == "subscription_snapshots"
    )
    assert missing.status is StageExecutionStatus.BLOCKED
    assert all(
        "subscription_snapshots" not in {item.dataset for item in stage.dataset_results}
        for stage in result.stage_results
    )
    assert all(stage.status is StageExecutionStatus.BLOCKED for stage in result.stage_results)
    assert request.workflow is PipelineWorkflow.TEMPORAL


def test_result_makes_no_registry_ri_or_dq_claims(tmp_path: Path) -> None:
    _, result = _run(tmp_path)

    assert [stage.stage_id for stage in result.stage_results] == [
        "header_inspection",
        "csv_ingestion",
        "type_normalization",
        "schema_validation",
    ]
    assert not any(
        "ri" in stage.stage_id or "quality" in stage.stage_id for stage in result.stage_results
    )
