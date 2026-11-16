"""Unit tests for Pipeline Execution Summary construction."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from nowa_customer_intelligence.pipeline import (
    PipelineExecutionSummary,
    PipelineOverallStatus,
    StageExecutionResult,
    StageExecutionStatus,
    StageRequirement,
    build_pipeline_execution_summary,
)


def make_stage(**updates: object) -> StageExecutionResult:
    """Create a valid stage result for builder tests."""
    values: dict[str, object] = {
        "stage_id": "csv_ingestion",
        "status": StageExecutionStatus.SUCCEEDED,
        "requirement": StageRequirement.REQUIRED,
    }
    values.update(updates)
    return StageExecutionResult(**values)  # type: ignore[arg-type]


def build_summary(**updates: object) -> PipelineExecutionSummary:
    """Build a summary with valid defaults and selected overrides."""
    values: dict[str, object] = {
        "summary_id": "summary-1",
        "run_id": "run-1",
        "client_scope": "client-pseudonym-1",
        "created_at_utc": datetime(2026, 11, 16, tzinfo=UTC),
        "overall_status": PipelineOverallStatus.SUCCEEDED,
        "stages": (),
        "dataset_presence": {"customers": True, "subscriptions": True},
    }
    values.update(updates)
    return build_pipeline_execution_summary(**values)  # type: ignore[arg-type]


def test_package_level_import_builds_summary_with_multiple_stages() -> None:
    stages = (
        make_stage(),
        make_stage(stage_id="schema_validation", status=StageExecutionStatus.PARTIAL),
    )
    created_at = datetime(2026, 11, 16, 12, tzinfo=UTC)

    summary = build_pipeline_execution_summary(
        summary_id="summary-23",
        run_id="run-17",
        client_scope="client-pseudonym-4",
        created_at_utc=created_at,
        overall_status=PipelineOverallStatus.SUCCEEDED,
        stages=stages,
        dataset_presence={"customers": True, "invoices": False},
    )

    assert isinstance(summary, PipelineExecutionSummary)
    assert summary.summary_id == "summary-23"
    assert summary.run_id == "run-17"
    assert summary.client_scope == "client-pseudonym-4"
    assert summary.created_at_utc == created_at
    assert summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert summary.stages == stages
    assert summary.dataset_presence == {"customers": True, "invoices": False}
    assert summary.dq_report_id is None


def test_builder_accepts_empty_stage_sequence_and_default_dq_reference() -> None:
    summary = build_summary()

    assert summary.stages == ()
    assert summary.dq_report_id is None


def test_builder_passes_valid_dq_report_reference() -> None:
    summary = build_summary(dq_report_id="dq-report-12")

    assert summary.dq_report_id == "dq-report-12"


@pytest.mark.parametrize(
    ("overall_status", "stage_status"),
    [
        (PipelineOverallStatus.SUCCEEDED, StageExecutionStatus.FAILED),
        (PipelineOverallStatus.FAILED, StageExecutionStatus.SUCCEEDED),
        (PipelineOverallStatus.BLOCKED, StageExecutionStatus.PARTIAL),
    ],
)
def test_builder_preserves_supplied_overall_status_without_aggregation(
    overall_status: PipelineOverallStatus, stage_status: StageExecutionStatus
) -> None:
    stage = make_stage(status=stage_status)

    summary = build_summary(overall_status=overall_status, stages=(stage,))

    assert summary.overall_status is overall_status
    assert summary.stages[0].status is stage_status


@pytest.mark.parametrize("field", ["summary_id", "run_id", "client_scope"])
@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_builder_delegates_invalid_identifiers_to_model(field: str, value: str) -> None:
    with pytest.raises(ValueError, match=field):
        build_summary(**{field: value})


def test_builder_delegates_naive_timestamp_validation_to_model() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        build_summary(created_at_utc=datetime(2026, 11, 16))


def test_builder_delegates_timestamp_type_validation_to_model() -> None:
    with pytest.raises(TypeError, match="created_at_utc"):
        build_summary(created_at_utc="2026-11-16T00:00:00Z")


def test_builder_delegates_overall_status_validation_to_model() -> None:
    with pytest.raises(TypeError, match="PipelineOverallStatus"):
        build_summary(overall_status=StageExecutionStatus.SUCCEEDED)


def test_builder_delegates_invalid_stage_validation_to_model() -> None:
    with pytest.raises(TypeError, match="stages"):
        build_summary(stages=(object(),))


def test_builder_delegates_duplicate_stage_id_validation_to_model() -> None:
    with pytest.raises(ValueError, match="unique"):
        build_summary(stages=(make_stage(), make_stage()))


@pytest.mark.parametrize("presence", [{"customers": 1}, {1: True}, []])
def test_builder_delegates_dataset_presence_validation_to_model(presence: object) -> None:
    with pytest.raises(TypeError, match="dataset_presence"):
        build_summary(dataset_presence=presence)


@pytest.mark.parametrize("dq_report_id", ["", " ", "\t\n"])
def test_builder_delegates_dq_reference_validation_to_model(dq_report_id: str) -> None:
    with pytest.raises(ValueError, match="dq_report_id"):
        build_summary(dq_report_id=dq_report_id)


def test_builder_defensively_copies_stage_sequence_and_does_not_modify_stages() -> None:
    stage = make_stage(records_received=3, records_processed=2, records_rejected=1)
    source_stages = [stage]

    summary = build_summary(stages=source_stages)
    source_stages.clear()

    assert summary.stages == (stage,)
    assert summary.stages[0] is stage
    assert stage.records_received == 3
    assert stage.records_processed == 2
    assert stage.records_rejected == 1


def test_builder_defensively_copies_dataset_presence_mapping() -> None:
    presence = {"customers": True}

    summary = build_summary(dataset_presence=presence)
    presence["customers"] = False
    presence["invoices"] = True

    assert summary.dataset_presence == {"customers": True}


def test_builder_normalizes_timestamp_using_existing_model_behavior() -> None:
    timestamp = datetime(2026, 11, 16, 7, 30, tzinfo=timezone(timedelta(hours=-5)))

    summary = build_summary(created_at_utc=timestamp)

    assert summary.created_at_utc == datetime(2026, 11, 16, 12, 30, tzinfo=UTC)
    assert summary.created_at_utc.tzinfo is UTC
