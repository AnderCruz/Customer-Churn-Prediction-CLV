"""Unit tests for immutable Pipeline Execution Summary models."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType

import pytest

from nowa_customer_intelligence.data.validation.models import DataQualityReport
from nowa_customer_intelligence.pipeline import (
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


def make_stage(**updates: object) -> StageExecutionResult:
    """Build a valid stage result with selected overrides."""
    values: dict[str, object] = {
        "stage_id": "csv_ingestion",
        "status": StageExecutionStatus.SUCCEEDED,
        "requirement": StageRequirement.REQUIRED,
    }
    values.update(updates)
    return StageExecutionResult(**values)  # type: ignore[arg-type]


def make_summary(**updates: object) -> PipelineExecutionSummary:
    """Build a valid summary with selected overrides."""
    values: dict[str, object] = {
        "summary_id": "summary-1",
        "run_id": "run-1",
        "client_scope": "client-pseudonym-1",
        "created_at_utc": datetime(2026, 11, 16, tzinfo=UTC),
        "overall_status": PipelineOverallStatus.SUCCEEDED,
        "stages": (),
        "dataset_presence": {"customers": True},
    }
    values.update(updates)
    return PipelineExecutionSummary(**values)  # type: ignore[arg-type]


def test_enums_have_exact_approved_values_and_distinct_types() -> None:
    assert [item.value for item in StageExecutionStatus] == [
        "SUCCEEDED",
        "FAILED",
        "PARTIAL",
        "BLOCKED",
        "SKIPPED",
        "NOT_APPLICABLE",
        "NOT_IMPLEMENTED",
    ]
    assert [item.value for item in PipelineOverallStatus] == [
        "SUCCEEDED",
        "PARTIAL",
        "FAILED",
        "BLOCKED",
    ]
    assert [item.value for item in StageRequirement] == [
        "REQUIRED",
        "OPTIONAL",
        "NOT_APPLICABLE",
    ]
    assert not isinstance(StageExecutionStatus.SUCCEEDED, PipelineOverallStatus)
    assert not isinstance(StageRequirement.REQUIRED, StageExecutionStatus)


def test_stage_result_constructs_with_optional_values_omitted() -> None:
    stage = make_stage()

    assert stage.stage_id == "csv_ingestion"
    assert stage.started_at_utc is None
    assert stage.completed_at_utc is None
    assert stage.records_received is None
    assert stage.records_processed is None
    assert stage.records_rejected is None
    assert stage.error_code is None
    assert stage.message is None
    assert stage.dataset_results == ()


def test_stage_result_existing_positional_constructor_remains_compatible() -> None:
    stage = StageExecutionResult(
        "csv_ingestion",
        StageExecutionStatus.SUCCEEDED,
        StageRequirement.REQUIRED,
    )

    assert stage.dataset_results == ()


def test_stage_result_defensively_copies_immutable_dataset_outcomes() -> None:
    dataset_result = DatasetStageResult(
        dataset="customers",
        status=StageExecutionStatus.SUCCEEDED,
        requirement=StageRequirement.REQUIRED,
        records_received=3,
        records_processed=3,
    )
    source = [dataset_result]

    stage = make_stage(dataset_results=source)
    source.clear()

    assert stage.dataset_results == (dataset_result,)
    assert isinstance(stage.dataset_results, tuple)
    with pytest.raises(FrozenInstanceError):
        dataset_result.status = StageExecutionStatus.FAILED  # type: ignore[misc]


@pytest.mark.parametrize("value", ["results", b"results", [object()]])
def test_stage_result_rejects_invalid_dataset_outcome_sequences(value: object) -> None:
    with pytest.raises(TypeError, match="dataset_results"):
        make_stage(dataset_results=value)


def test_stage_result_rejects_duplicate_dataset_outcomes() -> None:
    outcome = DatasetStageResult(
        dataset="customers",
        status=StageExecutionStatus.SUCCEEDED,
        requirement=StageRequirement.REQUIRED,
    )

    with pytest.raises(ValueError, match="dataset names must be unique"):
        make_stage(dataset_results=[outcome, outcome])


@pytest.mark.parametrize(
    ("dataset", "status", "requirement", "exception"),
    [
        (" ", StageExecutionStatus.SUCCEEDED, StageRequirement.REQUIRED, ValueError),
        ("customers", "SUCCEEDED", StageRequirement.REQUIRED, TypeError),
        (
            "customers",
            StageExecutionStatus.SUCCEEDED,
            StageRequirement.NOT_APPLICABLE,
            ValueError,
        ),
    ],
)
def test_dataset_stage_result_validates_identity_and_status(
    dataset: str,
    status: object,
    requirement: StageRequirement,
    exception: type[Exception],
) -> None:
    with pytest.raises(exception):
        DatasetStageResult(dataset=dataset, status=status, requirement=requirement)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_stage_result_rejects_empty_or_whitespace_stage_id(value: str) -> None:
    with pytest.raises(ValueError, match="stage_id"):
        make_stage(stage_id=value)


@pytest.mark.parametrize(
    ("field", "value", "expected_exception"),
    [
        ("stage_id", 1, TypeError),
        ("status", "SUCCEEDED", TypeError),
        ("status", PipelineOverallStatus.SUCCEEDED, TypeError),
        ("requirement", "REQUIRED", TypeError),
        ("requirement", StageExecutionStatus.SUCCEEDED, TypeError),
    ],
)
def test_stage_result_rejects_invalid_identifier_or_enum(
    field: str, value: object, expected_exception: type[Exception]
) -> None:
    with pytest.raises(expected_exception):
        make_stage(**{field: value})


@pytest.mark.parametrize("field", ["started_at_utc", "completed_at_utc"])
def test_stage_result_rejects_naive_timestamps(field: str) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_stage(**{field: datetime(2026, 11, 16)})


@pytest.mark.parametrize("field", ["started_at_utc", "completed_at_utc"])
def test_stage_result_normalizes_timestamp_to_utc(field: str) -> None:
    timestamp = datetime(2026, 11, 16, 7, 30, tzinfo=timezone(timedelta(hours=-5)))

    stage = make_stage(**{field: timestamp})

    assert getattr(stage, field) == datetime(2026, 11, 16, 12, 30, tzinfo=UTC)
    assert getattr(stage, field).tzinfo is UTC


@pytest.mark.parametrize("field", ["started_at_utc", "completed_at_utc"])
def test_stage_result_accepts_none_timestamps(field: str) -> None:
    assert getattr(make_stage(**{field: None}), field) is None


def test_stage_result_rejects_completion_before_start() -> None:
    with pytest.raises(ValueError, match="cannot precede"):
        make_stage(
            started_at_utc=datetime(2026, 11, 16, 12, tzinfo=UTC),
            completed_at_utc=datetime(2026, 11, 16, 11, tzinfo=UTC),
        )


@pytest.mark.parametrize("field", ["records_received", "records_processed", "records_rejected"])
@pytest.mark.parametrize("value", [-1, -10, 1.5, "2", True, False])
def test_stage_result_rejects_invalid_counts(field: str, value: object) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        make_stage(**{field: value})


@pytest.mark.parametrize("field", ["records_received", "records_processed", "records_rejected"])
@pytest.mark.parametrize("value", [0, 12, None])
def test_stage_result_accepts_non_negative_or_unknown_counts(field: str, value: object) -> None:
    assert getattr(make_stage(**{field: value}), field) == value


@pytest.mark.parametrize(
    ("status", "requirement"),
    [
        (StageExecutionStatus.SUCCEEDED, StageRequirement.NOT_APPLICABLE),
        (StageExecutionStatus.NOT_APPLICABLE, StageRequirement.REQUIRED),
        (StageExecutionStatus.NOT_APPLICABLE, StageRequirement.OPTIONAL),
    ],
)
def test_stage_result_enforces_both_directions_of_not_applicable_consistency(
    status: StageExecutionStatus, requirement: StageRequirement
) -> None:
    with pytest.raises(ValueError, match="both be NOT_APPLICABLE"):
        make_stage(status=status, requirement=requirement)


def test_stage_result_accepts_consistent_not_applicable_values() -> None:
    stage = make_stage(
        status=StageExecutionStatus.NOT_APPLICABLE,
        requirement=StageRequirement.NOT_APPLICABLE,
    )

    assert stage.status is StageExecutionStatus.NOT_APPLICABLE
    assert stage.requirement is StageRequirement.NOT_APPLICABLE


@pytest.mark.parametrize("field", ["error_code", "message"])
def test_stage_result_rejects_non_string_optional_text(field: str) -> None:
    with pytest.raises(TypeError, match=field):
        make_stage(**{field: 1})


def test_stage_result_is_frozen() -> None:
    stage = make_stage()

    with pytest.raises(FrozenInstanceError):
        stage.status = StageExecutionStatus.FAILED  # type: ignore[misc]


def test_summary_constructs_with_empty_stages_and_optional_report_reference() -> None:
    summary = make_summary()

    assert summary.stages == ()
    assert summary.dq_report_id is None


@pytest.mark.parametrize("field", ["summary_id", "run_id", "client_scope"])
@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_summary_rejects_empty_or_whitespace_identifiers(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=field):
        make_summary(**{field: value})


@pytest.mark.parametrize(
    ("field", "value", "expected_exception"),
    [
        ("summary_id", None, TypeError),
        ("run_id", 1, TypeError),
        ("client_scope", [], TypeError),
        ("overall_status", "SUCCEEDED", TypeError),
        ("overall_status", StageExecutionStatus.SUCCEEDED, TypeError),
    ],
)
def test_summary_rejects_invalid_identifier_types_and_status(
    field: str, value: object, expected_exception: type[Exception]
) -> None:
    with pytest.raises(expected_exception):
        make_summary(**{field: value})


def test_summary_rejects_naive_creation_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        make_summary(created_at_utc=datetime(2026, 11, 16))


def test_summary_normalizes_creation_timestamp_to_utc() -> None:
    timestamp = datetime(2026, 11, 16, 7, 30, tzinfo=timezone(timedelta(hours=-5)))

    summary = make_summary(created_at_utc=timestamp)

    assert summary.created_at_utc == datetime(2026, 11, 16, 12, 30, tzinfo=UTC)
    assert summary.created_at_utc.tzinfo is UTC


def test_summary_rejects_wrong_creation_timestamp_type() -> None:
    with pytest.raises(TypeError, match="created_at_utc"):
        make_summary(created_at_utc="2026-11-16T00:00:00Z")


def test_summary_accepts_multiple_distinct_stage_results() -> None:
    stages = (make_stage(), make_stage(stage_id="schema_validation"))

    summary = make_summary(stages=stages)

    assert summary.stages == stages


def test_summary_converts_mutable_stage_sequence_to_defensive_tuple() -> None:
    stages = [make_stage()]

    summary = make_summary(stages=stages)
    stages.clear()

    assert isinstance(summary.stages, tuple)
    assert len(summary.stages) == 1


@pytest.mark.parametrize("stages", [[make_stage(), make_stage()], (make_stage(), make_stage())])
def test_summary_rejects_duplicate_stage_ids(stages: object) -> None:
    with pytest.raises(ValueError, match="unique"):
        make_summary(stages=stages)


@pytest.mark.parametrize("stages", [[object()], "csv_ingestion", [None]])
def test_summary_rejects_invalid_stage_collection(stages: object) -> None:
    with pytest.raises(TypeError, match="stages"):
        make_summary(stages=stages)


def test_summary_stage_tuple_is_immutable() -> None:
    summary = make_summary(stages=[make_stage()])

    with pytest.raises(AttributeError):
        summary.stages.append(make_stage(stage_id="other"))  # type: ignore[attr-defined]


def test_summary_defensively_copies_and_freezes_dataset_presence() -> None:
    source: dict[str, bool] = {"customers": True}

    summary = make_summary(dataset_presence=source)
    source["customers"] = False
    source["invoices"] = True

    assert isinstance(summary.dataset_presence, MappingProxyType)
    assert summary.dataset_presence == {"customers": True}
    with pytest.raises(TypeError):
        summary.dataset_presence["customers"] = False  # type: ignore[index]


@pytest.mark.parametrize("value", [[], {"customers": 1}, {"customers": "true"}, {1: True}])
def test_summary_rejects_invalid_dataset_presence_mapping(value: object) -> None:
    with pytest.raises(TypeError):
        make_summary(dataset_presence=value)


def test_summary_rejects_non_mapping_dataset_presence() -> None:
    with pytest.raises(TypeError, match="dataset_presence"):
        make_summary(dataset_presence=[("customers", True)])


@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_summary_rejects_empty_optional_dq_report_id(value: str) -> None:
    with pytest.raises(ValueError, match="dq_report_id"):
        make_summary(dq_report_id=value)


def test_summary_rejects_non_string_dq_report_id() -> None:
    with pytest.raises(TypeError, match="dq_report_id"):
        make_summary(dq_report_id=3)


def test_summary_is_frozen() -> None:
    summary = make_summary()

    with pytest.raises(FrozenInstanceError):
        summary.overall_status = PipelineOverallStatus.FAILED  # type: ignore[misc]


@pytest.mark.parametrize(
    ("overall_status", "stage_status"),
    [
        (PipelineOverallStatus.SUCCEEDED, StageExecutionStatus.FAILED),
        (PipelineOverallStatus.FAILED, StageExecutionStatus.SUCCEEDED),
        (PipelineOverallStatus.BLOCKED, StageExecutionStatus.NOT_IMPLEMENTED),
    ],
)
def test_summary_preserves_supplied_overall_status_without_aggregation(
    overall_status: PipelineOverallStatus, stage_status: StageExecutionStatus
) -> None:
    summary = make_summary(
        overall_status=overall_status,
        stages=(make_stage(status=stage_status),),
    )

    assert summary.overall_status is overall_status
    assert summary.stages[0].status is stage_status


def test_enum_classes_are_distinct_from_each_other() -> None:
    class OtherStatus(Enum):
        SUCCEEDED = "SUCCEEDED"

    with pytest.raises(TypeError, match="PipelineOverallStatus"):
        make_summary(overall_status=OtherStatus.SUCCEEDED)


def make_request(**updates: object) -> PipelineExecutionRequest:
    values: dict[str, object] = {
        "run_id": "run-1",
        "client_scope": "client-pseudonym-1",
        "workflow": PipelineWorkflow.BASIC,
        "dataset_sources": {"customers": Path("customers.csv")},
        "execution_intent": "technical_validation",
    }
    values.update(updates)
    return PipelineExecutionRequest(**values)  # type: ignore[arg-type]


def test_pipeline_request_requires_explicit_supported_workflow() -> None:
    assert [workflow.value for workflow in PipelineWorkflow] == ["BASIC", "TEMPORAL"]
    with pytest.raises(TypeError, match="workflow"):
        make_request(workflow="BASIC")
    with pytest.raises(TypeError, match="workflow"):
        PipelineExecutionRequest(
            run_id="run-1",
            client_scope="client-pseudonym-1",
            dataset_sources={},
            execution_intent="technical_validation",
        )  # type: ignore[call-arg]


@pytest.mark.parametrize("field", ["run_id", "client_scope", "execution_intent"])
@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_pipeline_request_rejects_blank_required_metadata(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=field):
        make_request(**{field: value})


def test_pipeline_request_preserves_metadata_and_defensively_freezes_sources() -> None:
    sources = {"customers": " ./customers.csv "}
    intent = "  caller-declared intent  "

    request = make_request(dataset_sources=sources, execution_intent=intent)
    sources["subscriptions"] = "subscriptions.csv"

    assert request.execution_intent == intent
    assert request.dataset_sources == {"customers": " ./customers.csv "}
    assert isinstance(request.dataset_sources, MappingProxyType)
    with pytest.raises(TypeError):
        request.dataset_sources["subscriptions"] = "subscriptions.csv"  # type: ignore[index]


@pytest.mark.parametrize(
    "sources",
    [[], {"customers": None}, {1: "customers.csv"}, {"customers": " \t"}],
)
def test_pipeline_request_rejects_invalid_dataset_sources(sources: object) -> None:
    with pytest.raises((TypeError, ValueError), match="dataset_sources"):
        make_request(dataset_sources=sources)


def _make_data_quality_report(
    *, run_id: str = "run-1", client_scope: str = "client-pseudonym-1"
) -> DataQualityReport:
    from nowa_customer_intelligence.data.validation.reporting import build_data_quality_report

    return build_data_quality_report(
        findings=(),
        dataset_presence={
            name: False
            for name in (
                "customers",
                "subscriptions",
                "subscription_snapshots",
                "usage_monthly",
                "invoices",
            )
        },
        run_id=run_id,
        client_scope=client_scope,
        created_at_utc=datetime(2026, 11, 16, tzinfo=UTC),
    )


def test_pipeline_orchestration_result_accepts_summary_with_report_reference_only() -> None:
    summary = make_summary(dq_report_id="report-1")

    result = PipelineOrchestrationResult(summary=summary)

    assert result.summary is summary
    assert result.dq_report is None


def test_pipeline_orchestration_result_accepts_matching_data_quality_report() -> None:
    report = _make_data_quality_report()
    summary = make_summary(dq_report_id=report.report_id)

    result = PipelineOrchestrationResult(summary=summary, dq_report=report)

    assert result.dq_report is report


def test_pipeline_orchestration_result_rejects_unreferenced_report() -> None:
    report = _make_data_quality_report()

    with pytest.raises(ValueError, match="match summary.dq_report_id"):
        PipelineOrchestrationResult(summary=make_summary(), dq_report=report)


@pytest.mark.parametrize("field", ["run_id", "client_scope"])
def test_pipeline_orchestration_result_rejects_cross_context_report(field: str) -> None:
    report = _make_data_quality_report(**{field: "other-context"})
    summary = make_summary(dq_report_id=report.report_id)

    with pytest.raises(ValueError, match=field):
        PipelineOrchestrationResult(summary=summary, dq_report=report)
