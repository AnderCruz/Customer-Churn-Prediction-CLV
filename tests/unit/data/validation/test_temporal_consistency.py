"""Unit tests for temporal consistency rules TC-001 and TC-002."""

from collections import UserDict

import pandas as pd
import pytest

from nowa_customer_intelligence.data.validation.models import (
    DataQualitySeverity,
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)
from nowa_customer_intelligence.data.validation.temporal_consistency import (
    validate_temporal_consistency,
)


def make_subscriptions(
    start_dates: tuple[str, ...] = ("2025-01-01",),
    end_dates: tuple[str | None, ...] = ("2025-02-01",),
    cancellation_dates: tuple[str | None, ...] = ("2025-03-01",),
) -> pd.DataFrame:
    """Build a synthetic DataFrame with normalized UTC-aware datetime columns."""
    return pd.DataFrame(
        {
            "start_date": pd.to_datetime(start_dates, utc=True),
            "end_date": pd.to_datetime(end_dates, utc=True),
            "cancellation_date": pd.to_datetime(cancellation_dates, utc=True),
        }
    )


def test_returns_exactly_two_findings_in_rule_order() -> None:
    findings = validate_temporal_consistency({"subscriptions": make_subscriptions()})

    assert [finding.rule_id for finding in findings] == ["TC-001", "TC-002"]


@pytest.mark.parametrize("rule_index", [0, 1])
def test_equal_dates_are_valid(rule_index: int) -> None:
    subscriptions = make_subscriptions(
        start_dates=("2025-01-01",),
        end_dates=("2025-01-01",),
        cancellation_dates=("2025-01-01",),
    )

    finding = validate_temporal_consistency({"subscriptions": subscriptions})[rule_index]

    assert finding.result is RuleExecutionResult.PASS
    assert finding.records_evaluated == 1
    assert finding.records_affected == 0


@pytest.mark.parametrize(
    ("rule_index", "end_dates", "cancellation_dates"),
    [
        (0, ("2024-12-31",), ("2025-03-01",)),
        (1, ("2025-02-01",), ("2024-12-31",)),
    ],
)
def test_earlier_comparison_date_fails_and_blocks_subscriptions(
    rule_index: int,
    end_dates: tuple[str | None, ...],
    cancellation_dates: tuple[str | None, ...],
) -> None:
    subscriptions = make_subscriptions(
        end_dates=end_dates,
        cancellation_dates=cancellation_dates,
    )

    finding = validate_temporal_consistency({"subscriptions": subscriptions})[rule_index]

    assert finding.result is RuleExecutionResult.FAIL
    assert finding.records_evaluated == 1
    assert finding.records_affected == 1
    assert finding.blocking_datasets == ("subscriptions",)


def test_tc_001_mixed_dates_excludes_missing_end_without_using_cancellation() -> None:
    subscriptions = make_subscriptions(
        start_dates=("2025-01-01", "2025-01-01", "2025-01-01"),
        end_dates=("2025-02-01", "2024-12-31", None),
        cancellation_dates=(None, None, "2024-01-01"),
    )

    tc_001, tc_002 = validate_temporal_consistency({"subscriptions": subscriptions})

    assert (tc_001.result, tc_001.records_evaluated, tc_001.records_affected) == (
        RuleExecutionResult.FAIL,
        2,
        1,
    )
    assert tc_002.result is RuleExecutionResult.FAIL
    assert tc_002.records_evaluated == 1
    assert tc_002.records_affected == 1


def test_tc_002_mixed_dates_excludes_missing_cancellation_independently() -> None:
    subscriptions = make_subscriptions(
        start_dates=("2025-01-01", "2025-01-01", "2025-01-01"),
        end_dates=(None, "2024-12-31", "2025-02-01"),
        cancellation_dates=("2025-02-01", "2024-12-31", None),
    )

    tc_001, tc_002 = validate_temporal_consistency({"subscriptions": subscriptions})

    assert tc_001.records_evaluated == 2
    assert tc_001.records_affected == 1
    assert tc_002.records_evaluated == 2
    assert tc_002.records_affected == 1


@pytest.mark.parametrize(
    ("end_dates", "cancellation_dates", "expected_rule"),
    [
        ((None, None), ("2025-02-01", "2025-02-01"), "TC-001"),
        (("2025-02-01", "2025-02-01"), (None, None), "TC-002"),
    ],
)
def test_no_applicable_records_returns_not_applicable(
    end_dates: tuple[str | None, ...],
    cancellation_dates: tuple[str | None, ...],
    expected_rule: str,
) -> None:
    findings = validate_temporal_consistency(
        {
            "subscriptions": make_subscriptions(
                start_dates=("2025-01-01", "2025-01-01"),
                end_dates=end_dates,
                cancellation_dates=cancellation_dates,
            )
        }
    )
    finding = next(item for item in findings if item.rule_id == expected_rule)

    assert finding.result is RuleExecutionResult.NOT_APPLICABLE
    assert finding.records_evaluated is None
    assert finding.records_affected is None
    assert finding.blocking_datasets == ()


def test_empty_subscriptions_is_not_applicable_for_both_rules() -> None:
    subscriptions = make_subscriptions((), (), ())

    findings = validate_temporal_consistency({"subscriptions": subscriptions})

    assert [finding.result for finding in findings] == [
        RuleExecutionResult.NOT_APPLICABLE,
        RuleExecutionResult.NOT_APPLICABLE,
    ]


def test_findings_have_expected_metadata_and_scope() -> None:
    findings = validate_temporal_consistency({"subscriptions": make_subscriptions()})

    assert all(
        finding.implementation_status is RuleImplementationStatus.IMPLEMENTED_IN_DQ
        for finding in findings
    )
    assert all(finding.severity is DataQualitySeverity.ERROR for finding in findings)
    assert all(finding.datasets == ("subscriptions",) for finding in findings)
    assert all(finding.records_evaluated == 1 for finding in findings)
    assert all(finding.records_affected == 0 for finding in findings)
    assert all(finding.blocking_datasets == () for finding in findings)


def test_unknown_recognised_dataset_is_ignored() -> None:
    datasets = {
        "subscriptions": make_subscriptions(),
        "usage_monthly": pd.DataFrame({"unrelated": [object()]}),
    }

    assert len(validate_temporal_consistency(datasets)) == 2


def test_requires_mapping_and_required_subscriptions_dataframe() -> None:
    with pytest.raises(DataQualityValidationError, match="datasets must be a mapping"):
        validate_temporal_consistency([("subscriptions", make_subscriptions())])  # type: ignore[arg-type]

    with pytest.raises(DataQualityValidationError, match="required dataset is missing"):
        validate_temporal_consistency({})

    with pytest.raises(DataQualityValidationError, match="must be a pandas DataFrame"):
        validate_temporal_consistency({"subscriptions": "private-value"})  # type: ignore[dict-item]


def test_accepts_mapping_interface_and_exceptions_do_not_expose_values() -> None:
    findings = validate_temporal_consistency(UserDict({"subscriptions": make_subscriptions()}))
    assert len(findings) == 2

    marker = "DO-NOT-LEAK"
    with pytest.raises(DataQualityValidationError) as error:
        validate_temporal_consistency({"subscriptions": marker})  # type: ignore[dict-item]
    assert marker not in str(error.value)


def test_descriptions_do_not_expose_date_values() -> None:
    subscriptions = make_subscriptions(
        start_dates=("2040-01-01",),
        end_dates=("2030-01-01",),
        cancellation_dates=("2029-01-01",),
    )

    findings = validate_temporal_consistency({"subscriptions": subscriptions})

    assert all("2040-01-01" not in finding.description for finding in findings)
    assert all("2030-01-01" not in finding.description for finding in findings)
    assert all("2029-01-01" not in finding.description for finding in findings)


def test_does_not_modify_input_mapping_or_dataframe() -> None:
    subscriptions = make_subscriptions(
        end_dates=("2024-12-31",),
        cancellation_dates=(None,),
    )
    before = subscriptions.copy(deep=True)
    datasets = {"subscriptions": subscriptions}

    validate_temporal_consistency(datasets)

    assert list(datasets) == ["subscriptions"]
    pd.testing.assert_frame_equal(subscriptions, before)
