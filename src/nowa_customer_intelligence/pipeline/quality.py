"""Orchestrate Referential Integrity and Data Quality after technical validation."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualityReport,
    RuleExecutionResult,
)
from nowa_customer_intelligence.data.validation.referential_integrity import (
    validate_referential_integrity,
)
from nowa_customer_intelligence.data.validation.validator import validate_data_quality
from nowa_customer_intelligence.pipeline.models import (
    DatasetStageResult,
    PipelineExecutionRequest,
    PipelineWorkflow,
    StageExecutionResult,
    StageExecutionStatus,
    StageRequirement,
)
from nowa_customer_intelligence.pipeline.technical import TechnicalPipelineResult

_DATASETS = (
    "customers",
    "subscriptions",
    "subscription_snapshots",
    "usage_monthly",
    "invoices",
)
_REQUIRED_BY_WORKFLOW = {
    PipelineWorkflow.BASIC: frozenset({"customers", "subscriptions"}),
    PipelineWorkflow.TEMPORAL: frozenset({"customers", "subscriptions", "subscription_snapshots"}),
}


@dataclass(frozen=True)
class QualityOrchestrationResult:
    """Immutable RI/DQ outcomes retaining the originating request and technical result."""

    request: PipelineExecutionRequest
    technical_result: TechnicalPipelineResult
    gate_passed: bool
    referential_integrity_stage: StageExecutionResult
    data_quality_stage: StageExecutionResult
    ri_findings: tuple[DataQualityFinding, ...]
    dq_report: DataQualityReport | None

    def __post_init__(self) -> None:
        if type(self.request) is not PipelineExecutionRequest:
            raise TypeError("request must be a PipelineExecutionRequest")
        if type(self.technical_result) is not TechnicalPipelineResult:
            raise TypeError("technical_result must be a TechnicalPipelineResult")
        if not isinstance(self.gate_passed, bool):
            raise TypeError("gate_passed must be a boolean")
        for field_name in ("referential_integrity_stage", "data_quality_stage"):
            if type(getattr(self, field_name)) is not StageExecutionResult:
                raise TypeError(f"{field_name} must be a StageExecutionResult")
        if self.referential_integrity_stage.stage_id != "referential_integrity":
            raise ValueError("referential_integrity_stage has an invalid stage_id")
        if self.data_quality_stage.stage_id != "data_quality":
            raise ValueError("data_quality_stage has an invalid stage_id")
        findings = tuple(self.ri_findings)
        if any(type(finding) is not DataQualityFinding for finding in findings):
            raise TypeError("ri_findings must contain DataQualityFinding values")
        object.__setattr__(self, "ri_findings", findings)

        if not self.gate_passed:
            if (
                self.referential_integrity_stage.status is not StageExecutionStatus.BLOCKED
                or self.data_quality_stage.status is not StageExecutionStatus.BLOCKED
            ):
                raise ValueError("a failed schema gate requires both RI and DQ to be BLOCKED")
            if self.dq_report is not None:
                raise ValueError("a failed schema gate cannot contain a DQ Report")
            if self.ri_findings:
                raise ValueError("a failed schema gate cannot contain RI findings")
            return

        if self.referential_integrity_stage.status not in {
            StageExecutionStatus.SUCCEEDED,
            StageExecutionStatus.FAILED,
        }:
            raise ValueError("RI must succeed or fail after the schema gate passes")
        if self.data_quality_stage.status not in {
            StageExecutionStatus.SUCCEEDED,
            StageExecutionStatus.FAILED,
            StageExecutionStatus.BLOCKED,
        }:
            raise ValueError("DQ must succeed, fail, or be blocked after the schema gate passes")
        if self.referential_integrity_stage.status is StageExecutionStatus.FAILED:
            if self.ri_findings:
                raise ValueError("failed RI execution cannot contain findings")
            if self.data_quality_stage.status is not StageExecutionStatus.BLOCKED:
                raise ValueError("DQ must be BLOCKED when RI execution fails")
            if self.dq_report is not None:
                raise ValueError("an RI execution failure cannot contain a DQ Report")
        elif self.data_quality_stage.status is StageExecutionStatus.SUCCEEDED:
            if self.referential_integrity_stage.status is not StageExecutionStatus.SUCCEEDED:
                raise ValueError("a successful DQ stage requires successful RI execution")
            if type(self.dq_report) is not DataQualityReport:
                raise ValueError("a successful DQ stage must contain a DataQualityReport")
        elif self.dq_report is not None:
            raise ValueError("a failed or blocked DQ stage cannot contain a DQ Report")

        if self.dq_report is not None:
            if self.dq_report.run_id != self.request.run_id:
                raise ValueError("dq_report.run_id must match request.run_id")
            if self.dq_report.client_scope != self.request.client_scope:
                raise ValueError("dq_report.client_scope must match request.client_scope")
            if self.dq_report.findings[: len(self.ri_findings)] != self.ri_findings:
                raise ValueError("DQ Report must preserve the original RI findings")


def _dataset_requirement(dataset: str, workflow: PipelineWorkflow) -> StageRequirement:
    if dataset in _REQUIRED_BY_WORKFLOW[workflow]:
        return StageRequirement.REQUIRED
    return StageRequirement.OPTIONAL


def _schema_gate_failure(
    request: PipelineExecutionRequest,
    technical_result: TechnicalPipelineResult,
) -> tuple[str, str] | None:
    presence = technical_result.discovery.dataset_presence
    expected_presence = {name: name in request.dataset_sources for name in _DATASETS}
    if dict(presence) != expected_presence:
        return (
            "DISCOVERY_MISMATCH",
            "The technical result does not match the request's discovered dataset mapping.",
        )

    required = _REQUIRED_BY_WORKFLOW[request.workflow]
    missing_required = next(
        (name for name in _DATASETS if name in required and not presence[name]), None
    )
    if missing_required is not None:
        return (
            "REQUIRED_DATASET_MISSING",
            f"Required dataset {missing_required!r} is unavailable; RI and DQ are blocked.",
        )

    schema_stages = [
        stage for stage in technical_result.stage_results if stage.stage_id == "schema_validation"
    ]
    if len(schema_stages) != 1:
        return (
            "SCHEMA_OUTCOME_MISSING",
            "Schema validation outcomes are incomplete; RI and DQ are blocked.",
        )

    supplied = {name for name, is_present in presence.items() if is_present}
    outcomes = {outcome.dataset: outcome for outcome in schema_stages[0].dataset_results}
    unexpected_outcome = next((name for name in outcomes if name not in supplied), None)
    if unexpected_outcome is not None:
        return (
            "SCHEMA_OUTCOME_MISMATCH",
            "Schema outcomes contain a dataset not supplied in the request; RI and DQ are blocked.",
        )
    missing_outcome = next((name for name in _DATASETS if name in supplied - outcomes.keys()), None)
    if missing_outcome is not None:
        return (
            "SCHEMA_OUTCOME_MISSING",
            f"Schema outcome for supplied dataset {missing_outcome!r} is missing; "
            "RI and DQ are blocked.",
        )
    invalid_outcome = next(
        (
            name
            for name in _DATASETS
            if name in supplied and outcomes[name].status is not StageExecutionStatus.SUCCEEDED
        ),
        None,
    )
    if invalid_outcome is not None:
        return (
            "SCHEMA_VALIDATION_FAILED",
            f"Supplied dataset {invalid_outcome!r} did not pass schema validation; "
            "RI and DQ are blocked.",
        )

    validated = technical_result.schema_validated_datasets
    missing_frame = next((name for name in _DATASETS if name in supplied - validated.keys()), None)
    if missing_frame is not None:
        return (
            "VALIDATED_DATASET_MISSING",
            f"Validated frame for supplied dataset {missing_frame!r} is missing; "
            "RI and DQ are blocked.",
        )
    unexpected_frame = next((name for name in validated if name not in supplied), None)
    if unexpected_frame is not None:
        return (
            "DISCOVERY_MISMATCH",
            "The technical result contains a dataset not supplied in the request; "
            "RI and DQ are blocked.",
        )
    return None


def _blocked_stage(stage_id: str, code: str, message: str) -> StageExecutionResult:
    return StageExecutionResult(
        stage_id=stage_id,
        status=StageExecutionStatus.BLOCKED,
        requirement=StageRequirement.REQUIRED,
        error_code=code,
        message=message,
    )


def _failed_stage(
    stage_id: str, code: str, component: str, error: Exception
) -> StageExecutionResult:
    return StageExecutionResult(
        stage_id=stage_id,
        status=StageExecutionStatus.FAILED,
        requirement=StageRequirement.REQUIRED,
        error_code=code,
        message=f"{component} execution failed ({type(error).__name__}).",
    )


def _stage_dataset_results(
    findings: tuple[DataQualityFinding, ...],
    workflow: PipelineWorkflow,
    component: str,
) -> tuple[DatasetStageResult, ...]:
    """Report datasets attributed to evaluated findings, not rule-level pass/fail."""
    evaluated_datasets = {
        dataset
        for finding in findings
        if finding.result in {RuleExecutionResult.PASS, RuleExecutionResult.FAIL}
        for dataset in finding.datasets
    }
    return tuple(
        DatasetStageResult(
            dataset=dataset,
            status=StageExecutionStatus.SUCCEEDED,
            requirement=_dataset_requirement(dataset, workflow),
            message=(
                f"{component} executed for this dataset; rule-level outcomes remain in findings."
            ),
        )
        for dataset in _DATASETS
        if dataset in evaluated_datasets
    )


def _succeeded_stage(
    stage_id: str,
    findings: tuple[DataQualityFinding, ...],
    workflow: PipelineWorkflow,
    component: str,
) -> StageExecutionResult:
    return StageExecutionResult(
        stage_id=stage_id,
        status=StageExecutionStatus.SUCCEEDED,
        requirement=StageRequirement.REQUIRED,
        dataset_results=_stage_dataset_results(findings, workflow, component),
    )


def orchestrate_referential_integrity_and_data_quality(
    request: PipelineExecutionRequest,
    technical_result: TechnicalPipelineResult,
) -> QualityOrchestrationResult:
    """Run RI once, then the DQ coordinator, only after the ORCH-014 schema gate passes."""
    if type(request) is not PipelineExecutionRequest:
        raise TypeError("request must be a PipelineExecutionRequest")
    if type(technical_result) is not TechnicalPipelineResult:
        raise TypeError("technical_result must be a TechnicalPipelineResult")

    gate_failure = _schema_gate_failure(request, technical_result)
    if gate_failure is not None:
        code, message = gate_failure
        return QualityOrchestrationResult(
            request=request,
            technical_result=technical_result,
            gate_passed=False,
            referential_integrity_stage=_blocked_stage("referential_integrity", code, message),
            data_quality_stage=_blocked_stage("data_quality", code, message),
            ri_findings=(),
            dq_report=None,
        )

    datasets: Mapping[str, pd.DataFrame] = technical_result.schema_validated_datasets
    try:
        ri_findings = validate_referential_integrity(datasets)
    except Exception as exc:
        ri_stage = _failed_stage(
            "referential_integrity", "RI_EXECUTION_FAILED", "Referential Integrity", exc
        )
        dq_stage = _blocked_stage(
            "data_quality",
            "RI_EXECUTION_FAILED",
            "Data Quality was blocked because Referential Integrity did not complete.",
        )
        return QualityOrchestrationResult(
            request,
            technical_result,
            True,
            ri_stage,
            dq_stage,
            (),
            None,
        )

    if (
        type(ri_findings) is not tuple
        or len(ri_findings) != 4
        or any(type(finding) is not DataQualityFinding for finding in ri_findings)
        or tuple(finding.rule_id for finding in ri_findings)
        != ("RI-001", "RI-002", "RI-003", "RI-004")
    ):
        error = TypeError("RI returned an invalid findings sequence")
        ri_stage = _failed_stage(
            "referential_integrity", "RI_EXECUTION_FAILED", "Referential Integrity", error
        )
        dq_stage = _blocked_stage(
            "data_quality",
            "RI_EXECUTION_FAILED",
            "Data Quality was blocked because Referential Integrity returned an invalid result.",
        )
        return QualityOrchestrationResult(
            request,
            technical_result,
            True,
            ri_stage,
            dq_stage,
            (),
            None,
        )

    ri_stage = _succeeded_stage(
        "referential_integrity", ri_findings, request.workflow, "Referential Integrity"
    )
    try:
        report = validate_data_quality(
            datasets=datasets,
            ri_findings=ri_findings,
            run_id=request.run_id,
            client_scope=request.client_scope,
        )
    except Exception as exc:
        dq_stage = _failed_stage("data_quality", "DQ_EXECUTION_FAILED", "Data Quality", exc)
        return QualityOrchestrationResult(
            request,
            technical_result,
            True,
            ri_stage,
            dq_stage,
            ri_findings,
            None,
        )

    if type(report) is not DataQualityReport:
        error = TypeError("DQ coordinator returned an invalid report")
        dq_stage = _failed_stage("data_quality", "DQ_EXECUTION_FAILED", "Data Quality", error)
        return QualityOrchestrationResult(
            request,
            technical_result,
            True,
            ri_stage,
            dq_stage,
            ri_findings,
            None,
        )
    if report.run_id != request.run_id or report.client_scope != request.client_scope:
        error = ValueError("DQ report metadata did not match the request")
        dq_stage = _failed_stage(
            "data_quality", "DQ_REPORT_CONTEXT_MISMATCH", "Data Quality", error
        )
        return QualityOrchestrationResult(
            request,
            technical_result,
            True,
            ri_stage,
            dq_stage,
            ri_findings,
            None,
        )
    if report.findings[: len(ri_findings)] != ri_findings:
        error = ValueError("DQ report did not preserve the original RI findings")
        dq_stage = _failed_stage("data_quality", "DQ_REPORT_INVALID", "Data Quality", error)
        return QualityOrchestrationResult(
            request,
            technical_result,
            True,
            ri_stage,
            dq_stage,
            ri_findings,
            None,
        )

    dq_stage = _succeeded_stage("data_quality", report.findings, request.workflow, "Data Quality")
    return QualityOrchestrationResult(
        request,
        technical_result,
        True,
        ri_stage,
        dq_stage,
        ri_findings,
        report,
    )
