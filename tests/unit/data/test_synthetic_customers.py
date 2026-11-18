"""Verify synthetic account generation and the customer schema boundary."""

from dataclasses import asdict
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from nowa_customer_intelligence.data.preprocessing.type_normalization import normalize_dataset_types
from nowa_customer_intelligence.data.schemas.customers import CUSTOMER_SCHEMA
from nowa_customer_intelligence.data.synthetic.configuration import (
    EffectiveConfiguration,
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.customers import (
    CustomerGenerationError,
    generate_customers,
)
from nowa_customer_intelligence.data.synthetic.random_streams import create_random_stream

_DOCUMENT = b"""
config_schema_version: 1
base:
  population: {customer_count: 1000, episode_count_min: 1100, episode_count_max: 1400}
  history: {start_date: '2023-01-01', cutoff_date: '2026-01-01'}
  master_seed: 42
  workflow: BASIC
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios: {baseline: {scenario_version: 1}}
"""


def _effective(count: int = 1000, seed: int = 42) -> EffectiveConfiguration:
    return resolve_configuration(
        load_configuration(_DOCUMENT),
        "baseline",
        {"population": {"customer_count": count}, "master_seed": seed},
    )


@pytest.mark.parametrize("count", [1, 12, 1000])
def test_population_counts_types_and_contract(count: int) -> None:
    records = generate_customers(_effective(count))
    assert len(records) == len({record.customer_id for record in records}) == count
    assert records[0].customer_id == "synthetic-customer-000001"
    assert records[-1].customer_id == f"synthetic-customer-{count:06d}"
    assert all(record.country == "GB" for record in records)
    assert all(
        type(record.created_at) is date
        and date(2023, 1, 1) <= record.created_at <= date(2026, 1, 1)
        for record in records
    )
    rows = [dict(asdict(record), created_at=record.created_at.isoformat()) for record in records]
    assert all(set(row) == {"customer_id", "created_at", "country"} for row in rows)
    frame = normalize_dataset_types(pd.DataFrame(rows), "customers")
    assert len(CUSTOMER_SCHEMA.validate(frame)) == count


def test_population_replays_without_consuming_other_streams() -> None:
    effective = _effective(30)
    before = effective.model_dump()
    expected = generate_customers(effective)
    create_random_stream(42, "unrelated", namespace="baseline").integers(0, 100, size=500)
    assert generate_customers(effective) == expected
    changed = generate_customers(_effective(30, seed=43))
    assert [record.created_at for record in changed] != [record.created_at for record in expected]
    assert [record.customer_id for record in changed] == [record.customer_id for record in expected]
    assert effective.model_dump() == before


def test_rejects_unresolved_or_unprojectable_inputs() -> None:
    with pytest.raises(CustomerGenerationError, match="resolved"):
        generate_customers(load_configuration(_DOCUMENT))
    effective = resolve_configuration(
        load_configuration(_DOCUMENT), "baseline", {"history": {"start_date": "1500-01-01"}}
    )
    with pytest.raises(CustomerGenerationError, match="history"):
        generate_customers(effective)


def test_generation_needs_no_files_or_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    effective = _effective(2)

    def unexpected(*args: object, **kwargs: object) -> None:
        pytest.fail("Customer generation attempted external access.")

    monkeypatch.chdir(tmp_path)
    with monkeypatch.context() as guard:
        guard.setattr("socket.socket", unexpected)
        guard.setattr("builtins.open", unexpected)
        guard.setattr("io.open", unexpected)
        assert len(generate_customers(effective)) == 2
    assert list(tmp_path.iterdir()) == []
