"""Exercise synthetic accounts, supplied episodes and explicit billing facts together."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from nowa_customer_intelligence.data.preprocessing.type_normalization import normalize_dataset_types
from nowa_customer_intelligence.data.schemas.invoices import INVOICE_SCHEMA
from nowa_customer_intelligence.data.schemas.subscriptions import SUBSCRIPTION_SCHEMA
from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    InvoiceFact,
    InvoiceStatus,
    calculate_catalogue_charge,
    validate_invoice_relationships,
)
from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.customers import generate_customers
from nowa_customer_intelligence.data.synthetic.episodes import (
    EpisodeEvent,
    EpisodeEventType,
    EpisodeStatus,
    SubscriptionEpisode,
    build_episode_population,
)
from nowa_customer_intelligence.data.synthetic.run_context import create_run_context

_DOCUMENT = b"""
config_schema_version: 1
base:
  population: {customer_count: 2, episode_count_min: 2, episode_count_max: 2}
  history: {start_date: '2024-01-01', cutoff_date: '2024-01-31'}
  master_seed: 42
  workflow: BASIC
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios: {baseline: {scenario_version: 1}}
"""
_IDS = ("aaaaaaaa-1234-4234-8234-123456789abc", "bbbbbbbb-1234-7234-8234-123456789abc")


def test_explicit_episodes_and_billing_using_existing_schemas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    effective = resolve_configuration(load_configuration(_DOCUMENT), "baseline")
    context = create_run_context(effective)
    customers = generate_customers(context.effective_configuration)
    before = tuple(asdict(customer) for customer in customers)
    episodes = tuple(
        SubscriptionEpisode(
            identifier,
            customer.customer_id,
            customer.created_at,
            EpisodeStatus.ACTIVE,
            establishment=EpisodeEvent(
                f"fixture-event-{index}",
                EpisodeEventType.ESTABLISHED,
                datetime(
                    customer.created_at.year,
                    customer.created_at.month,
                    customer.created_at.day,
                    tzinfo=UTC,
                ),
            ),
        )
        for index, (identifier, customer) in enumerate(zip(_IDS, customers, strict=True))
    )
    population = build_episode_population(customers, reversed(episodes))
    assert population == episodes
    assert set(row.customer_id for row in population) == {row.customer_id for row in customers}
    assert tuple(row.subscription_id for row in population) == _IDS
    assert tuple(asdict(customer) for customer in customers) == before

    subscription_rows = [
        {
            "subscription_id": row.subscription_id,
            "customer_id": row.customer_id,
            "start_date": row.start_date.isoformat(),
            "subscription_status": row.subscription_status.value,
        }
        for row in population
    ]
    checked = SUBSCRIPTION_SCHEMA.validate(
        normalize_dataset_types(pd.DataFrame(subscription_rows), "subscriptions")
    )
    assert len(checked) == 2 and "churn" not in checked.columns

    episode = population[0]
    charge = calculate_catalogue_charge("launch", BillingFrequency.ANNUAL)
    fixture_date = episode.start_date + timedelta(days=3)
    invoice = InvoiceFact(
        "fixture-invoice",
        episode.subscription_id,
        fixture_date,
        charge.invoice_amount,
        InvoiceStatus.PENDING,
    )
    assert validate_invoice_relationships(population, [invoice]) == (invoice,)
    invoice_row = dict(
        asdict(invoice),
        invoice_date=fixture_date.isoformat(),
        amount=str(invoice.amount),
        invoice_status=invoice.invoice_status.value,
    )
    checked_invoice = INVOICE_SCHEMA.validate(
        normalize_dataset_types(pd.DataFrame([invoice_row]), "invoices")
    )
    assert checked_invoice.subscription_id.tolist() == [episode.subscription_id]
    assert context.generated_inventory == ()
    assert list(tmp_path.iterdir()) == []
