"""End-to-end tests for the public MVP pipeline entry point."""

from pathlib import Path
from unittest.mock import patch

import pytest

from nowa_customer_intelligence.data.validation.models import (
    DataQualityValidationError,
    RuleExecutionResult,
)
from nowa_customer_intelligence.data.validation.temporal_consistency import (
    validate_temporal_consistency,
)
from nowa_customer_intelligence.pipeline import (
    DatasetDiscoveryError,
    PipelineExecutionRequest,
    PipelineOperationalInputError,
    PipelineOverallStatus,
    PipelineWorkflow,
    StageExecutionStatus,
    execute_pipeline,
)
from nowa_customer_intelligence.pipeline import (
    execution as execution_module,
)
from nowa_customer_intelligence.pipeline import (
    quality as quality_module,
)
from nowa_customer_intelligence.pipeline.aggregation import determine_pipeline_overall_status

_VALID_CSV = {
    "customers": "customer_id,created_at\nC1,2025-01-01\n",
    "subscriptions": (
        "subscription_id,customer_id,start_date,subscription_status,end_date,cancellation_date\n"
        "S1,C1,2025-01-01,active,2025-03-01,\n"
    ),
    "subscription_snapshots": "subscription_id,snapshot_date,subscription_status\n"
    "S1,2025-02-01,active\n",
    "usage_monthly": "subscription_id,usage_month,active_users,total_users\nS1,2025-02-01,1,2\n",
    "invoices": "invoice_id,subscription_id,invoice_date,amount,currency,invoice_status\n"
    "I1,S1,2025-02-01,10.00,USD,paid\n",
}


def _sources(
    tmp_path: Path,
    names: set[str],
    overrides: dict[str, str] | None = None,
) -> dict[str, Path]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    result = {}
    for dataset in sorted(names):
        path = tmp_path / f"{dataset}.csv"
        path.write_text((overrides or {}).get(dataset, _VALID_CSV[dataset]), encoding="utf-8")
        result[dataset] = path
    return result


def _request(
    sources: dict[str, Path], workflow: PipelineWorkflow = PipelineWorkflow.BASIC
) -> PipelineExecutionRequest:
    return PipelineExecutionRequest(
        run_id="e2e-run-1",
        client_scope="pseudonymous-client-1",
        workflow=workflow,
        dataset_sources=sources,
        execution_intent="opaque-requested-operation",
    )


def _stage(result, stage_id: str):
    return next(stage for stage in result.summary.stages if stage.stage_id == stage_id)


def test_basic_required_datasets_valid_and_all_optional_absent(tmp_path: Path) -> None:
    result = execute_pipeline(_request(_sources(tmp_path, {"customers", "subscriptions"})))

    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert result.summary.dataset_presence == {
        "customers": True,
        "subscriptions": True,
        "subscription_snapshots": False,
        "usage_monthly": False,
        "invoices": False,
    }
    assert result.dq_report is not None
    assert result.dq_report.findings[1].result is RuleExecutionResult.NOT_APPLICABLE
    assert result.dq_report.findings[2].result is RuleExecutionResult.NOT_APPLICABLE
    assert result.dq_report.findings[3].result is RuleExecutionResult.NOT_APPLICABLE


def test_basic_all_five_datasets_valid(tmp_path: Path) -> None:
    result = execute_pipeline(_request(_sources(tmp_path, set(_VALID_CSV))))

    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert all(result.summary.dataset_presence.values())
    assert result.dq_report is not None
    assert [finding.rule_id for finding in result.dq_report.findings] == [
        "RI-001",
        "RI-002",
        "RI-003",
        "RI-004",
        "TC-001",
        "TC-002",
    ]


@pytest.mark.parametrize(
    "optional_dataset",
    ["subscription_snapshots", "usage_monthly", "invoices"],
)
def test_basic_present_empty_optional_datasets_are_allowed(
    tmp_path: Path,
    optional_dataset: str,
) -> None:
    empty_overrides = {
        "subscription_snapshots": "subscription_id,snapshot_date,subscription_status\n",
        "usage_monthly": "subscription_id,usage_month,active_users,total_users\n",
        "invoices": "invoice_id,subscription_id,invoice_date,amount,currency,invoice_status\n",
    }
    sources = _sources(
        tmp_path,
        {"customers", "subscriptions", optional_dataset},
        {optional_dataset: empty_overrides[optional_dataset]},
    )

    result = execute_pipeline(_request(sources))

    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert result.summary.dataset_presence[optional_dataset] is True
    assert result.dq_report is not None
    assert _stage(result, "schema_validation").status is StageExecutionStatus.SUCCEEDED


@pytest.mark.parametrize(
    ("workflow", "empty_dataset"),
    [
        (PipelineWorkflow.BASIC, "customers"),
        (PipelineWorkflow.BASIC, "subscriptions"),
        (PipelineWorkflow.TEMPORAL, "customers"),
        (PipelineWorkflow.TEMPORAL, "subscriptions"),
        (PipelineWorkflow.TEMPORAL, "subscription_snapshots"),
    ],
)
def test_present_empty_required_datasets_raise_operational_input_error(
    tmp_path: Path,
    workflow: PipelineWorkflow,
    empty_dataset: str,
) -> None:
    empty_headers = {
        "customers": "customer_id,created_at\n",
        "subscriptions": "subscription_id,customer_id,start_date,subscription_status\n",
        "subscription_snapshots": "subscription_id,snapshot_date,subscription_status\n",
    }
    supplied = {"customers", "subscriptions"}
    if workflow is PipelineWorkflow.TEMPORAL:
        supplied.add("subscription_snapshots")
    sources = _sources(tmp_path, supplied, {empty_dataset: empty_headers[empty_dataset]})
    request = _request(sources, workflow)
    with (
        patch.object(
            quality_module,
            "validate_referential_integrity",
            side_effect=AssertionError("RI must not execute for empty required input"),
        ) as ri_spy,
        patch.object(
            quality_module,
            "validate_data_quality",
            side_effect=AssertionError("DQ must not execute for empty required input"),
        ) as dq_spy,
        pytest.raises(PipelineOperationalInputError) as error,
    ):
        execute_pipeline(request)

    ri_spy.assert_not_called()
    dq_spy.assert_not_called()
    assert error.value.request is request
    assert error.value.dataset == empty_dataset
    assert error.value.discovery.stage_result.status is StageExecutionStatus.SUCCEEDED
    assert error.value.discovery.dataset_presence[empty_dataset] is True
    schema_stage = next(
        stage
        for stage in error.value.technical_result.stage_results
        if stage.stage_id == "schema_validation"
    )
    assert schema_stage.status is StageExecutionStatus.SUCCEEDED
    assert error.value.technical_result.discovery is error.value.discovery
    assert not hasattr(error.value, "summary")
    assert not hasattr(error.value, "dq_report")
    error_text = str(error.value)
    assert str(tmp_path) not in error_text
    assert "C1" not in error_text
    assert "2025-01-01" not in error_text


def test_missing_required_dataset_is_recorded_as_discovery_block(tmp_path: Path) -> None:
    result = execute_pipeline(_request(_sources(tmp_path, {"subscriptions"})))

    assert _stage(result, "dataset_discovery").status is StageExecutionStatus.BLOCKED
    assert _stage(result, "referential_integrity").status is StageExecutionStatus.BLOCKED
    assert _stage(result, "data_quality").status is StageExecutionStatus.BLOCKED
    assert result.summary.overall_status is PipelineOverallStatus.BLOCKED
    assert result.dq_report is None


def test_basic_supplied_optional_schema_failure_blocks_ri_and_dq(tmp_path: Path) -> None:
    sources = _sources(
        tmp_path,
        {"customers", "subscriptions", "usage_monthly"},
        {"usage_monthly": "subscription_id,usage_month,active_users\nS1,2025-02-01,-1\n"},
    )

    result = execute_pipeline(_request(sources))

    usage_outcome = next(
        outcome
        for outcome in _stage(result, "schema_validation").dataset_results
        if outcome.dataset == "usage_monthly"
    )
    assert usage_outcome.status is StageExecutionStatus.FAILED
    assert _stage(result, "schema_validation").status is StageExecutionStatus.PARTIAL
    assert _stage(result, "referential_integrity").status is StageExecutionStatus.BLOCKED
    assert _stage(result, "data_quality").status is StageExecutionStatus.BLOCKED
    assert result.dq_report is None
    assert result.summary.dq_report_id is None


def test_temporal_valid_required_datasets_and_optional_absence(tmp_path: Path) -> None:
    result = execute_pipeline(
        _request(
            _sources(tmp_path, {"customers", "subscriptions", "subscription_snapshots"}),
            PipelineWorkflow.TEMPORAL,
        )
    )

    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    snapshot_outcome = next(
        outcome
        for outcome in _stage(result, "dataset_discovery").dataset_results
        if outcome.dataset == "subscription_snapshots"
    )
    assert snapshot_outcome.requirement.name == "REQUIRED"
    assert result.summary.dataset_presence["usage_monthly"] is False
    assert result.summary.dataset_presence["invoices"] is False


def test_temporal_all_five_datasets_valid(tmp_path: Path) -> None:
    result = execute_pipeline(
        _request(_sources(tmp_path, set(_VALID_CSV)), PipelineWorkflow.TEMPORAL)
    )

    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert all(result.summary.dataset_presence.values())
    assert result.dq_report is not None
    assert result.summary.dq_report_id == result.dq_report.report_id


def test_temporal_missing_required_snapshots_blocks(tmp_path: Path) -> None:
    result = execute_pipeline(
        _request(
            _sources(tmp_path, {"customers", "subscriptions"}),
            PipelineWorkflow.TEMPORAL,
        )
    )

    assert _stage(result, "dataset_discovery").status is StageExecutionStatus.BLOCKED
    assert _stage(result, "referential_integrity").status is StageExecutionStatus.BLOCKED
    assert _stage(result, "data_quality").status is StageExecutionStatus.BLOCKED
    assert result.dq_report is None


def test_temporal_optional_usage_and_invoice_empty_are_allowed(tmp_path: Path) -> None:
    sources = _sources(
        tmp_path,
        set(_VALID_CSV),
        {
            "usage_monthly": "subscription_id,usage_month,active_users,total_users\n",
            "invoices": "invoice_id,subscription_id,invoice_date,amount,currency,invoice_status\n",
        },
    )

    result = execute_pipeline(_request(sources, PipelineWorkflow.TEMPORAL))

    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert result.dq_report is not None
    assert result.dq_report.dataset_presence["usage_monthly"] is True
    assert result.dq_report.dataset_presence["invoices"] is True


@pytest.mark.parametrize(
    ("contents", "failed_stage", "blocked_stage"),
    [
        ("wrong,header\nvalue,value\n", "header_inspection", "csv_ingestion"),
        (
            "customer_id,created_at\nC1,2025-01-01,extra\n",
            "csv_ingestion",
            "type_normalization",
        ),
        (
            "customer_id,created_at\nC1,not-a-date\n",
            "type_normalization",
            "schema_validation",
        ),
        (
            "customer_id,created_at\nC1,2025-01-01\nC1,2025-01-02\n",
            "schema_validation",
            "referential_integrity",
        ),
    ],
)
def test_technical_failure_stages_are_preserved_in_final_summary(
    tmp_path: Path,
    contents: str,
    failed_stage: str,
    blocked_stage: str,
) -> None:
    sources = _sources(tmp_path, {"customers", "subscriptions"}, {"customers": contents})

    result = execute_pipeline(_request(sources))

    assert _stage(result, failed_stage).status is StageExecutionStatus.FAILED
    assert _stage(result, blocked_stage).status is StageExecutionStatus.BLOCKED
    assert result.summary.overall_status is PipelineOverallStatus.FAILED
    assert tuple(stage.stage_id for stage in result.summary.stages) == (
        "dataset_discovery",
        "header_inspection",
        "csv_ingestion",
        "type_normalization",
        "schema_validation",
        "referential_integrity",
        "data_quality",
    )
    assert result.summary.overall_status is determine_pipeline_overall_status(result.summary.stages)


def test_data_row_decode_failure_is_not_reported_as_header_failure(tmp_path: Path) -> None:
    sources = _sources(tmp_path, {"customers", "subscriptions"})
    sources["customers"].write_bytes(b"customer_id,created_at\nC1,\xff\n")

    result = execute_pipeline(_request(sources))

    customer_header = next(
        item
        for item in _stage(result, "header_inspection").dataset_results
        if item.dataset == "customers"
    )
    assert customer_header.status is StageExecutionStatus.SUCCEEDED
    customer_ingestion = next(
        item
        for item in _stage(result, "csv_ingestion").dataset_results
        if item.dataset == "customers"
    )
    assert customer_ingestion.status is StageExecutionStatus.FAILED
    assert "customers.csv" not in str(result.summary.stages)
    assert "C1" not in str(result.summary.stages)


def test_ri_execution_failure_is_distinct_from_rule_failure(tmp_path: Path) -> None:
    sources = _sources(tmp_path, {"customers", "subscriptions"})
    with (
        patch.object(
            quality_module,
            "validate_referential_integrity",
            side_effect=DataQualityValidationError("private/path raw-value"),
        ) as ri_spy,
        patch.object(quality_module, "validate_data_quality") as dq_spy,
    ):
        result = execute_pipeline(_request(sources))

    ri_spy.assert_called_once()
    dq_spy.assert_not_called()
    assert _stage(result, "referential_integrity").status is StageExecutionStatus.FAILED
    assert _stage(result, "data_quality").status is StageExecutionStatus.BLOCKED
    assert result.dq_report is None
    assert "private/path" not in str(result.summary.stages)
    assert "raw-value" not in str(result.summary.stages)


def test_dq_execution_failure_preserves_ri_and_returns_no_report(tmp_path: Path) -> None:
    with patch.object(
        quality_module,
        "validate_data_quality",
        side_effect=DataQualityValidationError("private/path raw-value"),
    ) as dq_spy:
        result = execute_pipeline(_request(_sources(tmp_path, {"customers", "subscriptions"})))

    dq_spy.assert_called_once()
    assert _stage(result, "referential_integrity").status is StageExecutionStatus.SUCCEEDED
    assert _stage(result, "data_quality").status is StageExecutionStatus.FAILED
    assert result.dq_report is None
    assert result.summary.dq_report_id is None
    assert "private/path" not in str(result.summary.stages)


def test_ri_rule_fail_is_a_finding_not_an_execution_failure(tmp_path: Path) -> None:
    sources = _sources(
        tmp_path,
        {"customers", "subscriptions"},
        {
            "subscriptions": "subscription_id,customer_id,start_date,subscription_status\n"
            "S1,unknown,2025-01-01,active\n"
        },
    )

    result = execute_pipeline(_request(sources))

    assert _stage(result, "referential_integrity").status is StageExecutionStatus.SUCCEEDED
    assert result.dq_report is not None
    assert result.dq_report.findings[0].result is RuleExecutionResult.FAIL
    assert result.dq_report.summary.blocked


def test_tc_rule_fail_is_a_dq_finding_not_execution_failure(tmp_path: Path) -> None:
    sources = _sources(
        tmp_path,
        {"customers", "subscriptions"},
        {
            "subscriptions": "subscription_id,customer_id,start_date,subscription_status,end_date\n"
            "S1,C1,2025-03-01,active,2025-02-01\n"
        },
    )

    result = execute_pipeline(_request(sources))

    assert _stage(result, "data_quality").status is StageExecutionStatus.SUCCEEDED
    assert result.dq_report is not None
    tc_001 = next(finding for finding in result.dq_report.findings if finding.rule_id == "TC-001")
    assert tc_001.result is RuleExecutionResult.FAIL
    assert result.dq_report.summary.blocked


def test_discovery_rejects_invalid_source_and_unknown_dataset(tmp_path: Path) -> None:
    missing = tmp_path / "missing.csv"
    request = _request({"customers": missing})
    with pytest.raises(DatasetDiscoveryError) as error:
        execute_pipeline(request)
    assert str(missing) not in str(error.value)

    unknown_path = tmp_path / "unknown.csv"
    unknown_path.write_text("x\n", encoding="utf-8")
    with pytest.raises(DatasetDiscoveryError, match="unsupported dataset name"):
        execute_pipeline(_request({"customers": unknown_path, "unknown": unknown_path}))


def test_public_entry_point_invokes_each_pipeline_component_once(tmp_path: Path) -> None:
    sources = _sources(tmp_path, {"customers", "subscriptions"})
    with (
        patch.object(
            execution_module, "discover_datasets", wraps=execution_module.discover_datasets
        ) as discovery_spy,
        patch.object(
            execution_module,
            "run_technical_pipeline",
            wraps=execution_module.run_technical_pipeline,
        ) as technical_spy,
        patch.object(
            execution_module,
            "orchestrate_referential_integrity_and_data_quality",
            wraps=execution_module.orchestrate_referential_integrity_and_data_quality,
        ) as quality_spy,
        patch.object(
            execution_module,
            "build_final_pipeline_result",
            wraps=execution_module.build_final_pipeline_result,
        ) as finalization_spy,
        patch.object(
            quality_module,
            "validate_referential_integrity",
            wraps=quality_module.validate_referential_integrity,
        ) as ri_spy,
        patch.object(
            quality_module,
            "validate_data_quality",
            wraps=quality_module.validate_data_quality,
        ) as dq_spy,
        patch(
            "nowa_customer_intelligence.data.validation.validator.validate_temporal_consistency",
            wraps=validate_temporal_consistency,
        ) as tc_spy,
    ):
        result = execute_pipeline(_request(sources))

    for spy in (
        discovery_spy,
        technical_spy,
        quality_spy,
        finalization_spy,
        ri_spy,
        dq_spy,
        tc_spy,
    ):
        spy.assert_called_once()
    assert len(result.summary.stages) == 7
    assert result.dq_report is not None
    assert result.summary.dq_report_id == result.dq_report.report_id


def test_public_entry_point_rejects_invalid_request_type() -> None:
    with pytest.raises(TypeError, match="PipelineExecutionRequest"):
        execute_pipeline(object())  # type: ignore[arg-type]


def test_safe_errors_do_not_include_absolute_input_paths(tmp_path: Path) -> None:
    sources = _sources(tmp_path, {"customers", "subscriptions"})
    sources["customers"].write_text("invalid,header\n", encoding="utf-8")

    result = execute_pipeline(_request(sources))

    stage_text = str(result.summary.stages)
    assert str(tmp_path) not in stage_text
