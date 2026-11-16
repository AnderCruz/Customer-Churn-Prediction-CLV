"""Build immutable Data Quality reports from rule findings."""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import uuid4

from nowa_customer_intelligence.data.validation.models import (
    DataQualityFinding,
    DataQualityReport,
    DataQualitySeverity,
    DataQualitySummary,
    DataQualityValidationError,
    RuleExecutionResult,
    RuleImplementationStatus,
)

_DATASETS = ("customers", "subscriptions", "subscription_snapshots", "usage_monthly", "invoices")
_UNIMPLEMENTED_STATUSES = {
    RuleImplementationStatus.PROPOSED,
    RuleImplementationStatus.PENDING_DECISION,
    RuleImplementationStatus.DEFERRED,
}


def _validate_findings(findings: Sequence[DataQualityFinding]) -> tuple[DataQualityFinding, ...]:
    """Validate report inputs without modifying or interpreting rule outcomes."""
    if isinstance(findings, (str, bytes)) or not isinstance(findings, Sequence):
        raise DataQualityValidationError("findings must be a sequence of DataQualityFinding values")

    copied = tuple(findings)
    rule_ids: set[str] = set()
    for finding in copied:
        if type(finding) is not DataQualityFinding:
            raise DataQualityValidationError("findings must contain DataQualityFinding values")
        if finding.rule_id in rule_ids:
            raise DataQualityValidationError("findings must not contain duplicate rule IDs")
        rule_ids.add(finding.rule_id)

        if finding.implementation_status is RuleImplementationStatus.ALREADY_IMPLEMENTED:
            raise DataQualityValidationError(
                "checks owned by another validation layer cannot be DQ findings"
            )
        if (
            finding.implementation_status in _UNIMPLEMENTED_STATUSES
            and finding.result is not RuleExecutionResult.NOT_EVALUATED
        ):
            raise DataQualityValidationError("unimplemented rules must have a NOT_EVALUATED result")

        for count_name, count_value in (
            ("records_evaluated", finding.records_evaluated),
            ("records_affected", finding.records_affected),
        ):
            if count_value is not None and (
                not isinstance(count_value, int) or isinstance(count_value, bool) or count_value < 0
            ):
                raise DataQualityValidationError(
                    f"{count_name} must be a non-negative integer or None"
                )

        if (
            finding.records_evaluated is not None
            and finding.records_affected is not None
            and finding.records_affected > finding.records_evaluated
        ):
            raise DataQualityValidationError("affected row count exceeds evaluated row count")

        if finding.result is RuleExecutionResult.PASS:
            if finding.records_evaluated is None or finding.records_affected is None:
                raise DataQualityValidationError("PASS findings must include integer row counts")
            if finding.records_affected != 0:
                raise DataQualityValidationError("PASS findings must have zero affected rows")
            if finding.blocking_datasets:
                raise DataQualityValidationError("PASS findings cannot have blocking datasets")

        if finding.result is RuleExecutionResult.FAIL:
            if finding.records_evaluated is None or finding.records_affected is None:
                raise DataQualityValidationError("FAIL findings must include integer row counts")
            if finding.records_affected == 0:
                raise DataQualityValidationError("FAIL findings must have affected rows")

        if finding.result in {
            RuleExecutionResult.NOT_APPLICABLE,
            RuleExecutionResult.NOT_EVALUATED,
        } and (finding.records_evaluated is not None or finding.records_affected is not None):
            raise DataQualityValidationError(
                "NOT_APPLICABLE and NOT_EVALUATED findings must not contain row counts"
            )
        if (
            finding.result
            in {
                RuleExecutionResult.NOT_APPLICABLE,
                RuleExecutionResult.NOT_EVALUATED,
            }
            and finding.blocking_datasets
        ):
            raise DataQualityValidationError(
                "NOT_APPLICABLE and NOT_EVALUATED findings cannot block datasets"
            )
        if (
            finding.severity is DataQualitySeverity.ERROR
            and finding.result is RuleExecutionResult.FAIL
            and (
                not finding.blocking_datasets
                or any(dataset not in finding.datasets for dataset in finding.blocking_datasets)
            )
        ):
            raise DataQualityValidationError(
                "failing ERROR findings must identify their blocking datasets"
            )
    return copied


def _validate_presence(dataset_presence: Mapping[str, bool]) -> dict[str, bool]:
    if not isinstance(dataset_presence, Mapping):
        raise DataQualityValidationError("dataset_presence must be a mapping")

    if set(dataset_presence) != set(_DATASETS):
        raise DataQualityValidationError(
            "dataset_presence must identify all five contract datasets"
        )
    if any(not isinstance(value, bool) for value in dataset_presence.values()):
        raise DataQualityValidationError("dataset_presence values must be booleans")
    return {dataset: dataset_presence[dataset] for dataset in _DATASETS}


def build_data_quality_report(
    *,
    findings: Sequence[DataQualityFinding],
    dataset_presence: Mapping[str, bool],
    run_id: str,
    client_scope: str,
    contract_version: str = "1.1",
    specification_version: str = "0.2",
    created_at_utc: datetime | None = None,
) -> DataQualityReport:
    """Aggregate supplied findings into a DQ-only report.

    This function performs no rule evaluation, dataset validation, serialization, or
    persistence. ``client_scope`` must be a pseudonymous value supplied by the caller.
    """
    report_findings = _validate_findings(findings)
    presence = _validate_presence(dataset_presence)

    result_counts = {result: 0 for result in RuleExecutionResult}
    severity_counts = {severity: 0 for severity in DataQualitySeverity}
    blocked_datasets: list[str] = []
    seen_blocked: set[str] = set()

    for finding in report_findings:
        result_counts[finding.result] += 1
        if finding.result is RuleExecutionResult.FAIL:
            severity_counts[finding.severity] += 1
        if (
            finding.severity is DataQualitySeverity.ERROR
            and finding.result is RuleExecutionResult.FAIL
        ):
            for dataset in finding.blocking_datasets:
                if dataset not in seen_blocked:
                    blocked_datasets.append(dataset)
                    seen_blocked.add(dataset)

    summary = DataQualitySummary(
        severity_counts=severity_counts,
        result_counts=result_counts,
        blocked=bool(blocked_datasets),
        blocked_datasets=tuple(blocked_datasets),
    )
    return DataQualityReport(
        report_id=str(uuid4()),
        run_id=run_id,
        client_scope=client_scope,
        created_at_utc=created_at_utc or datetime.now(UTC),
        contract_version=contract_version,
        specification_version=specification_version,
        pipeline_stage="data_quality_validation",
        dataset_presence=presence,
        summary=summary,
        findings=report_findings,
    )
