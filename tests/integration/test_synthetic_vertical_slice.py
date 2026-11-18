"""Exercise development-only fixture export through both existing pipeline workflows."""

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    InvoiceFact,
    InvoiceStatus,
    calculate_catalogue_charge,
)
from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.customers import generate_customers
from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode
from nowa_customer_intelligence.data.synthetic.observations import SnapshotRecord, UsageRecord
from nowa_customer_intelligence.data.synthetic.projection import (
    export_development_csvs,
    project_development_population,
)
from nowa_customer_intelligence.data.synthetic.random_streams import create_random_stream
from nowa_customer_intelligence.data.synthetic.run_context import create_run_context
from nowa_customer_intelligence.data.validation.models import RuleExecutionResult
from nowa_customer_intelligence.pipeline import (
    PipelineExecutionRequest,
    PipelineOverallStatus,
    PipelineWorkflow,
    StageExecutionStatus,
    execute_pipeline,
)

_IDS = ("aaaaaaaa-1234-4234-8234-123456789abc", "bbbbbbbb-1234-7234-8234-123456789abc")
_DAY = date(2024, 3, 1)
_OBSERVED = datetime(2024, 3, 1, 12, tzinfo=UTC)


@pytest.mark.parametrize("workflow", [PipelineWorkflow.BASIC, PipelineWorkflow.TEMPORAL])
def test_fixture_exports_pass_existing_pipeline(workflow: PipelineWorkflow, tmp_path: Path) -> None:
    temporal = workflow is PipelineWorkflow.TEMPORAL
    snapshot_name = ", subscription_snapshots.csv" if temporal else ""
    document = f"""
config_schema_version: 1
base:
  population: {{customer_count: 2, episode_count_min: 2, episode_count_max: 2}}
  history: {{start_date: '2024-01-01', cutoff_date: '2024-03-31'}}
  master_seed: 42
  workflow: {workflow.value}
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv,
                      usage_monthly.csv, invoices.csv{snapshot_name}]
  policy_refs: {{contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}}
scenarios: {{baseline: {{scenario_version: 1}}}}
""".encode()
    effective = resolve_configuration(load_configuration(document), "baseline")
    context = create_run_context(effective)
    stream = create_random_stream(effective.master_seed, "vertical-fixture", namespace="baseline")
    assert stream.bit_generator.state["bit_generator"] == "PCG64"
    customers = generate_customers(context.effective_configuration)
    episodes = tuple(
        SubscriptionEpisode(key, customer.customer_id, customer.created_at, EpisodeStatus.ACTIVE)
        for key, customer in zip(_IDS, customers, strict=True)
    )
    episodes = (
        episodes[0],
        replace(
            episodes[1],
            subscription_status=EpisodeStatus.CANCELLED,
            end_date=date(2024, 3, 31),
            cancellation_date=date(2024, 3, 31),
        ),
    )
    # Explicit fixture dates and amounts, independent of scheduling and lifecycle policy.
    charge = calculate_catalogue_charge("launch", BillingFrequency.ANNUAL)
    invoice = InvoiceFact("fixture-1", _IDS[0], _DAY, charge.invoice_amount, InvoiceStatus.PENDING)
    usage = UsageRecord(
        _IDS[0], _DAY, _DAY, date(2024, 3, 31), 2, 3, 4, 5, Decimal("12.50"), "fixture_metric"
    )
    snapshots = (
        [
            SnapshotRecord(
                _IDS[0],
                _DAY,
                EpisodeStatus.TRIAL,
                _OBSERVED,
                _OBSERVED,
                _OBSERVED,
                _OBSERVED,
                "launch",
                BillingFrequency.ANNUAL,
                charge.recurring_revenue,
                "GBP",
                False,
            )
        ]
        if temporal
        else None
    )
    tables = project_development_population(
        effective, customers, episodes, usage=[usage], invoices=[invoice], snapshots=snapshots
    )
    counts = {table.dataset: len(table.rows) for table in tables}
    expected = {"customers": 2, "subscriptions": 2, "usage_monthly": 1, "invoices": 1}
    if temporal:
        expected["subscription_snapshots"] = 1
    assert counts == expected
    assert not list(tmp_path.iterdir())

    directory = tmp_path / "fixture-export"
    directory.mkdir()
    sources = export_development_csvs(directory, tables)
    assert set(tmp_path.iterdir()) == {directory}
    assert set(directory.iterdir()) == set(sources.values())
    assert "observed_at" not in "".join(path.read_text() for path in sources.values())
    assert "period_start" not in sources["usage_monthly"].read_text()
    request = PipelineExecutionRequest(
        run_id="development-fixture-validation",
        client_scope="fixture",
        workflow=workflow,
        dataset_sources=sources,
        execution_intent="development fixture validation",
    )
    result = execute_pipeline(request)
    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert result.summary.run_id != context.run_id
    assert context.generated_inventory == ()
    assert result.summary.dataset_presence["subscription_snapshots"] is temporal
    stages = {stage.stage_id: stage.status for stage in result.summary.stages}
    for name in ("schema_validation", "referential_integrity", "data_quality"):
        assert stages[name] is StageExecutionStatus.SUCCEEDED
    assert result.dq_report is not None
    findings = {finding.rule_id: finding.result for finding in result.dq_report.findings}
    for rule in ("RI-001", "RI-003", "RI-004"):
        assert findings[rule] is RuleExecutionResult.PASS
    assert findings["RI-002"] is (
        RuleExecutionResult.PASS if temporal else RuleExecutionResult.NOT_APPLICABLE
    )
    assert findings["TC-001"] is RuleExecutionResult.PASS
    assert findings["TC-002"] is RuleExecutionResult.PASS
    assert RuleExecutionResult.FAIL not in findings.values()
    assert RuleExecutionResult.NOT_EVALUATED not in findings.values()
