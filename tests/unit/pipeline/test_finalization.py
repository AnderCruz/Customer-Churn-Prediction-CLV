"""Tests for final Pipeline Execution Summary construction."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from nowa_customer_intelligence.pipeline import (
    PipelineExecutionRequest,
    PipelineOrchestrationResult,
    PipelineOverallStatus,
    PipelineWorkflow,
    StageExecutionStatus,
    StageRequirement,
    TechnicalPipelineResult,
    build_final_pipeline_result,
    discover_datasets,
    orchestrate_referential_integrity_and_data_quality,
    run_technical_pipeline,
)
from nowa_customer_intelligence.pipeline import finalization as finalization_module

_CSV = {
    "customers": "customer_id,created_at\nC1,2025-01-01\n",
    "subscriptions": "subscription_id,customer_id,start_date,subscription_status\n"
    "S1,C1,2025-01-01,active\n",
    "subscription_snapshots": "subscription_id,snapshot_date,subscription_status\n"
    "S1,2025-02-01,active\n",
    "usage_monthly": "subscription_id,usage_month,active_users\nS1,2025-02-01,1\n",
    "invoices": "invoice_id,subscription_id,invoice_date,amount,currency,invoice_status\n"
    "I1,S1,2025-02-01,10.00,USD,paid\n",
}


def _execution(
    tmp_path: Path,
    *,
    supplied: set[str] | None = None,
    workflow: PipelineWorkflow = PipelineWorkflow.BASIC,
    overrides: dict[str, str] | None = None,
):
    tmp_path.mkdir(parents=True, exist_ok=True)
    names = supplied if supplied is not None else {"customers", "subscriptions"}
    sources = {}
    for name in names:
        path = tmp_path / f"{name}.csv"
        path.write_text((overrides or {}).get(name, _CSV[name]), encoding="utf-8")
        sources[name] = path
    request = PipelineExecutionRequest(
        run_id="run-final-1",
        client_scope="client-pseudonym-1",
        workflow=workflow,
        dataset_sources=sources,
        execution_intent="opaque-operation-context",
    )
    discovery = discover_datasets(request)
    technical = run_technical_pipeline(request, discovery)
    quality = orchestrate_referential_integrity_and_data_quality(request, technical)
    return request, discovery, technical, quality


def _finalize(request, discovery, technical, quality):
    return build_final_pipeline_result(request, discovery, technical, quality)


def _replace_technical_stage(
    technical: TechnicalPipelineResult,
    stage_id: str,
    *,
    status: StageExecutionStatus,
    requirement: StageRequirement | None = None,
) -> TechnicalPipelineResult:
    stages = tuple(
        replace(
            stage,
            status=status,
            requirement=requirement if requirement is not None else stage.requirement,
        )
        if stage.stage_id == stage_id
        else stage
        for stage in technical.stage_results
    )
    return replace(technical, stage_results=stages)


def _relink_quality(quality, technical):
    return replace(quality, technical_result=technical)


def test_final_result_contains_all_seven_original_stages_in_order(tmp_path: Path) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    original_stages = (
        discovery.stage_result,
        *technical.stage_results,
        quality.referential_integrity_stage,
        quality.data_quality_stage,
    )

    result = _finalize(request, discovery, technical, quality)

    assert isinstance(result, PipelineOrchestrationResult)
    assert tuple(stage.stage_id for stage in result.summary.stages) == (
        "dataset_discovery",
        "header_inspection",
        "csv_ingestion",
        "type_normalization",
        "schema_validation",
        "referential_integrity",
        "data_quality",
    )
    assert all(
        actual is original
        for actual, original in zip(result.summary.stages, original_stages, strict=True)
    )
    assert tuple(stage.status for stage in result.summary.stages) == tuple(
        stage.status for stage in original_stages
    )
    for actual, original in zip(result.summary.stages, original_stages, strict=True):
        assert actual.dataset_results == original.dataset_results
        assert actual.requirement is original.requirement


def test_summary_uses_request_presence_context_and_existing_id_time_conventions(
    tmp_path: Path,
) -> None:
    request, discovery, technical, quality = _execution(tmp_path)

    result = _finalize(request, discovery, technical, quality)

    UUID(result.summary.summary_id)
    assert result.summary.run_id == request.run_id
    assert result.summary.client_scope == request.client_scope
    assert result.summary.created_at_utc.tzinfo is UTC
    assert result.summary.dataset_presence == discovery.dataset_presence
    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED


def test_aggregator_and_builder_are_called_once_with_original_stages(tmp_path: Path) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    real_aggregator = finalization_module.determine_pipeline_overall_status
    real_builder = finalization_module.build_pipeline_execution_summary
    with (
        patch.object(
            finalization_module,
            "determine_pipeline_overall_status",
            wraps=real_aggregator,
        ) as aggregate_spy,
        patch.object(
            finalization_module,
            "build_pipeline_execution_summary",
            wraps=real_builder,
        ) as builder_spy,
    ):
        result = _finalize(request, discovery, technical, quality)

    aggregate_spy.assert_called_once()
    builder_spy.assert_called_once()
    assert aggregate_spy.call_args.args[0] == result.summary.stages
    assert builder_spy.call_args.kwargs["overall_status"] is result.summary.overall_status
    assert result.summary.overall_status is real_aggregator(result.summary.stages)


@pytest.mark.parametrize(
    ("status", "requirement", "expected"),
    [
        (StageExecutionStatus.FAILED, StageRequirement.REQUIRED, PipelineOverallStatus.FAILED),
        (StageExecutionStatus.BLOCKED, StageRequirement.REQUIRED, PipelineOverallStatus.BLOCKED),
        (
            StageExecutionStatus.NOT_IMPLEMENTED,
            StageRequirement.REQUIRED,
            PipelineOverallStatus.BLOCKED,
        ),
        (StageExecutionStatus.PARTIAL, StageRequirement.REQUIRED, PipelineOverallStatus.PARTIAL),
        (StageExecutionStatus.FAILED, StageRequirement.OPTIONAL, PipelineOverallStatus.SUCCEEDED),
        (
            StageExecutionStatus.NOT_APPLICABLE,
            StageRequirement.NOT_APPLICABLE,
            PipelineOverallStatus.SUCCEEDED,
        ),
    ],
)
def test_overall_status_uses_existing_aggregator_without_rewriting_stage(
    tmp_path: Path,
    status: StageExecutionStatus,
    requirement: StageRequirement,
    expected: PipelineOverallStatus,
) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    technical = _replace_technical_stage(
        technical,
        "csv_ingestion",
        status=status,
        requirement=requirement,
    )
    quality = _relink_quality(quality, technical)

    result = _finalize(request, discovery, technical, quality)

    stage = next(stage for stage in result.summary.stages if stage.stage_id == "csv_ingestion")
    assert stage.status is status
    assert stage.requirement is requirement
    assert result.summary.overall_status is expected


def test_valid_dq_report_is_preserved_and_referenced(tmp_path: Path) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    original_report = quality.dq_report

    result = _finalize(request, discovery, technical, quality)

    assert original_report is not None
    assert result.dq_report is original_report
    assert result.summary.dq_report_id == original_report.report_id
    assert result.summary.run_id == original_report.run_id
    assert result.summary.client_scope == original_report.client_scope


def test_orch_014_block_has_no_report_or_report_reference(tmp_path: Path) -> None:
    request, discovery, technical, quality = _execution(
        tmp_path,
        supplied={"customers", "subscriptions", "usage_monthly"},
        overrides={"usage_monthly": "subscription_id,usage_month,active_users\nS1,2025-02-01,-1\n"},
    )

    result = _finalize(request, discovery, technical, quality)

    assert quality.gate_passed is False
    assert result.dq_report is None
    assert result.summary.dq_report_id is None
    assert result.summary.stages[-2:] == (
        quality.referential_integrity_stage,
        quality.data_quality_stage,
    )


def test_finalizer_does_not_invoke_discovery_or_processing_components(tmp_path: Path) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    with (
        patch("nowa_customer_intelligence.pipeline.discovery.discover_datasets") as discover_spy,
        patch("nowa_customer_intelligence.pipeline.technical.run_technical_pipeline") as tech_spy,
        patch(
            "nowa_customer_intelligence.pipeline.quality.validate_referential_integrity"
        ) as ri_spy,
        patch("nowa_customer_intelligence.pipeline.quality.validate_data_quality") as dq_spy,
        patch(
            "nowa_customer_intelligence.data.validation.validator.validate_temporal_consistency"
        ) as tc_spy,
    ):
        _finalize(request, discovery, technical, quality)

    discover_spy.assert_not_called()
    tech_spy.assert_not_called()
    ri_spy.assert_not_called()
    dq_spy.assert_not_called()
    tc_spy.assert_not_called()


def test_inconsistent_discovery_presence_is_rejected(tmp_path: Path) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    presence = dict(discovery.dataset_presence)
    presence["invoices"] = True
    contradictory_discovery = replace(discovery, dataset_presence=presence)
    contradictory_technical = replace(technical, discovery=contradictory_discovery)
    contradictory_quality = _relink_quality(quality, contradictory_technical)

    with pytest.raises(ValueError, match="dataset presence does not match"):
        _finalize(request, contradictory_discovery, contradictory_technical, contradictory_quality)


def test_technical_result_must_reference_exact_discovery_result(tmp_path: Path) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    another_discovery = replace(discovery, dataset_presence=dict(discovery.dataset_presence))

    with pytest.raises(ValueError, match="does not reference the supplied discovery"):
        _finalize(request, another_discovery, technical, quality)


def test_quality_result_must_reference_exact_request_and_technical_result(
    tmp_path: Path,
) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    copied_request = replace(request)
    with pytest.raises(ValueError, match="does not reference the supplied request"):
        _finalize(copied_request, discovery, technical, quality)

    other_technical = replace(technical)
    with pytest.raises(ValueError, match="does not reference the supplied technical"):
        _finalize(request, discovery, other_technical, quality)


@pytest.mark.parametrize("field", ["run_id", "client_scope"])
def test_mismatched_quality_request_context_is_rejected(tmp_path: Path, field: str) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    altered_request = replace(request, **{field: f"other-{field}"})
    altered_quality = object.__new__(type(quality))
    for name in (
        "technical_result",
        "gate_passed",
        "referential_integrity_stage",
        "data_quality_stage",
        "ri_findings",
        "dq_report",
    ):
        object.__setattr__(altered_quality, name, getattr(quality, name))
    object.__setattr__(altered_quality, "request", altered_request)

    with pytest.raises(ValueError, match="quality_result .* does not match"):
        _finalize(request, discovery, technical, altered_quality)


@pytest.mark.parametrize("malformation", ["duplicate", "missing"])
def test_duplicate_or_missing_upstream_stage_results_are_rejected(
    tmp_path: Path,
    malformation: str,
) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    malformed = object.__new__(TechnicalPipelineResult)
    object.__setattr__(malformed, "discovery", discovery)
    object.__setattr__(malformed, "normalized_datasets", technical.normalized_datasets)
    object.__setattr__(malformed, "schema_validated_datasets", technical.schema_validated_datasets)
    stages = technical.stage_results
    if malformation == "duplicate":
        stages = (stages[0], stages[1], stages[1], stages[3])
    else:
        stages = stages[:3]
    object.__setattr__(malformed, "stage_results", stages)
    malformed_quality = replace(quality, technical_result=malformed)

    with pytest.raises(ValueError, match="duplicate|missing"):
        _finalize(request, discovery, malformed, malformed_quality)


def test_upstream_stage_objects_and_quality_result_remain_unchanged(tmp_path: Path) -> None:
    request, discovery, technical, quality = _execution(tmp_path)
    old_statuses = tuple(
        (stage.stage_id, stage.status, stage.requirement, stage.dataset_results)
        for stage in (
            discovery.stage_result,
            *technical.stage_results,
            quality.referential_integrity_stage,
            quality.data_quality_stage,
        )
    )

    result = _finalize(request, discovery, technical, quality)

    new_statuses = tuple(
        (stage.stage_id, stage.status, stage.requirement, stage.dataset_results)
        for stage in result.summary.stages
    )
    assert new_statuses == old_statuses
    with pytest.raises(FrozenInstanceError):
        quality.gate_passed = False  # type: ignore[misc]
