"""Check projection boundaries, headers and temporary-export isolation."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord
from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode
from nowa_customer_intelligence.data.synthetic.projection import (
    ProjectedDataset,
    ProjectionError,
    export_development_csvs,
    project_development_population,
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
_DAY = date(2024, 1, 1)
_CUSTOMER = CustomerRecord("synthetic-test", _DAY, "GB")
_EPISODE = SubscriptionEpisode(
    "aaaaaaaa-1234-4234-8234-123456789abc", _CUSTOMER.customer_id, _DAY, EpisodeStatus.ACTIVE
)


def _configuration(document: bytes = _DOCUMENT):
    return resolve_configuration(load_configuration(document), "baseline")


def _project():
    return project_development_population(_configuration(), [_CUSTOMER], [_EPISODE])


def test_projects_exact_contract_order_and_keeps_missing_fields_blank() -> None:
    customer, episode = _project()
    assert customer.columns == (
        "customer_id",
        "created_at",
        "country",
        "industry",
        "company_size",
        "account_status",
    )
    assert customer.rows == (("synthetic-test", "2024-01-01", "GB", "", "", ""),)
    assert episode.columns[:6] == (
        "subscription_id",
        "customer_id",
        "plan_id",
        "start_date",
        "end_date",
        "subscription_status",
    )
    assert episode.rows[0][2:6] == ("", "2024-01-01", "", "active")
    assert "establishment" not in episode.columns


def test_rejects_wrong_type_empty_and_unowned_customers() -> None:
    effective = _configuration()
    with pytest.raises(ProjectionError, match="resolved"):
        project_development_population({}, [_CUSTOMER], [_EPISODE])
    with pytest.raises(ProjectionError, match="typed"):
        project_development_population(effective, [replace(_CUSTOMER, country=1)], [_EPISODE])
    with pytest.raises(ProjectionError, match="contain records"):
        project_development_population(effective, [_CUSTOMER], [])
    with pytest.raises(ProjectionError, match="Every projected customer"):
        project_development_population(
            effective, [_CUSTOMER, replace(_CUSTOMER, customer_id="other")], [_EPISODE]
        )


def test_requires_exact_inventory_and_nonempty_temporal_snapshots() -> None:
    raw = _DOCUMENT.replace(b"workflow: BASIC", b"workflow: TEMPORAL").replace(
        b"subscriptions.csv]", b"subscriptions.csv, subscription_snapshots.csv]"
    )
    effective = _configuration(raw)
    with pytest.raises(ProjectionError, match="declared inventory"):
        project_development_population(effective, [_CUSTOMER], [_EPISODE])
    with pytest.raises(ProjectionError, match="no records"):
        project_development_population(effective, [_CUSTOMER], [_EPISODE], snapshots=[])
    with pytest.raises(ProjectionError, match="after the extraction cutoff"):
        project_development_population(
            _configuration(), [_CUSTOMER], [replace(_EPISODE, start_date=date(2024, 5, 1))]
        )


def test_allows_explicitly_empty_optional_dataset() -> None:
    effective = _configuration(
        _DOCUMENT.replace(b"subscriptions.csv]", b"subscriptions.csv, invoices.csv]")
    )
    tables = project_development_population(effective, [_CUSTOMER], [_EPISODE], invoices=[])
    assert tables[-1].rows == ()
    assert tables[-1].columns == (
        "invoice_id",
        "subscription_id",
        "invoice_date",
        "due_date",
        "paid_date",
        "amount",
        "currency",
        "invoice_status",
    )


def test_export_refuses_missing_occupied_and_malformed_destinations(tmp_path: Path) -> None:
    tables = _project()
    with pytest.raises(ProjectionError, match="existing"):
        export_development_csvs(tmp_path / "missing", tables)
    with pytest.raises(ProjectionError, match="requires customers"):
        export_development_csvs(tmp_path, tables[:1])
    with pytest.raises(ProjectionError, match="Invalid"):
        export_development_csvs(tmp_path, (*tables, ProjectedDataset("../escape", (), ())))
    assert not list(tmp_path.iterdir())
    sentinel = tmp_path / "sentinel"
    sentinel.write_text("preserve")
    with pytest.raises(ProjectionError, match="empty"):
        export_development_csvs(tmp_path, tables)
    assert sentinel.read_text() == "preserve"
    assert set(tmp_path.iterdir()) == {sentinel}


def test_export_rolls_back_its_own_files_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.open

    def fail_second(path: Path, *args, **kwargs):
        if path.name == "subscriptions.csv":
            raise OSError("simulated export failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_second)
    with pytest.raises(OSError, match="simulated"):
        export_development_csvs(tmp_path, _project())
    assert not list(tmp_path.iterdir())
