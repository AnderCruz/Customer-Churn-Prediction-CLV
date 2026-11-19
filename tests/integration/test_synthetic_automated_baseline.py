"""Run the authorised fictional population at its configured baseline scale."""

import json
from dataclasses import replace
from datetime import UTC, datetime, time
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.synthetic.billing import InvoiceStatus
from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.development import (
    SCENARIO_VERSION,
    DevelopmentGenerationError,
    DevelopmentGenerationRequest,
    DevelopmentPopulation,
    DevelopmentScenario,
    generate_development_population,
)
from nowa_customer_intelligence.data.synthetic.identity_registry import EpisodeIdentityRegistry
from nowa_customer_intelligence.data.synthetic.observations import UsageAssumptions
from nowa_customer_intelligence.data.synthetic.provenance import (
    evaluate_development_acceptance,
    run_development_with_provenance,
)
from nowa_customer_intelligence.data.synthetic.semantic_validation import ValidationStatus
from nowa_customer_intelligence.data.validation.models import RuleExecutionResult
from nowa_customer_intelligence.pipeline import (
    PipelineOverallStatus,
    PipelineWorkflow,
    StageExecutionStatus,
)

_BASELINE = b"""
config_schema_version: 1
base:
  population: {customer_count: 1000, episode_count_min: 1100, episode_count_max: 1400}
  history: {start_date: '2021-04-01', cutoff_date: '2024-03-31'}
  master_seed: 42
  workflow: TEMPORAL
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv, subscription_snapshots.csv,
                      usage_monthly.csv, invoices.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios: {baseline: {scenario_version: 1}}
"""


def test_automated_baseline_replays_and_passes_both_workflows(tmp_path: Path) -> None:
    effective = resolve_configuration(load_configuration(_BASELINE), "baseline")
    directory = tmp_path / "development"
    directory.mkdir()
    request = DevelopmentGenerationRequest(
        effective,
        DevelopmentScenario(
            1200, "launch", 25, InvoiceStatus.FAILED, UsageAssumptions(2, 20, 60, 300)
        ),
        tmp_path / "registry.sqlite",
        "fieldwise-fictional",
        "baseline-test",
        datetime.combine(datetime(2024, 3, 31).date(), time.max, tzinfo=UTC),
        directory,
    )
    verified = run_development_with_provenance(request)
    result = verified.population
    acceptance = evaluate_development_acceptance(verified.provenance, directory=directory)
    assert acceptance.accepted
    assert verified.provenance.integrity is not None and verified.provenance.integrity.passed
    counts = {table.dataset: len(table.rows) for table in result.tables}
    assert counts["customers"] == 1000 and counts["subscriptions"] == 1200
    assert all(count > 0 for count in counts.values()) and len(counts) == 5
    assert len(result.exported_files) == 5
    assert set(directory.iterdir()) == set(result.exported_files)
    assert all("churn" not in table.columns for table in result.tables)
    assert sum(row.prior_subscription_id is not None for row in result.episodes) == 200
    assert len({row.episode.subscription_id for row in result.episodes}) == 1200
    assert {charge.frequency.value for charge in result.charges} == {"annual", "monthly"}
    for validation in result.validation:
        assert validation.summary.overall_status is PipelineOverallStatus.SUCCEEDED
        stages = {stage.stage_id: stage.status for stage in validation.summary.stages}
        for stage in ("schema_validation", "referential_integrity", "data_quality"):
            assert stages[stage] is StageExecutionStatus.SUCCEEDED
        assert validation.dq_report is not None
        assert all(
            finding.result in (RuleExecutionResult.PASS, RuleExecutionResult.NOT_APPLICABLE)
            for finding in validation.dq_report.findings
        )
    basic, temporal = result.validation
    assert not basic.summary.dataset_presence["subscription_snapshots"]
    assert all(temporal.summary.dataset_presence.values())
    findings = {finding.rule: finding.status for finding in result.findings}
    for rule in (
        "registry_reuse",
        "baseline_lifecycle",
        "baseline_billing",
        "feature_availability",
    ):
        assert findings[rule] is ValidationStatus.PASSED
    assert findings["target_and_eligibility"] is ValidationStatus.BLOCKED_BY_UNRESOLVED_POLICY

    replay = generate_development_population(
        replace(request, export_directory=None, validation_workflows=())
    )
    assert replay.tables == result.tables
    assert replay.episodes == result.episodes
    assert replay.charges == result.charges
    assert replay.exported_files == ()
    print(
        json.dumps(
            {
                "counts": counts,
                "first_seconds": round(result.elapsed_seconds, 3),
                "replay_seconds": round(replay.elapsed_seconds, 3),
                "pipeline": [
                    {
                        finding.rule_id: finding.result.value
                        for finding in validation.dq_report.findings
                    }
                    for validation in result.validation
                ],
                "pipeline_stages": [
                    {stage.stage_id: stage.status.value for stage in validation.summary.stages}
                    for validation in result.validation
                ],
                "semantic": {name: status.value for name, status in findings.items()},
                "acceptance": {check.gate: check.status.value for check in acceptance.gates},
                "integrity_files": len(verified.provenance.integrity.files),
            }
        )
    )


def test_fresh_registry_keeps_business_facts_and_allocates_new_identifiers(tmp_path: Path) -> None:
    small = _BASELINE.replace(b"1000", b"4").replace(b"1100", b"4").replace(b"1400", b"8")
    effective = resolve_configuration(load_configuration(small), "baseline")
    original = DevelopmentGenerationRequest(
        effective,
        DevelopmentScenario(
            5,
            "growth",
            50,
            InvoiceStatus.PENDING,
            UsageAssumptions(1, 4, 20, 40),
            activation_evidence_lag_days=20,
        ),
        tmp_path / "first.sqlite",
        "fixture",
        "fresh-registry",
        datetime(2024, 3, 31, 23, 59, 59, 999999, tzinfo=UTC),
        validation_workflows=(PipelineWorkflow.TEMPORAL,),
    )
    first = generate_development_population(original)
    second = generate_development_population(
        replace(original, registry_path=tmp_path / "second.sqlite", validation_workflows=()),
    )
    assert first.exported_files == second.exported_files == ()
    assert {path.name for path in tmp_path.iterdir()} == {"first.sqlite", "second.sqlite"}
    assert first.validation[0].summary.overall_status is PipelineOverallStatus.SUCCEEDED
    first_ids = {row.episode.subscription_id: row.identity.source_key for row in first.episodes}
    second_ids = {row.episode.subscription_id: row.identity.source_key for row in second.episodes}
    assert first_ids.keys().isdisjoint(second_ids)
    assert set(first_ids.values()) == set(second_ids.values())

    def business_usage(result: DevelopmentPopulation, identities: dict[str, str]):
        return {
            (identities[row.subscription_id], row.usage_month): (
                row.active_users,
                row.sessions_count,
                row.events_count,
            )
            for row in result.usage
        }

    assert business_usage(first, first_ids) == business_usage(second, second_ids)

    def business_charges(result: DevelopmentPopulation, identities: dict[str, str]):
        return {
            (identities[row.invoice.subscription_id], row.invoice.invoice_date): (
                row.invoice.amount,
                row.plan_id,
                row.period_end,
                row.invoice.invoice_status,
            )
            for row in result.charges
        }

    def business_snapshots(result: DevelopmentPopulation, identities: dict[str, str]):
        return {
            (identities[row.subscription_id], row.snapshot_date): (
                row.subscription_status,
                row.recurring_revenue,
                row.available_at,
            )
            for row in result.snapshots
        }

    assert business_charges(first, first_ids) == business_charges(second, second_ids)
    assert business_snapshots(first, first_ids) == business_snapshots(second, second_ids)

    with pytest.raises(DevelopmentGenerationError, match="empty development export"):
        replace(original, export_directory=tmp_path)
    with pytest.raises(DevelopmentGenerationError, match="observation cutoff"):
        replace(original, observation_cutoff=datetime(2024, 3, 31))
    with pytest.raises(DevelopmentGenerationError, match="identity scopes"):
        replace(original, source_namespace="")
    with pytest.raises(DevelopmentGenerationError, match="authorised development"):
        generate_development_population(effective)


def test_failed_export_rolls_back_csvs_and_never_invokes_pipeline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    small = _BASELINE.replace(b"1000", b"3").replace(b"1100", b"3").replace(b"1400", b"6")
    effective = resolve_configuration(load_configuration(small), "baseline")
    export = tmp_path / "export"
    export.mkdir()
    request = DevelopmentGenerationRequest(
        effective,
        DevelopmentScenario(3, "launch", 0, InvoiceStatus.PENDING, UsageAssumptions(1, 2, 3, 4)),
        tmp_path / "registry.sqlite",
        "synthetic-client",
        "export-retry",
        datetime.combine(datetime(2024, 3, 31).date(), time.max, tzinfo=UTC),
        export,
    )
    original_open = Path.open

    def fail_second_csv(path, *args, **kwargs):
        if path.name == "subscriptions.csv":
            raise OSError("simulated export failure")
        return original_open(path, *args, **kwargs)

    def fail_unexpected_access(*args, **kwargs):
        pytest.fail("No pipeline or network access is expected on export failure.")

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", fail_second_csv)
        guard.setattr("socket.socket", fail_unexpected_access)
        guard.setattr(
            "nowa_customer_intelligence.data.synthetic.development.execute_pipeline",
            fail_unexpected_access,
        )
        with pytest.raises(OSError, match="simulated export failure"):
            generate_development_population(request)
    assert list(export.iterdir()) == []
    registry = EpisodeIdentityRegistry(request.registry_path)
    history = registry.history(client=request.client, namespace=f"{SCENARIO_VERSION}:export-retry")
    assert len(history) == 3
    retry = generate_development_population(replace(request, validation_workflows=()))
    assert {row.episode.subscription_id for row in retry.episodes} == {
        row.subscription_id for row in history
    }
    assert set(tmp_path.iterdir()) == {export, request.registry_path}
