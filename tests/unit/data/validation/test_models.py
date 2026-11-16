"""Unit tests for immutable Data Quality models."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType

import pytest

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualityReport,
    DataQualitySeverity,
    DataQualitySummary,
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)


def make_finding(**updates: object) -> DataQualityFinding:
    """Build a finding with valid default values and selected overrides."""
    values: dict[str, object] = {
        "rule_id": "RI-001",
        "implementation_status": RuleImplementationStatus.IMPLEMENTED_IN_DQ,
        "severity": DataQualitySeverity.ERROR,
        "result": RuleExecutionResult.PASS,
        "datasets": ("subscriptions", "customers"),
        "description": "Subscription customer references are valid.",
        "records_evaluated": 3,
        "records_affected": 0,
        "blocking_datasets": (),
    }
    values.update(updates)
    return DataQualityFinding(**values)  # type: ignore[arg-type]


def make_summary(**updates: object) -> DataQualitySummary:
    """Build a summary with valid default values and selected overrides."""
    values: dict[str, object] = {
        "severity_counts": {DataQualitySeverity.ERROR: 0},
        "result_counts": {RuleExecutionResult.PASS: 1},
        "blocked": False,
        "blocked_datasets": (),
    }
    values.update(updates)
    return DataQualitySummary(**values)  # type: ignore[arg-type]


def make_report(**updates: object) -> DataQualityReport:
    """Build a report with valid default values and selected overrides."""
    values: dict[str, object] = {
        "report_id": "report-1",
        "run_id": "run-1",
        "client_scope": "client-pseudonym-1",
        "created_at_utc": datetime(2025, 1, 1, tzinfo=UTC),
        "contract_version": "1.1",
        "specification_version": "0.2",
        "pipeline_stage": "data_quality_validation",
        "dataset_presence": {"customers": True, "invoices": False},
        "summary": make_summary(),
        "findings": (make_finding(),),
    }
    values.update(updates)
    return DataQualityReport(**values)  # type: ignore[arg-type]


def test_enums_have_expected_values_and_distinct_types() -> None:
    assert [item.value for item in DataQualitySeverity] == ["ERROR", "WARNING", "INFO"]
    assert [item.value for item in RuleImplementationStatus] == [
        "ALREADY IMPLEMENTED",
        "PROPOSED",
        "PENDING DECISION",
        "DEFERRED",
        "IMPLEMENTED IN DATA QUALITY",
    ]
    assert [item.value for item in RuleExecutionResult] == [
        "PASS",
        "FAIL",
        "NOT_APPLICABLE",
        "NOT_EVALUATED",
    ]
    assert RuleImplementationStatus.IMPLEMENTED_IN_DQ != RuleExecutionResult.PASS
    assert not isinstance(RuleExecutionResult.PASS, RuleImplementationStatus)


def test_each_model_constructs_successfully() -> None:
    finding = make_finding()
    summary = make_summary()
    report = make_report(summary=summary, findings=(finding,))

    assert finding.rule_id == "RI-001"
    assert summary.result_counts[RuleExecutionResult.PASS] == 1
    assert report.findings == (finding,)
    assert report.pipeline_stage == "data_quality_validation"


def test_models_are_frozen() -> None:
    finding = make_finding()
    summary = make_summary()
    report = make_report()

    with pytest.raises(FrozenInstanceError):
        finding.rule_id = "RI-002"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        summary.blocked = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        report.run_id = "another-run"  # type: ignore[misc]


def test_sequence_inputs_are_copied_to_tuples() -> None:
    datasets = ["subscriptions"]
    blocking_datasets = ["customers"]
    summary_blocked_datasets = ["customers"]
    findings = [make_finding()]

    finding = make_finding(datasets=datasets, blocking_datasets=blocking_datasets)
    summary = make_summary(blocked_datasets=summary_blocked_datasets)
    report = make_report(findings=findings)

    datasets.append("invoices")
    blocking_datasets.clear()
    summary_blocked_datasets.append("invoices")
    findings.clear()

    assert finding.datasets == ("subscriptions",)
    assert finding.blocking_datasets == ("customers",)
    assert summary.blocked_datasets == ("customers",)
    assert len(report.findings) == 1


def test_report_mappings_are_defensively_copied_and_immutable() -> None:
    severity_counts = {DataQualitySeverity.ERROR: 1}
    result_counts = {RuleExecutionResult.FAIL: 1}
    presence = {"customers": True}

    summary = make_summary(severity_counts=severity_counts, result_counts=result_counts)
    report = make_report(dataset_presence=presence, summary=summary)
    severity_counts[DataQualitySeverity.ERROR] = 9
    result_counts.clear()
    presence["customers"] = False
    presence["invoices"] = True

    assert isinstance(summary.severity_counts, MappingProxyType)
    assert isinstance(summary.result_counts, MappingProxyType)
    assert isinstance(report.dataset_presence, MappingProxyType)
    assert summary.severity_counts[DataQualitySeverity.ERROR] == 1
    assert summary.result_counts[RuleExecutionResult.FAIL] == 1
    assert report.dataset_presence == {"customers": True}
    with pytest.raises(TypeError):
        summary.severity_counts[DataQualitySeverity.ERROR] = 2  # type: ignore[index]
    with pytest.raises(TypeError):
        report.dataset_presence["customers"] = False  # type: ignore[index]


def test_report_findings_and_nested_finding_are_immutable() -> None:
    finding = make_finding(datasets=["subscriptions"])
    source_findings = [finding]
    report = make_report(findings=source_findings)
    source_findings.clear()

    assert isinstance(report.findings, tuple)
    assert report.findings[0].datasets == ("subscriptions",)
    with pytest.raises(FrozenInstanceError):
        report.findings[0].description = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("field", ["run_id", "client_scope"])
@pytest.mark.parametrize("value", ["", " ", "\t\n"])
def test_report_rejects_empty_or_whitespace_only_metadata(field: str, value: str) -> None:
    with pytest.raises(DataQualityValidationError):
        make_report(**{field: value})


@pytest.mark.parametrize("field", ["run_id", "client_scope"])
def test_report_preserves_accepted_metadata_exactly(field: str) -> None:
    original = "  accepted-metadata  "

    report = make_report(**{field: original})

    assert getattr(report, field) == original


def test_report_rejects_naive_datetime() -> None:
    with pytest.raises(DataQualityValidationError, match="timezone-aware"):
        make_report(created_at_utc=datetime(2025, 1, 1))


def test_report_normalizes_aware_datetime_to_utc() -> None:
    timestamp = datetime(2025, 1, 1, 7, 30, tzinfo=timezone(timedelta(hours=-5)))

    report = make_report(created_at_utc=timestamp)

    assert report.created_at_utc == datetime(2025, 1, 1, 12, 30, tzinfo=UTC)
    assert report.created_at_utc.tzinfo is UTC


@pytest.mark.parametrize("field", ["records_evaluated", "records_affected"])
@pytest.mark.parametrize("value", [-1, -100])
def test_finding_rejects_negative_record_counts(field: str, value: int) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        make_finding(**{field: value})


@pytest.mark.parametrize("field", ["records_evaluated", "records_affected"])
def test_finding_rejects_boolean_record_counts(field: str) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        make_finding(**{field: True})


@pytest.mark.parametrize(
    ("field", "mapping"),
    [
        ("severity_counts", {DataQualitySeverity.ERROR: -1}),
        ("severity_counts", {DataQualitySeverity.ERROR: True}),
        ("severity_counts", {DataQualitySeverity.ERROR: "1"}),
        ("severity_counts", {"ERROR": 1}),
        ("result_counts", {RuleExecutionResult.PASS: False}),
        ("result_counts", {RuleExecutionResult.PASS: -1}),
        ("result_counts", {"PASS": 1}),
    ],
)
def test_summary_rejects_invalid_count_mapping_values(
    field: str, mapping: Mapping[object, object]
) -> None:
    with pytest.raises((TypeError, ValueError)):
        make_summary(**{field: mapping})


def test_summary_requires_boolean_blocked_value() -> None:
    with pytest.raises(TypeError, match="blocked must be a boolean"):
        make_summary(blocked=1)


@pytest.mark.parametrize(
    "mapping",
    [
        {"customers": 1},
        {"customers": "true"},
        {1: True},
    ],
)
def test_report_rejects_invalid_dataset_presence_mapping(mapping: Mapping[object, object]) -> None:
    with pytest.raises(TypeError):
        make_report(dataset_presence=mapping)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("implementation_status", RuleExecutionResult.PASS),
        ("severity", RuleImplementationStatus.PROPOSED),
        ("result", DataQualitySeverity.INFO),
    ],
)
def test_finding_rejects_enum_from_wrong_enum_type(field: str, value: Enum) -> None:
    with pytest.raises(TypeError):
        make_finding(**{field: value})


def test_report_requires_data_quality_pipeline_stage() -> None:
    with pytest.raises(ValueError, match="pipeline_stage"):
        make_report(pipeline_stage="schema_validation")


def test_report_rejects_data_quality_summary_subclass() -> None:
    class ExtendedSummary(DataQualitySummary):
        pass

    summary = ExtendedSummary(
        severity_counts={DataQualitySeverity.ERROR: 0},
        result_counts={RuleExecutionResult.PASS: 1},
        blocked=False,
        blocked_datasets=(),
    )

    with pytest.raises(TypeError, match="summary must be a DataQualitySummary"):
        make_report(summary=summary)


def test_data_quality_validation_error_is_safe_value_error() -> None:
    error = DataQualityValidationError("run_id must contain a non-whitespace character")

    assert isinstance(error, ValueError)
    assert str(error) == "run_id must contain a non-whitespace character"
