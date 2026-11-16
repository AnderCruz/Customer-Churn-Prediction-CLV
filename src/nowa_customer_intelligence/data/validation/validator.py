"""Coordinate implemented Data Quality rules over schema-validated datasets."""

from collections.abc import Mapping
from datetime import datetime

import pandas as pd

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualityReport,
    DataQualitySeverity,
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)
from nowa_customer_intelligence.data.validation.reporting import build_data_quality_report
from nowa_customer_intelligence.data.validation.temporal_consistency import (
    validate_temporal_consistency,
)

_DATASETS = ("customers", "subscriptions", "subscription_snapshots", "usage_monthly", "invoices")
_REQUIRED_DATASETS = ("customers", "subscriptions")
_EXPECTED_RI = ("RI-001", "RI-002", "RI-003", "RI-004")
_RI_DATASETS = {
    "RI-001": ("subscriptions", "customers"),
    "RI-002": ("subscription_snapshots", "subscriptions"),
    "RI-003": ("usage_monthly", "subscriptions"),
    "RI-004": ("invoices", "subscriptions"),
}
_RI_CHILD_DATASETS = {
    "RI-001": "subscriptions",
    "RI-002": "subscription_snapshots",
    "RI-003": "usage_monthly",
    "RI-004": "invoices",
}
_REQUIRED_COLUMNS = {
    "customers": ("customer_id",),
    "subscriptions": (
        "subscription_id",
        "customer_id",
        "start_date",
        "end_date",
        "cancellation_date",
    ),
    "subscription_snapshots": ("subscription_id",),
    "usage_monthly": ("subscription_id",),
    "invoices": ("subscription_id",),
}


def _validate_datasets(datasets: Mapping[str, pd.DataFrame]) -> None:
    if not isinstance(datasets, Mapping):
        raise DataQualityValidationError(
            "datasets must be a mapping of dataset names to DataFrames"
        )

    missing = [dataset for dataset in _REQUIRED_DATASETS if dataset not in datasets]
    if missing:
        raise DataQualityValidationError(f"required dataset is missing: {missing[0]}")

    unknown = [dataset for dataset in datasets if dataset not in _DATASETS]
    if unknown:
        if not isinstance(unknown[0], str):
            raise DataQualityValidationError("dataset names must be recognized strings")
        raise DataQualityValidationError(f"unknown dataset name: {unknown[0]!r}")

    if any(not isinstance(frame, pd.DataFrame) for frame in datasets.values()):
        raise DataQualityValidationError("all supplied dataset values must be pandas DataFrames")

    for dataset, frame in datasets.items():
        missing_columns = [column for column in _REQUIRED_COLUMNS[dataset] if column not in frame]
        if missing_columns:
            raise DataQualityValidationError(
                f"schema validation precondition is not met for dataset: {dataset}"
            )


def _validate_ri_findings(
    ri_findings: tuple[DataQualityFinding, ...],
    datasets: Mapping[str, pd.DataFrame],
) -> None:
    if type(ri_findings) is not tuple or len(ri_findings) != len(_EXPECTED_RI):
        raise DataQualityValidationError("ri_findings must contain exactly RI-001 through RI-004")

    for finding, expected_rule in zip(ri_findings, _EXPECTED_RI, strict=True):
        if type(finding) is not DataQualityFinding or finding.rule_id != expected_rule:
            raise DataQualityValidationError(
                "ri_findings must contain RI-001 through RI-004 in rule order"
            )
        if finding.implementation_status is not RuleImplementationStatus.IMPLEMENTED_IN_DQ:
            raise DataQualityValidationError("RI findings must be implemented DQ rule results")
        if finding.severity is not DataQualitySeverity.ERROR:
            raise DataQualityValidationError("RI findings must have ERROR severity")
        if finding.datasets != _RI_DATASETS[expected_rule]:
            raise DataQualityValidationError("RI finding dataset attribution is inconsistent")

        child_dataset = _RI_CHILD_DATASETS.get(expected_rule)
        if child_dataset is not None and child_dataset not in datasets:
            if (
                finding.result is not RuleExecutionResult.NOT_APPLICABLE
                or finding.records_evaluated is not None
                or finding.records_affected is not None
                or finding.blocking_datasets
            ):
                raise DataQualityValidationError(
                    "an absent optional dataset must have a NOT_APPLICABLE RI result"
                )
            continue

        if finding.result is RuleExecutionResult.NOT_APPLICABLE:
            raise DataQualityValidationError(
                "a present dataset cannot have a NOT_APPLICABLE RI result"
            )
        if finding.result not in {RuleExecutionResult.PASS, RuleExecutionResult.FAIL}:
            raise DataQualityValidationError("RI results must be PASS, FAIL, or NOT_APPLICABLE")
        if finding.records_evaluated is None or finding.records_affected is None:
            raise DataQualityValidationError("evaluated RI results must include row counts")
        if finding.records_evaluated != len(datasets[child_dataset or "subscriptions"]):
            raise DataQualityValidationError(
                f"{expected_rule} evaluated row count does not match "
                f"the {child_dataset or 'subscriptions'} dataset"
            )
        if finding.records_affected > finding.records_evaluated:
            raise DataQualityValidationError("RI row counts are inconsistent")

        if finding.result is RuleExecutionResult.PASS:
            if finding.records_affected != 0 or finding.blocking_datasets:
                raise DataQualityValidationError("passing RI findings cannot block datasets")
        elif finding.records_affected == 0 or finding.blocking_datasets != finding.datasets:
            raise DataQualityValidationError("failing RI findings have inconsistent blocking scope")


def validate_data_quality(
    *,
    datasets: Mapping[str, pd.DataFrame],
    ri_findings: tuple[DataQualityFinding, ...],
    run_id: str,
    client_scope: str,
    contract_version: str = "1.1",
    specification_version: str = "0.2",
    created_at_utc: datetime | None = None,
) -> DataQualityReport:
    """Coordinate the approved DQ rules and return a DQ-only report.

    Caller precondition: header inspection, ingestion, type normalization, and Pandera
    schema validation have succeeded for every supplied dataset. This function performs
    only structural precondition checks; it does not establish or rerun schema validity.
    Referential Integrity must already have run exactly once, and its findings must be
    supplied as ``ri_findings``. The coordinator never reruns RI.

    Registry consistency, semantic attribution, workflow orchestration, submission
    acceptance, and eligibility decisions are outside this function.
    """
    _validate_datasets(datasets)
    _validate_ri_findings(ri_findings, datasets)
    temporal_findings = validate_temporal_consistency(datasets)
    findings = (*ri_findings, *temporal_findings)
    presence = {dataset: dataset in datasets for dataset in _DATASETS}
    return build_data_quality_report(
        findings=findings,
        dataset_presence=presence,
        run_id=run_id,
        client_scope=client_scope,
        contract_version=contract_version,
        specification_version=specification_version,
        created_at_utc=created_at_utc,
    )
