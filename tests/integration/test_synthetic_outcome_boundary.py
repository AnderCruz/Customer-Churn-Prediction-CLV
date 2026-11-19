"""Run contract projection and evidence checks without crossing their boundaries."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.customers import generate_customers
from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode
from nowa_customer_intelligence.data.synthetic.ground_truth import OutcomeRecord, OutcomeState
from nowa_customer_intelligence.data.synthetic.projection import (
    export_development_csvs,
    project_development_population,
)
from nowa_customer_intelligence.data.synthetic.run_context import create_run_context
from nowa_customer_intelligence.data.synthetic.semantic_validation import (
    ValidationStatus,
    validate_synthetic_evidence,
)
from nowa_customer_intelligence.pipeline import (
    PipelineExecutionRequest,
    PipelineOverallStatus,
    execute_pipeline,
)

_DOCUMENT = b"""
config_schema_version: 1
base:
  population: {customer_count: 1, episode_count_min: 1, episode_count_max: 1}
  history: {start_date: '2024-01-01', cutoff_date: '2024-04-01'}
  master_seed: 42
  workflow: BASIC
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios: {baseline: {scenario_version: 1}}
"""


def test_only_contract_facts_are_exported_when_internal_outcomes_are_supplied(
    tmp_path: Path,
) -> None:
    effective = resolve_configuration(load_configuration(_DOCUMENT), "baseline")
    context = create_run_context(effective)
    customers = generate_customers(context.effective_configuration)
    episode = SubscriptionEpisode(
        "aaaaaaaa-1234-4234-8234-123456789abc",
        customers[0].customer_id,
        customers[0].created_at,
        EpisodeStatus.ACTIVE,
    )
    t = datetime(2024, 4, 1, tzinfo=UTC)
    outcome = OutcomeRecord(
        episode.subscription_id,
        t,
        t + timedelta(hours=1),
        OutcomeState.PENDING_ASCERTAINMENT,
    )
    evidence = {
        row.rule: row.status
        for row in validate_synthetic_evidence(
            customers,
            (episode,),
            cutoff=t.date(),
            outcomes=(outcome,),
            episode_owners={episode.subscription_id: customers[0].customer_id},
        )
    }
    assert evidence["outcome_facts"] is ValidationStatus.PASSED
    assert evidence["target_and_eligibility"] is ValidationStatus.BLOCKED_BY_UNRESOLVED_POLICY
    assert evidence["feature_availability"] is ValidationStatus.NOT_EVALUATED
    tables = project_development_population(effective, customers, [episode])
    assert not list(tmp_path.iterdir())
    sources = export_development_csvs(tmp_path, tables)
    assert set(sources) == {"customers", "subscriptions"}
    for path in sources.values():
        data = path.read_text(encoding="utf-8")
        assert not any(
            word in data for word in ("pending_ascertainment", "outcome", "observation_at")
        )
    result = execute_pipeline(
        PipelineExecutionRequest(
            run_id="batch-05-fixture",
            client_scope="fixture",
            workflow=effective.workflow,
            dataset_sources=sources,
            execution_intent="check contract and internal evidence separation",
        )
    )
    assert result.summary.overall_status is PipelineOverallStatus.SUCCEEDED
    assert outcome.state is OutcomeState.PENDING_ASCERTAINMENT
