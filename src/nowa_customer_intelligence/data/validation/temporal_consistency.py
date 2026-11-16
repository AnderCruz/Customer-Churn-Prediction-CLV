"""Temporal consistency checks for schema-validated subscription data."""

from collections.abc import Mapping

import pandas as pd

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualitySeverity,
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)


def _evaluate_date_order(
    subscriptions: pd.DataFrame,
    *,
    rule_id: str,
    comparison_column: str,
    date_label: str,
) -> DataQualityFinding:
    """Build a finding by comparing present date pairs without modifying input data."""
    applicable = subscriptions["start_date"].notna() & subscriptions[comparison_column].notna()
    evaluated_count = int(applicable.sum())

    if evaluated_count == 0:
        return DataQualityFinding(
            rule_id=rule_id,
            implementation_status=RuleImplementationStatus.IMPLEMENTED_IN_DQ,
            severity=DataQualitySeverity.ERROR,
            result=RuleExecutionResult.NOT_APPLICABLE,
            datasets=("subscriptions",),
            description=f"No subscription records have both dates required for {rule_id}.",
            records_evaluated=None,
            records_affected=None,
            blocking_datasets=(),
        )

    violations = (
        subscriptions.loc[applicable, comparison_column]
        < subscriptions.loc[applicable, "start_date"]
    )
    affected_count = int(violations.sum())
    failed = affected_count > 0

    return DataQualityFinding(
        rule_id=rule_id,
        implementation_status=RuleImplementationStatus.IMPLEMENTED_IN_DQ,
        severity=DataQualitySeverity.ERROR,
        result=RuleExecutionResult.FAIL if failed else RuleExecutionResult.PASS,
        datasets=("subscriptions",),
        description=(
            f"One or more subscription records have {date_label} before start_date."
            if failed
            else f"All applicable subscription records satisfy the {date_label} date order."
        ),
        records_evaluated=evaluated_count,
        records_affected=affected_count,
        blocking_datasets=("subscriptions",) if failed else (),
    )


def validate_temporal_consistency(
    datasets: Mapping[str, pd.DataFrame],
) -> tuple[DataQualityFinding, ...]:
    """Evaluate TC-001 and TC-002 on schema-validated subscription data.

    Missing nullable comparison dates are excluded from the corresponding rule. The
    function reads but does not modify the mapping or its DataFrames.

    Args:
        datasets: Mapping containing the schema-validated ``subscriptions`` DataFrame.

    Returns:
        Exactly two findings in TC-001, TC-002 order.

    Raises:
        DataQualityValidationError: If the mapping is invalid, subscriptions are absent,
            or the subscriptions value is not a pandas DataFrame.
    """
    if not isinstance(datasets, Mapping):
        raise DataQualityValidationError(
            "datasets must be a mapping of dataset names to DataFrames"
        )
    if "subscriptions" not in datasets:
        raise DataQualityValidationError("required dataset is missing: subscriptions")

    subscriptions = datasets["subscriptions"]
    if not isinstance(subscriptions, pd.DataFrame):
        raise DataQualityValidationError("subscriptions dataset must be a pandas DataFrame")

    return (
        _evaluate_date_order(
            subscriptions,
            rule_id="TC-001",
            comparison_column="end_date",
            date_label="end_date",
        ),
        _evaluate_date_order(
            subscriptions,
            rule_id="TC-002",
            comparison_column="cancellation_date",
            date_label="cancellation_date",
        ),
    )
