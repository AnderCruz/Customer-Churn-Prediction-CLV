"""Unit tests for ORCH-014, Referential Integrity, and DQ orchestration."""

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import patch

import pytest

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualityReport,
    DataQualityValidationError,
    RuleExecutionResult,
)
from nowa_customer_intelligence.data.validation.reporting import build_data_quality_report
from nowa_customer_intelligence.data.validation.temporal_consistency import (
    validate_temporal_consistency,
)
from nowa_customer_intelligence.pipeline import (
    PipelineExecutionRequest,
    PipelineWorkflow,
    StageExecutionResult,
    StageExecutionStatus,
    StageRequirement,
    TechnicalPipelineResult,
    discover_datasets,
    orchestrate_referential_integrity_and_data_quality,
    run_technical_pipeline,
)
from nowa_customer_intelligence.pipeline import quality as quality_module

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


def _build(
    tmp_path: Path,
    supplied: set[str] | None = None,
    *,
    workflow: PipelineWorkflow = PipelineWorkflow.BASIC,
    overrides: dict[str, str] | None = None,
) -> tuple[PipelineExecutionRequest, TechnicalPipelineResult]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    names = supplied if supplied is not None else {"customers", "subscriptions"}
    sources = {}
    for name in names:
        path = tmp_path / f"{name}.csv"
        path.write_text((overrides or {}).get(name, _CSV[name]), encoding="utf-8")
        sources[name] = path
    request = PipelineExecutionRequest(
        run_id="run-pes-4b-4",
        client_scope="client-pseudonym-1",
        workflow=workflow,
        dataset_sources=sources,
        execution_intent="dq_validation",
    )
    discovery = discover_datasets(request)
    return request, run_technical_pipeline(request, discovery)


def _run(request: PipelineExecutionRequest, technical: TechnicalPipelineResult):
    return orchestrate_referential_integrity_and_data_quality(request, technical)


def _schema_stage(technical: TechnicalPipelineResult) -> StageExecutionResult:
    return next(stage for stage in technical.stage_results if stage.stage_id == "schema_validation")


def _evaluated_report(
    findings: tuple[DataQualityFinding, ...], *, run_id: str, client_scope: str
) -> DataQualityReport:
    return build_data_quality_report(
        findings=findings,
        dataset_presence={name: name in {"customers", "subscriptions"} for name in _CSV},
        run_id=run_id,
        client_scope=client_scope,
    )


def test_complete_schema_valid_mapping_runs_ri_then_dq_once_and_builds_report(
    tmp_path: Path,
) -> None:
    request, technical = _build(tmp_path)
    real_ri = quality_module.validate_referential_integrity
    real_dq = quality_module.validate_data_quality
    with (
        patch.object(quality_module, "validate_referential_integrity", wraps=real_ri) as ri_spy,
        patch.object(quality_module, "validate_data_quality", wraps=real_dq) as dq_spy,
        patch(
            "nowa_customer_intelligence.data.validation.validator.validate_temporal_consistency",
            wraps=validate_temporal_consistency,
        ) as tc_spy,
    ):
        result = _run(request, technical)

    ri_spy.assert_called_once_with(technical.schema_validated_datasets)
    dq_spy.assert_called_once()
    tc_spy.assert_called_once_with(technical.schema_validated_datasets)
    assert dq_spy.call_args.kwargs["datasets"] is technical.schema_validated_datasets
    assert dq_spy.call_args.kwargs["ri_findings"] is result.ri_findings
    assert result.gate_passed is True
    assert result.referential_integrity_stage.status is StageExecutionStatus.SUCCEEDED
    assert result.data_quality_stage.status is StageExecutionStatus.SUCCEEDED
    assert result.dq_report is not None
    assert result.dq_report.findings[:4] == result.ri_findings
    assert result.dq_report.run_id == request.run_id
    assert result.dq_report.client_scope == request.client_scope


@pytest.mark.parametrize(
    ("supplied", "workflow", "overrides", "expected_code"),
    [
        (
            {"subscriptions"},
            PipelineWorkflow.BASIC,
            None,
            "REQUIRED_DATASET_MISSING",
        ),
        (
            {"customers", "subscriptions"},
            PipelineWorkflow.BASIC,
            {"customers": "customer_id,created_at\nC1,2025-01-01\nC1,2025-01-02\n"},
            "SCHEMA_VALIDATION_FAILED",
        ),
        (
            {"customers", "subscriptions", "usage_monthly"},
            PipelineWorkflow.BASIC,
            {"usage_monthly": "subscription_id,usage_month,active_users\nS1,2025-02-01,-1\n"},
            "SCHEMA_VALIDATION_FAILED",
        ),
    ],
)
def test_failed_orch_014_gate_blocks_ri_and_dq_without_calling_components(
    tmp_path: Path,
    supplied: set[str],
    workflow: PipelineWorkflow,
    overrides: dict[str, str] | None,
    expected_code: str,
) -> None:
    request, technical = _build(tmp_path, supplied, workflow=workflow, overrides=overrides)
    with (
        patch.object(
            quality_module,
            "validate_referential_integrity",
            side_effect=AssertionError("RI must not execute"),
        ) as ri_spy,
        patch.object(
            quality_module,
            "validate_data_quality",
            side_effect=AssertionError("DQ must not execute"),
        ) as dq_spy,
    ):
        result = _run(request, technical)

    ri_spy.assert_not_called()
    dq_spy.assert_not_called()
    assert result.gate_passed is False
    assert result.referential_integrity_stage.status is StageExecutionStatus.BLOCKED
    assert result.data_quality_stage.status is StageExecutionStatus.BLOCKED
    assert result.referential_integrity_stage.error_code == expected_code
    assert result.data_quality_stage.error_code == expected_code
    assert result.dq_report is None
    assert result.technical_result is technical
    assert result.ri_findings == ()


def test_missing_optional_datasets_do_not_block_and_are_reported_absent(
    tmp_path: Path,
) -> None:
    request, technical = _build(tmp_path)

    result = _run(request, technical)

    assert result.gate_passed
    assert result.dq_report is not None
    assert result.dq_report.dataset_presence["usage_monthly"] is False
    assert result.dq_report.dataset_presence["invoices"] is False
    assert result.referential_integrity_stage.status is StageExecutionStatus.SUCCEEDED


def test_temporal_workflow_requires_snapshot_dataset(tmp_path: Path) -> None:
    request, technical = _build(
        tmp_path,
        {"customers", "subscriptions"},
        workflow=PipelineWorkflow.TEMPORAL,
    )
    with patch.object(quality_module, "validate_referential_integrity") as ri_spy:
        result = _run(request, technical)

    ri_spy.assert_not_called()
    assert result.gate_passed is False
    assert result.referential_integrity_stage.error_code == "REQUIRED_DATASET_MISSING"
    assert result.dq_report is None


def test_supplied_dataset_missing_its_schema_outcome_blocks_gate(
    tmp_path: Path,
) -> None:
    request, technical = _build(tmp_path)
    schema_stage = _schema_stage(technical)
    altered_stage = replace(
        schema_stage,
        dataset_results=tuple(
            outcome
            for outcome in schema_stage.dataset_results
            if outcome.dataset != "subscriptions"
        ),
    )
    altered = replace(
        technical,
        stage_results=tuple(
            altered_stage if stage.stage_id == "schema_validation" else stage
            for stage in technical.stage_results
        ),
    )

    result = _run(request, altered)

    assert result.gate_passed is False
    assert result.referential_integrity_stage.error_code == "SCHEMA_OUTCOME_MISSING"
    assert result.dq_report is None


def test_supplied_dataset_missing_validated_frame_blocks_gate(tmp_path: Path) -> None:
    request, technical = _build(tmp_path)
    altered = replace(
        technical,
        schema_validated_datasets={"customers": technical.schema_validated_datasets["customers"]},
    )

    result = _run(request, altered)

    assert result.gate_passed is False
    assert result.referential_integrity_stage.error_code == "VALIDATED_DATASET_MISSING"
    assert result.dq_report is None


def test_failing_ri_rule_is_preserved_but_successful_execution_stage_succeeds(
    tmp_path: Path,
) -> None:
    request, technical = _build(
        tmp_path,
        overrides={
            "subscriptions": "subscription_id,customer_id,start_date,subscription_status\n"
            "S1,unknown-customer,2025-01-01,active\n"
        },
    )

    result = _run(request, technical)

    assert result.referential_integrity_stage.status is StageExecutionStatus.SUCCEEDED
    assert result.ri_findings[0].rule_id == "RI-001"
    assert result.ri_findings[0].result is RuleExecutionResult.FAIL
    assert result.dq_report is not None
    assert result.dq_report.findings[0] == result.ri_findings[0]
    assert result.dq_report.summary.blocked


def test_ri_execution_error_is_safe_and_blocks_dq(tmp_path: Path) -> None:
    request, technical = _build(tmp_path)
    with (
        patch.object(
            quality_module,
            "validate_referential_integrity",
            side_effect=DataQualityValidationError("private/path raw-value"),
        ) as ri_spy,
        patch.object(quality_module, "validate_data_quality") as dq_spy,
    ):
        result = _run(request, technical)

    ri_spy.assert_called_once()
    dq_spy.assert_not_called()
    assert result.referential_integrity_stage.status is StageExecutionStatus.FAILED
    assert result.data_quality_stage.status is StageExecutionStatus.BLOCKED
    assert result.dq_report is None
    assert "private/path" not in str(result.referential_integrity_stage)
    assert "raw-value" not in str(result.referential_integrity_stage)


def test_dq_execution_error_preserves_original_ri_findings_without_report(
    tmp_path: Path,
) -> None:
    request, technical = _build(tmp_path)
    with patch.object(
        quality_module,
        "validate_data_quality",
        side_effect=DataQualityValidationError("private/path raw-value"),
    ) as dq_spy:
        result = _run(request, technical)

    dq_spy.assert_called_once()
    assert result.referential_integrity_stage.status is StageExecutionStatus.SUCCEEDED
    assert result.data_quality_stage.status is StageExecutionStatus.FAILED
    assert result.dq_report is None
    assert len(result.ri_findings) == 4
    assert "private/path" not in str(result.data_quality_stage)
    assert "raw-value" not in str(result.data_quality_stage)


def test_dq_report_returned_by_coordinator_is_not_rebuilt(tmp_path: Path) -> None:
    request, technical = _build(tmp_path)
    ri_findings = quality_module.validate_referential_integrity(technical.schema_validated_datasets)
    report = _evaluated_report(
        ri_findings, run_id=request.run_id, client_scope=request.client_scope
    )
    with patch.object(quality_module, "validate_data_quality", return_value=report) as dq_spy:
        result = _run(request, technical)

    dq_spy.assert_called_once()
    assert result.dq_report is report


def test_result_preserves_technical_outcomes_and_is_frozen(tmp_path: Path) -> None:
    request, technical = _build(tmp_path)

    result = _run(request, technical)

    assert result.technical_result is technical
    assert result.technical_result.stage_results is technical.stage_results
    assert isinstance(result.ri_findings, tuple)
    with pytest.raises(FrozenInstanceError):
        result.gate_passed = False  # type: ignore[misc]


def test_result_rejects_report_when_gate_was_blocked(tmp_path: Path) -> None:
    request, technical = _build(tmp_path)
    blocked = StageExecutionResult(
        stage_id="referential_integrity",
        status=StageExecutionStatus.BLOCKED,
        requirement=StageRequirement.REQUIRED,
    )
    dq_blocked = replace(blocked, stage_id="data_quality")
    report = _evaluated_report((), run_id=request.run_id, client_scope=request.client_scope)

    with pytest.raises(ValueError, match="failed schema gate cannot contain"):
        quality_module.QualityOrchestrationResult(
            request,
            technical,
            False,
            blocked,
            dq_blocked,
            (),
            report,
        )


def test_result_rejects_cross_context_report(tmp_path: Path) -> None:
    request, technical = _build(tmp_path)
    ri_findings = quality_module.validate_referential_integrity(technical.schema_validated_datasets)
    report = _evaluated_report(ri_findings, run_id="other-run", client_scope=request.client_scope)
    ri_stage = StageExecutionResult(
        stage_id="referential_integrity",
        status=StageExecutionStatus.SUCCEEDED,
        requirement=StageRequirement.REQUIRED,
    )
    dq_stage = StageExecutionResult(
        stage_id="data_quality",
        status=StageExecutionStatus.SUCCEEDED,
        requirement=StageRequirement.REQUIRED,
    )

    with pytest.raises(ValueError, match="dq_report.run_id"):
        quality_module.QualityOrchestrationResult(
            request,
            technical,
            True,
            ri_stage,
            dq_stage,
            ri_findings,
            report,
        )
