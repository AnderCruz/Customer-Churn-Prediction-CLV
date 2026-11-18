"""Exercise WP-01 through WP-03 using the public component interfaces."""

from pathlib import Path

from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.customers import generate_customers
from nowa_customer_intelligence.data.synthetic.run_context import create_run_context


def test_configuration_to_customer_population(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    document = load_configuration(b"""
config_schema_version: 1
base:
  population: {customer_count: 3, episode_count_min: 3, episode_count_max: 4}
  history: {start_date: '2025-01-01', cutoff_date: '2025-02-01'}
  master_seed: 51
  workflow: BASIC
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios:
  development:
    scenario_version: 1
    patch:
      population: {customer_count: 4}
""")
    effective = resolve_configuration(document, "development")
    first, second = create_run_context(effective), create_run_context(effective)
    records = generate_customers(first.effective_configuration)
    assert len(records) == 4
    assert records == generate_customers(second.effective_configuration)
    assert first.run_id != second.run_id
    assert first.generated_inventory == second.generated_inventory == ()
    assert list(tmp_path.iterdir()) == []
