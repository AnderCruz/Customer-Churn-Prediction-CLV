"""Check configuration-only declarations against the public CSV pipeline."""

from pathlib import Path
from uuid import UUID

import pytest

from nowa_customer_intelligence.data.ingestion import DATASET_FILENAMES
from nowa_customer_intelligence.data.synthetic.configuration import (
    ConfigurationError,
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.run_context import create_run_context
from nowa_customer_intelligence.pipeline import (
    PipelineExecutionRequest,
    PipelineOverallStatus,
    PipelineWorkflow,
    discover_datasets,
    execute_pipeline,
)

# Prepared consumer fixtures are written by the tests, independently of WP-01.
_FIXTURES = {
    "customers": "customer_id,created_at\nC1,2025-01-01\n",
    "subscriptions": (
        "subscription_id,customer_id,start_date,subscription_status\nS1,C1,2025-01-01,active\n"
    ),
    "subscription_snapshots": (
        "subscription_id,snapshot_date,subscription_status\nS1,2025-02-01,active\n"
    ),
}
_CORE = ("customers", "subscriptions")
_WITH_SNAPSHOTS = (*_CORE, "subscription_snapshots")


def _document(workflow: PipelineWorkflow, datasets: tuple[str, ...]) -> bytes:
    filenames = ", ".join(DATASET_FILENAMES[name] for name in datasets)
    return f"""
config_schema_version: 1
base:
  population: {{customer_count: 1, episode_count_min: 1, episode_count_max: 1}}
  history: {{start_date: '2024-01-01', cutoff_date: '2026-01-01'}}
  master_seed: 0
  workflow: {workflow.value}
  execution_scope: configuration_only
  requested_outputs: [{filenames}]
  policy_refs: {{contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}}
scenarios: {{baseline: {{scenario_version: 1}}}}
""".encode()


@pytest.mark.parametrize(
    ("workflow", "datasets"),
    [
        (PipelineWorkflow.BASIC, _CORE),
        (PipelineWorkflow.BASIC, _WITH_SNAPSHOTS),
        (PipelineWorkflow.TEMPORAL, _WITH_SNAPSHOTS),
    ],
)
def test_declared_inventory_matches_pipeline_discovery_without_generating_data(
    workflow: PipelineWorkflow, datasets: tuple[str, ...], tmp_path: Path
) -> None:
    fixture_paths = {name: tmp_path / DATASET_FILENAMES[name] for name in datasets}
    for name, path in fixture_paths.items():
        path.write_text(_FIXTURES[name], encoding="utf-8")
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}

    effective = resolve_configuration(load_configuration(_document(workflow, datasets)), "baseline")
    context = create_run_context(
        effective, run_id_factory=lambda: UUID("12345678-1234-4234-8234-123456789abc")
    )
    assert context.planned_inventory == tuple(path.name for path in fixture_paths.values())
    assert context.generated_inventory == ()
    assert all(
        stage.stage_id.value in {"configuration_validation", "context_preparation"}
        for stage in context.stage_outcomes
    )
    assert {gate.gate_id: gate.applicability for gate in context.gates}[
        "publication_authorisation"
    ] == "outside_scope"

    request = PipelineExecutionRequest(
        run_id="fixture-validation-1",
        client_scope="fixture-client",
        workflow=context.effective_configuration.workflow,
        dataset_sources=fixture_paths,
        execution_intent="verify existing fixture compatibility",
    )
    discovery = discover_datasets(request)
    assert context.required_inputs == tuple(
        DATASET_FILENAMES[row.dataset]
        for row in discovery.stage_result.dataset_results
        if row.requirement.value == "REQUIRED"
    )
    result = execute_pipeline(request)
    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert result.summary.run_id == request.run_id != context.run_id
    assert result.summary.dataset_presence["subscription_snapshots"] == (
        "subscription_snapshots" in datasets
    )
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before


def test_invalid_temporal_inventory_stops_before_context_or_file_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    structural = load_configuration(_document(PipelineWorkflow.TEMPORAL, _CORE))

    def unexpected_pipeline(*args: object, **kwargs: object) -> None:
        pytest.fail("An invalid configuration reached the CSV pipeline.")

    monkeypatch.setattr(
        "nowa_customer_intelligence.pipeline.execution.execute_pipeline", unexpected_pipeline
    )
    monkeypatch.setattr("nowa_customer_intelligence.pipeline.execute_pipeline", unexpected_pipeline)

    def unexpected_run_id() -> UUID:
        pytest.fail("An invalid configuration reached run ID creation.")

    with pytest.raises(ConfigurationError, match="CONFIG_EFFECTIVE_INVALID"):
        create_run_context(
            resolve_configuration(structural, "baseline"), run_id_factory=unexpected_run_id
        )
    assert list(tmp_path.iterdir()) == []
