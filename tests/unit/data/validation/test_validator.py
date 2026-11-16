"""Unit tests for DQ coordination over schema-validated synthetic frames."""

from dataclasses import replace
from unittest.mock import patch

import pandas as pd
import pytest

from nowa_customer_intelligence.data.validation.models import (
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)
from nowa_customer_intelligence.data.validation.referential_integrity import (
    validate_referential_integrity,
)
from nowa_customer_intelligence.data.validation.temporal_consistency import (
    validate_temporal_consistency,
)
from nowa_customer_intelligence.data.validation.validator import validate_data_quality


def make_datasets(
    *, snapshots: bool = True, invalid_reference: bool = False
) -> dict[str, pd.DataFrame]:
    datasets = {
        "customers": pd.DataFrame({"customer_id": ["C001"]}),
        "subscriptions": pd.DataFrame(
            {
                "subscription_id": ["S001"],
                "customer_id": ["MISSING" if invalid_reference else "C001"],
                "start_date": pd.to_datetime(["2025-01-01"], utc=True),
                "end_date": pd.to_datetime(["2024-12-31"], utc=True),
                "cancellation_date": pd.to_datetime(["2025-02-01"], utc=True),
            }
        ),
    }
    if snapshots:
        datasets["subscription_snapshots"] = pd.DataFrame({"subscription_id": ["S001"]})
    return datasets


def coordinate(datasets: dict[str, pd.DataFrame]):
    ri_findings = validate_referential_integrity(datasets)
    return validate_data_quality(
        datasets=datasets,
        ri_findings=ri_findings,
        run_id="run-123",
        client_scope="client-pseudonym-1",
    )


def test_combines_four_prior_ri_findings_with_two_temporal_findings() -> None:
    report = coordinate(make_datasets())

    assert [finding.rule_id for finding in report.findings] == [
        "RI-001",
        "RI-002",
        "RI-003",
        "RI-004",
        "TC-001",
        "TC-002",
    ]
    assert report.summary.blocked
    assert report.summary.blocked_datasets == ("subscriptions",)


def test_snapshot_absence_is_supported_and_reported_as_not_applicable() -> None:
    datasets = make_datasets(snapshots=False)

    report = coordinate(datasets)
    ri_002 = report.findings[1]

    assert report.dataset_presence["subscription_snapshots"] is False
    assert ri_002.result is RuleExecutionResult.NOT_APPLICABLE
    assert ri_002.records_evaluated is None
    assert ri_002.records_affected is None


def test_present_empty_snapshots_are_evaluated_and_reported_as_present() -> None:
    datasets = make_datasets()
    datasets["subscription_snapshots"] = pd.DataFrame(
        {"subscription_id": pd.Series(dtype="string")}
    )

    report = coordinate(datasets)
    ri_002 = report.findings[1]

    assert report.dataset_presence["subscription_snapshots"] is True
    assert ri_002.result is RuleExecutionResult.PASS
    assert ri_002.records_evaluated == 0
    assert ri_002.records_affected == 0


@pytest.mark.parametrize(
    ("rule_id", "child_dataset"),
    [
        ("RI-001", "subscriptions"),
        ("RI-002", "subscription_snapshots"),
        ("RI-003", "usage_monthly"),
        ("RI-004", "invoices"),
    ],
)
def test_evaluated_ri_count_must_match_child_dataset_rows(
    rule_id: str,
    child_dataset: str,
) -> None:
    datasets = make_datasets()
    if child_dataset in {"usage_monthly", "invoices"}:
        datasets[child_dataset] = pd.DataFrame({"subscription_id": ["S001"]})
    ri_findings = list(validate_referential_integrity(datasets))
    index = int(rule_id[-1]) - 1
    ri_findings[index] = replace(
        ri_findings[index],
        records_evaluated=len(datasets[child_dataset]) + 1,
    )

    with pytest.raises(DataQualityValidationError, match="evaluated row count does not match"):
        validate_data_quality(
            datasets=datasets,
            ri_findings=tuple(ri_findings),
            run_id="run-123",
            client_scope="client-pseudonym-1",
        )


def test_optional_usage_and_invoice_datasets_are_not_applicable_when_absent() -> None:
    report = coordinate(make_datasets())

    assert report.findings[2].result is RuleExecutionResult.NOT_APPLICABLE
    assert report.findings[3].result is RuleExecutionResult.NOT_APPLICABLE
    assert report.dataset_presence["usage_monthly"] is False
    assert report.dataset_presence["invoices"] is False


@pytest.mark.parametrize("optional", ["usage_monthly", "invoices"])
def test_present_valid_optional_datasets_are_preserved(optional: str) -> None:
    datasets = make_datasets()
    datasets[optional] = pd.DataFrame({"subscription_id": ["S001"]})

    report = coordinate(datasets)
    finding_index = 2 if optional == "usage_monthly" else 3

    assert report.dataset_presence[optional] is True
    assert report.findings[finding_index].result is RuleExecutionResult.PASS


def test_coordinator_does_not_rerun_referential_integrity() -> None:
    datasets = make_datasets()
    prior_ri = validate_referential_integrity(datasets)

    with patch(
        "nowa_customer_intelligence.data.validation.validator.validate_referential_integrity",
        side_effect=AssertionError("RI must not be rerun"),
        create=True,
    ):
        report = validate_data_quality(
            datasets=datasets,
            ri_findings=prior_ri,
            run_id="run-123",
            client_scope="client-pseudonym-1",
        )

    assert report.findings[:4] == prior_ri


def test_temporal_validator_is_called_exactly_once() -> None:
    datasets = make_datasets()
    ri_findings = validate_referential_integrity(datasets)

    with patch(
        "nowa_customer_intelligence.data.validation.validator.validate_temporal_consistency",
        wraps=validate_temporal_consistency,
    ) as temporal_validator:
        validate_data_quality(
            datasets=datasets,
            ri_findings=ri_findings,
            run_id="run-123",
            client_scope="client-pseudonym-1",
        )

    temporal_validator.assert_called_once_with(datasets)


@pytest.mark.parametrize("missing", ["customers", "subscriptions"])
def test_missing_required_dataset_is_rejected(missing: str) -> None:
    datasets = make_datasets()
    ri_findings = validate_referential_integrity(datasets)
    del datasets[missing]

    with pytest.raises(DataQualityValidationError, match=missing):
        validate_data_quality(
            datasets=datasets,
            ri_findings=ri_findings,
            run_id="run-123",
            client_scope="client-pseudonym-1",
        )


@pytest.mark.parametrize(
    "bad_findings",
    [
        (),
        (None, None, None, None),
    ],
)
def test_missing_or_invalid_ri_results_are_rejected(
    bad_findings: tuple[object, ...],
) -> None:
    with pytest.raises(DataQualityValidationError, match="RI-001 through RI-004"):
        validate_data_quality(
            datasets=make_datasets(),
            ri_findings=bad_findings,  # type: ignore[arg-type]
            run_id="run-123",
            client_scope="client-pseudonym-1",
        )


def test_duplicate_reordered_and_unexpected_ri_rules_are_rejected() -> None:
    datasets = make_datasets()
    findings = validate_referential_integrity(datasets)
    invalid_sequences = (
        (findings[0], findings[0], findings[2], findings[3]),
        (findings[1], findings[0], findings[2], findings[3]),
        (findings[0], findings[1], findings[2], replace(findings[3], rule_id="RI-005")),
    )

    for invalid in invalid_sequences:
        with pytest.raises(DataQualityValidationError):
            validate_data_quality(
                datasets=datasets,
                ri_findings=invalid,
                run_id="run-123",
                client_scope="client-pseudonym-1",
            )


@pytest.mark.parametrize(
    "updated",
    [
        {"implementation_status": RuleImplementationStatus.PROPOSED},
        {"result": RuleExecutionResult.NOT_APPLICABLE},
        {"records_affected": 1},
        {"blocking_datasets": ()},
    ],
)
def test_inconsistent_ri_result_is_rejected(updated: dict[str, object]) -> None:
    datasets = make_datasets()
    findings = list(validate_referential_integrity(datasets))
    if updated == {"blocking_datasets": ()}:
        findings[0] = replace(
            findings[0],
            result=RuleExecutionResult.FAIL,
            records_affected=1,
            blocking_datasets=(),
        )
    else:
        findings[0] = replace(findings[0], **updated)

    with pytest.raises(DataQualityValidationError):
        validate_data_quality(
            datasets=datasets,
            ri_findings=tuple(findings),
            run_id="run-123",
            client_scope="client-pseudonym-1",
        )


def test_metadata_is_propagated_and_input_frames_are_not_modified() -> None:
    datasets = make_datasets(snapshots=False)
    ri_findings = validate_referential_integrity(datasets)
    before = {name: frame.copy(deep=True) for name, frame in datasets.items()}

    report = validate_data_quality(
        datasets=datasets,
        ri_findings=ri_findings,
        run_id=" run-123 ",
        client_scope=" client-pseudonym-1 ",
        contract_version="1.1",
        specification_version="0.2",
    )

    assert report.run_id == " run-123 "
    assert report.client_scope == " client-pseudonym-1 "
    assert tuple(datasets) == tuple(before)
    for name, frame in datasets.items():
        pd.testing.assert_frame_equal(frame, before[name])


def test_schema_validation_is_a_caller_precondition_only() -> None:
    datasets = make_datasets()
    ri_findings = validate_referential_integrity(datasets)

    with patch(
        "nowa_customer_intelligence.data.schemas.CUSTOMER_SCHEMA.validate",
        side_effect=AssertionError("schema validation must remain upstream"),
    ):
        report = validate_data_quality(
            datasets=datasets,
            ri_findings=ri_findings,
            run_id="run-123",
            client_scope="client-pseudonym-1",
        )

    assert len(report.findings) == 6


def test_registry_failure_is_not_an_input_or_dq_finding() -> None:
    datasets = make_datasets()
    report = coordinate(datasets)

    assert len(report.findings) == 6
    assert all(not finding.rule_id.startswith("REGISTRY") for finding in report.findings)


def test_unknown_dataset_is_rejected_before_rule_execution() -> None:
    datasets = make_datasets()
    datasets["secret_dataset"] = pd.DataFrame()
    ri_findings = validate_referential_integrity(make_datasets())

    with pytest.raises(DataQualityValidationError, match="secret_dataset"):
        validate_data_quality(
            datasets=datasets,
            ri_findings=ri_findings,
            run_id="run-123",
            client_scope="client-pseudonym-1",
        )


def test_missing_rule_input_column_is_rejected_without_running_rules() -> None:
    datasets = make_datasets()
    datasets["subscriptions"] = datasets["subscriptions"].drop(columns="end_date")
    ri_findings = validate_referential_integrity(make_datasets())

    with patch(
        "nowa_customer_intelligence.data.validation.validator.validate_temporal_consistency",
        side_effect=AssertionError("rules must not run on structurally incomplete input"),
    ):
        with pytest.raises(DataQualityValidationError, match="schema validation precondition"):
            validate_data_quality(
                datasets=datasets,
                ri_findings=ri_findings,
                run_id="run-123",
                client_scope="client-pseudonym-1",
            )
