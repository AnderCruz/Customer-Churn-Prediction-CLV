"""Unit tests for DQ report aggregation and construction."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualitySeverity,
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)
from nowa_customer_intelligence.data.validation.reporting import build_data_quality_report

DATASET_PRESENCE = {
    "customers": True,
    "subscriptions": True,
    "subscription_snapshots": False,
    "usage_monthly": False,
    "invoices": False,
}


def make_finding(**updates: object) -> DataQualityFinding:
    values: dict[str, object] = {
        "rule_id": "RI-001",
        "implementation_status": RuleImplementationStatus.IMPLEMENTED_IN_DQ,
        "severity": DataQualitySeverity.ERROR,
        "result": RuleExecutionResult.PASS,
        "datasets": ("subscriptions", "customers"),
        "description": "Subscription customer references are valid.",
        "records_evaluated": 2,
        "records_affected": 0,
        "blocking_datasets": (),
    }
    values.update(updates)
    return DataQualityFinding(**values)  # type: ignore[arg-type]


def make_unvalidated_finding(**updates: object) -> DataQualityFinding:
    """Create a deliberately malformed instance to test the report boundary itself."""
    values: dict[str, object] = {
        "rule_id": "SENSITIVE-TEST-MARKER",
        "implementation_status": RuleImplementationStatus.IMPLEMENTED_IN_DQ,
        "severity": DataQualitySeverity.ERROR,
        "result": RuleExecutionResult.PASS,
        "datasets": ("subscriptions",),
        "description": "A safe test finding.",
        "records_evaluated": 1,
        "records_affected": 0,
        "blocking_datasets": (),
    }
    values.update(updates)
    finding = object.__new__(DataQualityFinding)
    for field, value in values.items():
        object.__setattr__(finding, field, value)
    return finding


def build_report(
    findings: tuple[DataQualityFinding, ...] | list[DataQualityFinding],
    **updates: object,
):
    values: dict[str, object] = {
        "findings": findings,
        "dataset_presence": DATASET_PRESENCE,
        "run_id": "run-123",
        "client_scope": "client-pseudonym-1",
    }
    values.update(updates)
    return build_data_quality_report(**values)  # type: ignore[arg-type]


def test_builds_report_with_metadata_presence_and_generated_id() -> None:
    finding = make_finding()

    report = build_report([finding])

    UUID(report.report_id)
    assert report.run_id == "run-123"
    assert report.client_scope == "client-pseudonym-1"
    assert report.contract_version == "1.1"
    assert report.specification_version == "0.2"
    assert report.dataset_presence == DATASET_PRESENCE
    assert report.findings == (finding,)
    assert report.created_at_utc.tzinfo is UTC


def test_counts_all_result_values_and_only_failed_severities() -> None:
    findings = (
        make_finding(rule_id="RI-001"),
        make_finding(
            rule_id="TC-001",
            severity=DataQualitySeverity.WARNING,
            result=RuleExecutionResult.FAIL,
            records_evaluated=2,
            records_affected=1,
        ),
        make_finding(
            rule_id="RI-002",
            result=RuleExecutionResult.NOT_APPLICABLE,
            records_evaluated=None,
            records_affected=None,
        ),
    )

    summary = build_report(findings).summary

    assert summary.result_counts == {
        RuleExecutionResult.PASS: 1,
        RuleExecutionResult.FAIL: 1,
        RuleExecutionResult.NOT_APPLICABLE: 1,
        RuleExecutionResult.NOT_EVALUATED: 0,
    }
    assert summary.severity_counts == {
        DataQualitySeverity.ERROR: 0,
        DataQualitySeverity.WARNING: 1,
        DataQualitySeverity.INFO: 0,
    }


def test_error_fail_blocks_and_deduplicates_datasets_in_finding_order() -> None:
    findings = (
        make_finding(
            rule_id="RI-001",
            result=RuleExecutionResult.FAIL,
            records_affected=1,
            blocking_datasets=("subscriptions", "customers"),
        ),
        make_finding(
            rule_id="RI-002",
            result=RuleExecutionResult.FAIL,
            records_affected=1,
            datasets=("subscription_snapshots", "subscriptions"),
            blocking_datasets=("subscription_snapshots", "subscriptions"),
        ),
    )

    summary = build_report(findings).summary

    assert summary.blocked is True
    assert summary.blocked_datasets == (
        "subscriptions",
        "customers",
        "subscription_snapshots",
    )


@pytest.mark.parametrize(
    ("severity", "result", "blocking_datasets", "expected_blocked"),
    [
        (DataQualitySeverity.WARNING, RuleExecutionResult.FAIL, ("subscriptions",), False),
        (DataQualitySeverity.ERROR, RuleExecutionResult.PASS, (), False),
        (DataQualitySeverity.INFO, RuleExecutionResult.FAIL, ("subscriptions",), False),
    ],
)
def test_only_error_fail_findings_block(
    severity: DataQualitySeverity,
    result: RuleExecutionResult,
    blocking_datasets: tuple[str, ...],
    expected_blocked: bool,
) -> None:
    finding = make_finding(
        severity=severity,
        result=result,
        records_affected=1 if result is RuleExecutionResult.FAIL else 0,
        blocking_datasets=blocking_datasets,
    )

    summary = build_report((finding,)).summary

    assert summary.blocked is expected_blocked
    expected_datasets = ("subscriptions",) if expected_blocked else ()
    assert summary.blocked_datasets == expected_datasets


def test_error_failure_without_a_valid_blocking_scope_is_rejected() -> None:
    finding = make_finding(
        result=RuleExecutionResult.FAIL,
        records_affected=1,
        blocking_datasets=(),
    )

    with pytest.raises(DataQualityValidationError, match="blocking datasets"):
        build_report((finding,))


@pytest.mark.parametrize(
    ("result", "updates", "message"),
    [
        (
            RuleExecutionResult.PASS,
            {"records_affected": 1},
            "PASS findings must have zero affected rows",
        ),
        (
            RuleExecutionResult.PASS,
            {"blocking_datasets": ("subscriptions",)},
            "PASS findings cannot have blocking datasets",
        ),
        (
            RuleExecutionResult.FAIL,
            {"records_affected": 0, "blocking_datasets": ("subscriptions", "customers")},
            "FAIL findings must have affected rows",
        ),
        (
            RuleExecutionResult.FAIL,
            {"records_evaluated": 1, "records_affected": 2},
            "affected row count exceeds evaluated row count",
        ),
        (
            RuleExecutionResult.FAIL,
            {"records_evaluated": None, "records_affected": 1},
            "FAIL findings must include integer row counts",
        ),
    ],
)
def test_pass_and_fail_row_count_invariants_are_enforced(
    result: RuleExecutionResult,
    updates: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(DataQualityValidationError, match=message):
        build_report((make_finding(result=result, **updates),))


@pytest.mark.parametrize("value", [-1, True, "1"])
@pytest.mark.parametrize("field", ["records_evaluated", "records_affected"])
def test_report_boundary_rejects_invalid_row_count_values(field: str, value: object) -> None:
    finding = make_unvalidated_finding(**{field: value})

    with pytest.raises(DataQualityValidationError) as error:
        build_report((finding,))

    assert field in str(error.value)
    assert "SENSITIVE-TEST-MARKER" not in str(error.value)


@pytest.mark.parametrize(
    ("result", "updates"),
    [
        (
            RuleExecutionResult.NOT_APPLICABLE,
            {"records_evaluated": 1, "records_affected": 0},
        ),
        (
            RuleExecutionResult.NOT_EVALUATED,
            {"records_evaluated": 1, "records_affected": 0},
        ),
        (
            RuleExecutionResult.NOT_APPLICABLE,
            {
                "records_evaluated": None,
                "records_affected": None,
                "blocking_datasets": ("subscriptions",),
            },
        ),
        (
            RuleExecutionResult.NOT_EVALUATED,
            {
                "records_evaluated": None,
                "records_affected": None,
                "blocking_datasets": ("subscriptions",),
            },
        ),
    ],
)
def test_not_applicable_and_not_evaluated_require_no_counts_or_blockers(
    result: RuleExecutionResult,
    updates: dict[str, object],
) -> None:
    with pytest.raises(DataQualityValidationError):
        build_report((make_finding(result=result, **updates),))


def test_error_failure_blocking_datasets_must_be_in_finding_scope() -> None:
    finding = make_finding(
        result=RuleExecutionResult.FAIL,
        records_affected=1,
        blocking_datasets=("invoices",),
    )

    with pytest.raises(DataQualityValidationError, match="blocking datasets"):
        build_report((finding,))


def test_empty_findings_produce_zero_counts() -> None:
    summary = build_report(()).summary

    assert not summary.blocked
    assert not summary.blocked_datasets
    assert all(count == 0 for count in summary.result_counts.values())
    assert all(count == 0 for count in summary.severity_counts.values())


@pytest.mark.parametrize(
    ("status", "result"),
    [
        (RuleImplementationStatus.PROPOSED, RuleExecutionResult.NOT_EVALUATED),
        (RuleImplementationStatus.PENDING_DECISION, RuleExecutionResult.NOT_EVALUATED),
        (RuleImplementationStatus.DEFERRED, RuleExecutionResult.NOT_EVALUATED),
    ],
)
def test_generic_builder_preserves_unimplemented_status_and_not_evaluated_result(
    status: RuleImplementationStatus,
    result: RuleExecutionResult,
) -> None:
    finding = make_finding(
        rule_id="FUTURE-001",
        implementation_status=status,
        result=result,
        records_evaluated=None,
        records_affected=None,
    )

    report = build_report((finding,))

    assert report.findings == (finding,)
    assert report.findings[0].implementation_status is status
    assert report.findings[0].result is RuleExecutionResult.NOT_EVALUATED
    assert report.summary.result_counts[RuleExecutionResult.NOT_EVALUATED] == 1
    assert report.summary.result_counts[RuleExecutionResult.PASS] == 0
    assert not report.summary.blocked


def test_already_implemented_checks_are_not_added_as_dq_findings() -> None:
    finding = make_finding(implementation_status=RuleImplementationStatus.ALREADY_IMPLEMENTED)

    with pytest.raises(DataQualityValidationError, match="another validation layer"):
        build_report((finding,))


def test_duplicate_rule_ids_are_rejected() -> None:
    with pytest.raises(DataQualityValidationError, match="duplicate rule IDs"):
        build_report((make_finding(), make_finding()))


@pytest.mark.parametrize("field", ["run_id", "client_scope"])
@pytest.mark.parametrize("value", ["", "  ", "\t\n"])
def test_invalid_run_metadata_is_rejected(field: str, value: str) -> None:
    with pytest.raises(DataQualityValidationError):
        build_report((), **{field: value})


def test_metadata_is_preserved_and_aware_timestamp_is_normalized() -> None:
    original = "  pseudonymous-client  "
    timestamp = datetime(2025, 1, 1, 7, 0, tzinfo=timezone(timedelta(hours=-5)))

    report = build_report((), client_scope=original, created_at_utc=timestamp)

    assert report.client_scope == original
    assert report.created_at_utc == datetime(2025, 1, 1, 12, 0, tzinfo=UTC)


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(DataQualityValidationError, match="timezone-aware"):
        build_report((), created_at_utc=datetime(2025, 1, 1))


def test_report_collections_are_defensively_copied_and_immutable() -> None:
    source_findings = [make_finding()]
    source_presence = dict(DATASET_PRESENCE)

    report = build_report(source_findings, dataset_presence=source_presence)
    source_findings.clear()
    source_presence["customers"] = False

    assert len(report.findings) == 1
    assert report.dataset_presence["customers"] is True


def test_presence_mapping_must_contain_exactly_the_known_datasets() -> None:
    incomplete: Mapping[str, bool] = {"customers": True}

    with pytest.raises(DataQualityValidationError, match="all five contract datasets"):
        build_report((), dataset_presence=incomplete)
