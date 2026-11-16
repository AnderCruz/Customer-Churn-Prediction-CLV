"""Unit tests for the initial referential integrity rules."""

import pandas as pd
import pytest

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualitySeverity,
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)
from nowa_customer_intelligence.data.validation.referential_integrity import (
    validate_referential_integrity,
)


def make_datasets(
    *,
    customer_ids: tuple[str, ...] = ("C001",),
    subscription_customer_ids: tuple[str, ...] = ("C001",),
    subscription_ids: tuple[str, ...] = ("S001",),
    snapshot_subscription_ids: tuple[str, ...] = ("S001",),
) -> dict[str, pd.DataFrame]:
    """Build synthetic datasets containing the columns used by RI-001 and RI-002."""
    return {
        "customers": pd.DataFrame({"customer_id": list(customer_ids)}),
        "subscriptions": pd.DataFrame(
            {
                "subscription_id": list(subscription_ids),
                "customer_id": list(subscription_customer_ids),
            }
        ),
        "subscription_snapshots": pd.DataFrame(
            {"subscription_id": list(snapshot_subscription_ids)}
        ),
    }


def get_finding(findings: tuple[DataQualityFinding, ...], rule_id: str) -> DataQualityFinding:
    return next(finding for finding in findings if finding.rule_id == rule_id)


def test_returns_exactly_ri_001_through_ri_004_in_order() -> None:
    findings = validate_referential_integrity(make_datasets())

    assert len(findings) == 4
    assert [finding.rule_id for finding in findings] == [
        "RI-001",
        "RI-002",
        "RI-003",
        "RI-004",
    ]
    assert [finding.result for finding in findings] == [
        RuleExecutionResult.PASS,
        RuleExecutionResult.PASS,
        RuleExecutionResult.NOT_APPLICABLE,
        RuleExecutionResult.NOT_APPLICABLE,
    ]
    assert all(
        finding.implementation_status is RuleImplementationStatus.IMPLEMENTED_IN_DQ
        for finding in findings
    )
    assert all(finding.severity is DataQualitySeverity.ERROR for finding in findings)


def test_customers_and_subscriptions_are_required_but_snapshots_are_optional() -> None:
    datasets = make_datasets()
    datasets.pop("subscription_snapshots")

    findings = validate_referential_integrity(datasets)

    assert [finding.rule_id for finding in findings] == [
        "RI-001",
        "RI-002",
        "RI-003",
        "RI-004",
    ]
    ri_002 = get_finding(findings, "RI-002")
    assert ri_002.result is RuleExecutionResult.NOT_APPLICABLE
    assert ri_002.records_evaluated is None
    assert ri_002.records_affected is None
    assert ri_002.blocking_datasets == ()


def test_ri_001_pass_finding_has_correct_counts_scope_and_no_blocking_datasets() -> None:
    finding = get_finding(validate_referential_integrity(make_datasets()), "RI-001")

    assert finding.result is RuleExecutionResult.PASS
    assert finding.datasets == ("subscriptions", "customers")
    assert finding.records_evaluated == 1
    assert finding.records_affected == 0
    assert finding.blocking_datasets == ()


def test_ri_001_fails_one_invalid_customer_reference() -> None:
    datasets = make_datasets(subscription_customer_ids=("MISSING-CUSTOMER",))

    finding = get_finding(validate_referential_integrity(datasets), "RI-001")

    assert finding.result is RuleExecutionResult.FAIL
    assert finding.records_evaluated == 1
    assert finding.records_affected == 1
    assert finding.datasets == ("subscriptions", "customers")
    assert finding.blocking_datasets == ("subscriptions", "customers")
    assert "MISSING-CUSTOMER" not in finding.description


def test_ri_001_counts_each_record_with_invalid_reference() -> None:
    datasets = make_datasets(
        subscription_ids=("S001", "S002", "S003"),
        subscription_customer_ids=("MISSING-CUSTOMER", "OTHER-MISSING", "MISSING-CUSTOMER"),
        snapshot_subscription_ids=("S001",),
    )

    finding = get_finding(validate_referential_integrity(datasets), "RI-001")

    assert finding.records_evaluated == 3
    assert finding.records_affected == 3


def test_ri_001_empty_subscription_source_passes_with_zero_counts() -> None:
    datasets = make_datasets(
        subscription_ids=(),
        subscription_customer_ids=(),
        snapshot_subscription_ids=(),
    )

    finding = get_finding(validate_referential_integrity(datasets), "RI-001")

    assert finding.result is RuleExecutionResult.PASS
    assert finding.records_evaluated == 0
    assert finding.records_affected == 0
    assert finding.blocking_datasets == ()


def test_ri_001_compares_exact_strings_without_trimming() -> None:
    datasets = make_datasets(subscription_customer_ids=(" C001 ",))

    finding = get_finding(validate_referential_integrity(datasets), "RI-001")

    assert finding.result is RuleExecutionResult.FAIL
    assert finding.records_affected == 1


def test_ri_002_pass_finding_has_correct_counts_scope_and_no_blocking_datasets() -> None:
    finding = get_finding(validate_referential_integrity(make_datasets()), "RI-002")

    assert finding.result is RuleExecutionResult.PASS
    assert finding.datasets == ("subscription_snapshots", "subscriptions")
    assert finding.records_evaluated == 1
    assert finding.records_affected == 0
    assert finding.blocking_datasets == ()


def test_ri_002_fails_one_invalid_subscription_reference() -> None:
    datasets = make_datasets(snapshot_subscription_ids=("MISSING-SUBSCRIPTION",))

    finding = get_finding(validate_referential_integrity(datasets), "RI-002")

    assert finding.result is RuleExecutionResult.FAIL
    assert finding.records_evaluated == 1
    assert finding.records_affected == 1
    assert finding.datasets == ("subscription_snapshots", "subscriptions")
    assert finding.blocking_datasets == ("subscription_snapshots", "subscriptions")
    assert "MISSING-SUBSCRIPTION" not in finding.description


def test_ri_002_counts_each_record_with_repeated_invalid_reference() -> None:
    datasets = make_datasets(
        snapshot_subscription_ids=("MISSING-SUBSCRIPTION", "MISSING-SUBSCRIPTION", "S001")
    )

    finding = get_finding(validate_referential_integrity(datasets), "RI-002")

    assert finding.records_evaluated == 3
    assert finding.records_affected == 2


def test_ri_002_empty_snapshot_source_passes_with_zero_counts() -> None:
    datasets = make_datasets(snapshot_subscription_ids=())

    finding = get_finding(validate_referential_integrity(datasets), "RI-002")

    assert finding.result is RuleExecutionResult.PASS
    assert finding.records_evaluated == 0
    assert finding.records_affected == 0
    assert finding.blocking_datasets == ()


def test_ri_002_absent_snapshot_dataset_is_not_applicable_without_counts() -> None:
    datasets = make_datasets()
    del datasets["subscription_snapshots"]

    finding = get_finding(validate_referential_integrity(datasets), "RI-002")

    assert finding.implementation_status is RuleImplementationStatus.IMPLEMENTED_IN_DQ
    assert finding.result is RuleExecutionResult.NOT_APPLICABLE
    assert finding.records_evaluated is None
    assert finding.records_affected is None
    assert finding.blocking_datasets == ()


def test_ri_002_compares_exact_strings_without_trimming() -> None:
    datasets = make_datasets(snapshot_subscription_ids=(" S001 ",))

    finding = get_finding(validate_referential_integrity(datasets), "RI-002")

    assert finding.result is RuleExecutionResult.FAIL
    assert finding.records_affected == 1


def test_ri_003_and_ri_004_pass_with_valid_optional_dataset_references() -> None:
    datasets = make_datasets()
    datasets["usage_monthly"] = pd.DataFrame({"subscription_id": ["S001"]})
    datasets["invoices"] = pd.DataFrame({"subscription_id": ["S001"]})

    findings = validate_referential_integrity(datasets)

    assert get_finding(findings, "RI-003").result is RuleExecutionResult.PASS
    assert get_finding(findings, "RI-004").result is RuleExecutionResult.PASS


def test_ri_003_fails_one_invalid_usage_reference_with_expected_metadata() -> None:
    datasets = make_datasets()
    datasets["usage_monthly"] = pd.DataFrame({"subscription_id": ["MISSING-USAGE-SUB"]})

    finding = get_finding(validate_referential_integrity(datasets), "RI-003")

    assert finding.implementation_status is RuleImplementationStatus.IMPLEMENTED_IN_DQ
    assert finding.severity is DataQualitySeverity.ERROR
    assert finding.result is RuleExecutionResult.FAIL
    assert finding.datasets == ("usage_monthly", "subscriptions")
    assert finding.records_evaluated == 1
    assert finding.records_affected == 1
    assert finding.blocking_datasets == ("usage_monthly", "subscriptions")
    assert "MISSING-USAGE-SUB" not in finding.description


def test_ri_003_counts_multiple_invalid_usage_records_including_repeats() -> None:
    datasets = make_datasets()
    datasets["usage_monthly"] = pd.DataFrame(
        {"subscription_id": ["MISSING-USAGE-SUB", "MISSING-USAGE-SUB", "OTHER-MISSING"]}
    )

    finding = get_finding(validate_referential_integrity(datasets), "RI-003")

    assert finding.records_evaluated == 3
    assert finding.records_affected == 3


def test_ri_003_empty_optional_dataframe_passes_with_zero_counts() -> None:
    datasets = make_datasets()
    datasets["usage_monthly"] = pd.DataFrame({"subscription_id": pd.Series(dtype="string")})

    finding = get_finding(validate_referential_integrity(datasets), "RI-003")

    assert finding.result is RuleExecutionResult.PASS
    assert finding.records_evaluated == 0
    assert finding.records_affected == 0
    assert finding.blocking_datasets == ()


def test_ri_003_absent_usage_dataset_is_not_applicable() -> None:
    finding = get_finding(validate_referential_integrity(make_datasets()), "RI-003")

    assert finding.implementation_status is RuleImplementationStatus.IMPLEMENTED_IN_DQ
    assert finding.severity is DataQualitySeverity.ERROR
    assert finding.result is RuleExecutionResult.NOT_APPLICABLE
    assert finding.datasets == ("usage_monthly", "subscriptions")
    assert finding.records_evaluated is None
    assert finding.records_affected is None
    assert finding.blocking_datasets == ()
    assert "usage_monthly" in finding.description
    assert "not applicable" in finding.description


def test_ri_004_fails_one_invalid_invoice_reference_with_expected_metadata() -> None:
    datasets = make_datasets()
    datasets["invoices"] = pd.DataFrame({"subscription_id": ["MISSING-INVOICE-SUB"]})

    finding = get_finding(validate_referential_integrity(datasets), "RI-004")

    assert finding.implementation_status is RuleImplementationStatus.IMPLEMENTED_IN_DQ
    assert finding.severity is DataQualitySeverity.ERROR
    assert finding.result is RuleExecutionResult.FAIL
    assert finding.datasets == ("invoices", "subscriptions")
    assert finding.records_evaluated == 1
    assert finding.records_affected == 1
    assert finding.blocking_datasets == ("invoices", "subscriptions")
    assert "MISSING-INVOICE-SUB" not in finding.description


def test_ri_004_counts_multiple_invalid_invoice_records_including_repeats() -> None:
    datasets = make_datasets()
    datasets["invoices"] = pd.DataFrame(
        {"subscription_id": ["MISSING-INVOICE-SUB", "MISSING-INVOICE-SUB", "OTHER-MISSING"]}
    )

    finding = get_finding(validate_referential_integrity(datasets), "RI-004")

    assert finding.records_evaluated == 3
    assert finding.records_affected == 3


def test_ri_004_empty_optional_dataframe_passes_with_zero_counts() -> None:
    datasets = make_datasets()
    datasets["invoices"] = pd.DataFrame({"subscription_id": pd.Series(dtype="string")})

    finding = get_finding(validate_referential_integrity(datasets), "RI-004")

    assert finding.result is RuleExecutionResult.PASS
    assert finding.records_evaluated == 0
    assert finding.records_affected == 0
    assert finding.blocking_datasets == ()


def test_ri_004_absent_invoice_dataset_is_not_applicable() -> None:
    finding = get_finding(validate_referential_integrity(make_datasets()), "RI-004")

    assert finding.implementation_status is RuleImplementationStatus.IMPLEMENTED_IN_DQ
    assert finding.severity is DataQualitySeverity.ERROR
    assert finding.result is RuleExecutionResult.NOT_APPLICABLE
    assert finding.datasets == ("invoices", "subscriptions")
    assert finding.records_evaluated is None
    assert finding.records_affected is None
    assert finding.blocking_datasets == ()
    assert "invoices" in finding.description
    assert "not applicable" in finding.description


@pytest.mark.parametrize("missing_dataset", ["customers", "subscriptions"])
def test_missing_required_dataset_raises_safe_error(missing_dataset: str) -> None:
    datasets = make_datasets()
    del datasets[missing_dataset]

    with pytest.raises(DataQualityValidationError) as error:
        validate_referential_integrity(datasets)

    assert missing_dataset in str(error.value)
    assert "C001" not in str(error.value)


@pytest.mark.parametrize("invalid_dataset", ["customers", "subscriptions"])
def test_non_dataframe_required_dataset_raises_safe_error(invalid_dataset: str) -> None:
    datasets: dict[str, object] = make_datasets()
    datasets[invalid_dataset] = object()

    with pytest.raises(DataQualityValidationError) as error:
        validate_referential_integrity(datasets)  # type: ignore[arg-type]

    assert "DataFrames" in str(error.value)
    assert "C001" not in str(error.value)


def test_present_snapshot_dataset_must_be_a_dataframe() -> None:
    datasets: dict[str, object] = make_datasets()
    datasets["subscription_snapshots"] = "PRIVATE-SNAPSHOT-DATA"

    with pytest.raises(DataQualityValidationError) as error:
        validate_referential_integrity(datasets)  # type: ignore[arg-type]

    assert "DataFrames" in str(error.value)
    assert "PRIVATE-SNAPSHOT-DATA" not in str(error.value)


def test_invalid_datasets_argument_type_raises_data_quality_validation_error() -> None:
    with pytest.raises(DataQualityValidationError, match="datasets must be a mapping"):
        validate_referential_integrity([])  # type: ignore[arg-type]


def test_unknown_dataframe_dataset_name_is_rejected_with_safe_message() -> None:
    private_value = "PRIVATE-RECORD-VALUE"
    datasets = make_datasets()
    datasets["marketing_events"] = pd.DataFrame({"value": [private_value]})

    with pytest.raises(DataQualityValidationError) as error:
        validate_referential_integrity(datasets)

    assert "marketing_events" in str(error.value)
    assert private_value not in str(error.value)
    assert "DataFrame" not in str(error.value)


def test_unknown_dataset_name_with_non_dataframe_value_is_rejected_first() -> None:
    datasets: dict[str, object] = make_datasets()
    datasets["unknown_dataset"] = "PRIVATE-RECORD-VALUE"

    with pytest.raises(DataQualityValidationError) as error:
        validate_referential_integrity(datasets)  # type: ignore[arg-type]

    assert "unknown dataset name: 'unknown_dataset'" in str(error.value)
    assert "PRIVATE-RECORD-VALUE" not in str(error.value)
    assert "DataFrames" not in str(error.value)


def test_non_string_unknown_dataset_name_error_does_not_include_object_repr() -> None:
    class SecretKey:
        def __repr__(self) -> str:
            return "SECRET-KEY-REPRESENTATION"

    datasets: dict[object, object] = make_datasets()
    datasets[SecretKey()] = pd.DataFrame()

    with pytest.raises(DataQualityValidationError) as error:
        validate_referential_integrity(datasets)  # type: ignore[arg-type]

    assert str(error.value) == "dataset names must be recognized strings"
    assert "SECRET-KEY-REPRESENTATION" not in str(error.value)


@pytest.mark.parametrize("optional_dataset", ["usage_monthly", "invoices"])
def test_recognized_optional_dataset_is_accepted(optional_dataset: str) -> None:
    datasets = make_datasets()
    datasets[optional_dataset] = pd.DataFrame({"subscription_id": ["S001"]})

    findings = validate_referential_integrity(datasets)

    assert [finding.rule_id for finding in findings] == ["RI-001", "RI-002", "RI-003", "RI-004"]


@pytest.mark.parametrize("optional_dataset", ["usage_monthly", "invoices"])
def test_present_optional_dataset_must_be_a_dataframe(optional_dataset: str) -> None:
    datasets: dict[str, object] = make_datasets()
    datasets[optional_dataset] = "PRIVATE-OPTIONAL-DATA"

    with pytest.raises(DataQualityValidationError) as error:
        validate_referential_integrity(datasets)  # type: ignore[arg-type]

    assert "DataFrames" in str(error.value)
    assert "PRIVATE-OPTIONAL-DATA" not in str(error.value)


def test_input_mapping_and_dataframes_are_not_modified() -> None:
    datasets = make_datasets(
        customer_ids=("C001", "C002"),
        subscription_ids=("S001", "S002"),
        subscription_customer_ids=("C001", "MISSING-CUSTOMER"),
        snapshot_subscription_ids=("S001", "MISSING-SUBSCRIPTION"),
    )
    datasets["usage_monthly"] = pd.DataFrame({"subscription_id": ["S001", "MISSING-USAGE-SUB"]})
    datasets["invoices"] = pd.DataFrame({"subscription_id": ["MISSING-INVOICE-SUB"]})
    original_keys = tuple(datasets)
    original_frames = {name: frame.copy(deep=True) for name, frame in datasets.items()}

    validate_referential_integrity(datasets)

    assert tuple(datasets) == original_keys
    for name, original in original_frames.items():
        pd.testing.assert_frame_equal(datasets[name], original)


def test_finding_descriptions_do_not_expose_raw_invalid_identifiers() -> None:
    secret_customer_id = "PRIVATE-CUSTOMER-REF"
    secret_subscription_id = "PRIVATE-SUBSCRIPTION-REF"
    datasets = make_datasets(
        subscription_customer_ids=(secret_customer_id,),
        snapshot_subscription_ids=(secret_subscription_id,),
    )
    datasets["usage_monthly"] = pd.DataFrame({"subscription_id": [secret_customer_id]})
    datasets["invoices"] = pd.DataFrame({"subscription_id": [secret_subscription_id]})

    findings = validate_referential_integrity(datasets)

    combined_descriptions = " ".join(finding.description for finding in findings)
    assert secret_customer_id not in combined_descriptions
    assert secret_subscription_id not in combined_descriptions
