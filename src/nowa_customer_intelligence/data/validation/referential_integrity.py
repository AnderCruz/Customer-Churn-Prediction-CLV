"""Referential integrity checks across schema-validated client datasets."""

from collections.abc import Mapping

import pandas as pd

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualitySeverity,
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)

_REQUIRED_DATASETS = ("customers", "subscriptions")
_ACCEPTED_DATASETS = frozenset(
    (*_REQUIRED_DATASETS, "subscription_snapshots", "usage_monthly", "invoices")
)


def _make_finding(
    *,
    rule_id: str,
    child_dataset: str,
    parent_dataset: str,
    evaluated_count: int,
    affected_count: int,
    pass_description: str,
    fail_description: str,
) -> DataQualityFinding:
    """Create a finding with the common severity and implementation status."""
    result = RuleExecutionResult.FAIL if affected_count else RuleExecutionResult.PASS
    blocking_datasets = (child_dataset, parent_dataset) if affected_count else ()
    return DataQualityFinding(
        rule_id=rule_id,
        implementation_status=RuleImplementationStatus.IMPLEMENTED_IN_DQ,
        severity=DataQualitySeverity.ERROR,
        result=result,
        datasets=(child_dataset, parent_dataset),
        description=fail_description if affected_count else pass_description,
        records_evaluated=evaluated_count,
        records_affected=affected_count,
        blocking_datasets=blocking_datasets,
    )


def _evaluate_reference(
    *,
    child: pd.DataFrame,
    parent: pd.DataFrame,
    child_dataset: str,
    parent_dataset: str,
    child_column: str,
    parent_column: str,
    rule_id: str,
    pass_description: str,
    fail_description: str,
) -> DataQualityFinding:
    """Count source rows whose foreign key is absent from the parent key column."""
    child_identifiers = child[child_column]
    parent_identifiers = parent[parent_column]
    valid_references = child_identifiers.isin(parent_identifiers)
    affected_count = int((~valid_references).sum())

    return _make_finding(
        rule_id=rule_id,
        child_dataset=child_dataset,
        parent_dataset=parent_dataset,
        evaluated_count=len(child_identifiers),
        affected_count=affected_count,
        pass_description=pass_description,
        fail_description=fail_description,
    )


def _not_applicable_finding(
    *,
    rule_id: str,
    child_dataset: str,
    parent_dataset: str,
    description: str,
) -> DataQualityFinding:
    """Create a result for an RI rule whose optional child dataset is absent."""
    return DataQualityFinding(
        rule_id=rule_id,
        implementation_status=RuleImplementationStatus.IMPLEMENTED_IN_DQ,
        severity=DataQualitySeverity.ERROR,
        result=RuleExecutionResult.NOT_APPLICABLE,
        datasets=(child_dataset, parent_dataset),
        description=description,
        records_evaluated=None,
        records_affected=None,
        blocking_datasets=(),
    )


def validate_referential_integrity(
    datasets: Mapping[str, pd.DataFrame],
) -> tuple[DataQualityFinding, ...]:
    """Evaluate RI-001 through RI-004 on schema-validated DataFrames.

    Identifier values are compared as supplied. This function does not normalize values,
    modify input DataFrames, or rerun schemas. RI-002, RI-003, and RI-004 are not
    applicable when their optional child datasets are absent.

    Args:
        datasets: Mapping of contract dataset names to schema-validated DataFrames.

    Returns:
        Exactly four findings in RI-001, RI-002, RI-003, RI-004 order.

    Raises:
        DataQualityValidationError: If the mapping is invalid, a required dataset is
            missing, or any supplied dataset value is not a pandas DataFrame.
    """
    if not isinstance(datasets, Mapping):
        raise DataQualityValidationError(
            "datasets must be a mapping of dataset names to DataFrames"
        )

    missing_datasets = [name for name in _REQUIRED_DATASETS if name not in datasets]
    if missing_datasets:
        raise DataQualityValidationError(f"required dataset is missing: {missing_datasets[0]}")

    unknown_datasets = [name for name in datasets if name not in _ACCEPTED_DATASETS]
    if unknown_datasets:
        unknown_name = unknown_datasets[0]
        if not isinstance(unknown_name, str):
            raise DataQualityValidationError("dataset names must be recognized strings")
        raise DataQualityValidationError(f"unknown dataset name: {unknown_name!r}")

    if any(not isinstance(dataframe, pd.DataFrame) for dataframe in datasets.values()):
        raise DataQualityValidationError("all supplied dataset values must be pandas DataFrames")

    customers = datasets["customers"]
    subscriptions = datasets["subscriptions"]

    ri_001 = _evaluate_reference(
        child=subscriptions,
        parent=customers,
        child_dataset="subscriptions",
        parent_dataset="customers",
        child_column="customer_id",
        parent_column="customer_id",
        rule_id="RI-001",
        pass_description="All subscription customer references match the customers dataset.",
        fail_description=(
            "One or more subscription records reference customers absent "
            "from the customers dataset."
        ),
    )
    if "subscription_snapshots" in datasets:
        ri_002 = _evaluate_reference(
            child=datasets["subscription_snapshots"],
            parent=subscriptions,
            child_dataset="subscription_snapshots",
            parent_dataset="subscriptions",
            child_column="subscription_id",
            parent_column="subscription_id",
            rule_id="RI-002",
            pass_description=(
                "All snapshot subscription references match the subscriptions dataset."
            ),
            fail_description=(
                "One or more snapshot records reference subscriptions absent "
                "from the subscriptions dataset."
            ),
        )
    else:
        ri_002 = _not_applicable_finding(
            rule_id="RI-002",
            child_dataset="subscription_snapshots",
            parent_dataset="subscriptions",
            description=(
                "The optional subscription_snapshots dataset is absent; RI-002 is not applicable."
            ),
        )

    if "usage_monthly" in datasets:
        ri_003 = _evaluate_reference(
            child=datasets["usage_monthly"],
            parent=subscriptions,
            child_dataset="usage_monthly",
            parent_dataset="subscriptions",
            child_column="subscription_id",
            parent_column="subscription_id",
            rule_id="RI-003",
            pass_description="All usage subscription references match the subscriptions dataset.",
            fail_description=(
                "One or more usage records reference subscriptions absent "
                "from the subscriptions dataset."
            ),
        )
    else:
        ri_003 = _not_applicable_finding(
            rule_id="RI-003",
            child_dataset="usage_monthly",
            parent_dataset="subscriptions",
            description="The optional usage_monthly dataset is absent; RI-003 is not applicable.",
        )

    if "invoices" in datasets:
        ri_004 = _evaluate_reference(
            child=datasets["invoices"],
            parent=subscriptions,
            child_dataset="invoices",
            parent_dataset="subscriptions",
            child_column="subscription_id",
            parent_column="subscription_id",
            rule_id="RI-004",
            pass_description="All invoice subscription references match the subscriptions dataset.",
            fail_description=(
                "One or more invoice records reference subscriptions absent "
                "from the subscriptions dataset."
            ),
        )
    else:
        ri_004 = _not_applicable_finding(
            rule_id="RI-004",
            child_dataset="invoices",
            parent_dataset="subscriptions",
            description="The optional invoices dataset is absent; RI-004 is not applicable.",
        )

    return (ri_001, ri_002, ri_003, ri_004)
