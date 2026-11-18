"""Project verified synthetic records for local development CSV validation."""

import csv
from collections.abc import Iterable
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import pandas as pd

from nowa_customer_intelligence.data.ingestion import DATASET_COLUMNS, DATASET_FILENAMES
from nowa_customer_intelligence.data.preprocessing.type_normalization import normalize_dataset_types
from nowa_customer_intelligence.data.synthetic.billing import (
    InvoiceFact,
    validate_invoice_relationships,
)
from nowa_customer_intelligence.data.synthetic.configuration import (
    EffectiveConfiguration,
    required_filenames,
)
from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord
from nowa_customer_intelligence.data.synthetic.episodes import (
    SubscriptionEpisode,
    build_episode_population,
)
from nowa_customer_intelligence.data.synthetic.observations import (
    SnapshotRecord,
    UsageRecord,
    validate_snapshots,
    validate_usage,
)


class ProjectionError(ValueError):
    """The inputs cannot be projected by the development-only boundary."""


# Table order follows contract §4. The ingestion registry groups required fields separately.
_COLUMNS = {key: columns.required + columns.optional for key, columns in DATASET_COLUMNS.items()}
_COLUMNS["subscriptions"] = (
    "subscription_id",
    "customer_id",
    "plan_id",
    "start_date",
    "end_date",
    "subscription_status",
    "billing_frequency",
    "recurring_revenue",
    "currency",
    "auto_renew",
    "cancellation_date",
    "cancellation_reason",
)
_COLUMNS["invoices"] = (
    "invoice_id",
    "subscription_id",
    "invoice_date",
    "due_date",
    "paid_date",
    "amount",
    "currency",
    "invoice_status",
)
_INTERNAL_FIELDS = {
    "subscriptions": ("establishment",),
    "usage_monthly": ("period_start", "period_end", "available_at"),
    "subscription_snapshots": ("observed_at", "occurred_at", "effective_at", "available_at"),
}


@dataclass(frozen=True, slots=True)
class ProjectedDataset:
    """Immutable CSV-compatible rows with a fixed contract header."""

    dataset: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def _csv_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, StrEnum):
        return value.value
    if type(value) is bool:
        return "true" if value else "false"
    if type(value) is date:
        return value.isoformat()
    if type(value) in (str, int, Decimal):
        return str(value)
    raise ProjectionError("Unsupported field type in a development projection.")


def _project_table(dataset: str, records: Iterable[object]) -> ProjectedDataset:
    columns = _COLUMNS[dataset]
    allowed = set(columns) | set(_INTERNAL_FIELDS.get(dataset, ()))
    rows = []
    for record in records:
        if any(field.name not in allowed for field in fields(record)):
            raise ProjectionError("Unsupported field in a development projection.")
        row = tuple(_csv_value(getattr(record, column, None)) for column in columns)
        if any(
            not row[columns.index(column)].strip() for column in DATASET_COLUMNS[dataset].required
        ):
            raise ProjectionError("A required contract value is missing.")
        rows.append(row)
    # Use the existing pipeline's type boundary to reject unrepresentable dates or decimals.
    normalize_dataset_types(pd.DataFrame(rows, columns=columns), dataset)
    return ProjectedDataset(dataset, columns, tuple(rows))


def project_development_population(
    effective: EffectiveConfiguration,
    customers: Iterable[CustomerRecord],
    episodes: Iterable[SubscriptionEpisode],
    *,
    snapshots: Iterable[SnapshotRecord] | None = None,
    usage: Iterable[UsageRecord] | None = None,
    invoices: Iterable[InvoiceFact] | None = None,
) -> tuple[ProjectedDataset, ...]:
    """Validate supplied relationships and project the declared workflow inventory."""
    if type(effective) is not EffectiveConfiguration:
        raise ProjectionError("Expected a resolved effective configuration.")
    customers = tuple(customers)
    if any(
        type(customer) is not CustomerRecord
        or type(customer.customer_id) is not str
        or not customer.customer_id
        or customer.customer_id.strip() != customer.customer_id
        or type(customer.created_at) is not date
        or type(customer.country) is not str
        or not customer.country.strip()
        for customer in customers
    ):
        raise ProjectionError("Expected typed development customer records.")
    episodes = build_episode_population(customers, episodes)
    if not customers or not episodes:
        raise ProjectionError("Customers and subscriptions must contain records.")
    if {customer.customer_id for customer in customers} != {row.customer_id for row in episodes}:
        raise ProjectionError("Every projected customer must have a supplied subscription.")

    supplied = {
        "customers": customers,
        "subscriptions": episodes,
        "subscription_snapshots": snapshots,
        "usage_monthly": usage,
        "invoices": invoices,
    }
    inventory = {DATASET_FILENAMES[key] for key, rows in supplied.items() if rows is not None}
    if inventory != set(effective.requested_outputs):
        raise ProjectionError("Supplied datasets must match the declared inventory.")
    cutoff = date.fromisoformat(effective.history.cutoff_date)
    if any(episode.start_date > cutoff for episode in episodes):
        raise ProjectionError("A subscription starts after the extraction cutoff.")
    tables = {
        "customers": tuple(sorted(customers, key=lambda customer: customer.customer_id)),
        "subscriptions": episodes,
    }
    if snapshots is not None:
        tables["subscription_snapshots"] = validate_snapshots(snapshots, episodes, cutoff=cutoff)
    if usage is not None:
        tables["usage_monthly"] = validate_usage(usage, episodes, cutoff=cutoff)
    if invoices is not None:
        tables["invoices"] = validate_invoice_relationships(episodes, invoices)
    for dataset, rows in tables.items():
        if DATASET_FILENAMES[dataset] in required_filenames(effective.workflow) and not rows:
            raise ProjectionError("A required workflow dataset has no records.")
    return tuple(_project_table(dataset, rows) for dataset, rows in tables.items())


def export_development_csvs(
    temporary_directory: Path, tables: Iterable[ProjectedDataset]
) -> dict[str, Path]:
    """Write only to an existing empty caller-owned temporary directory."""
    if not temporary_directory.is_dir() or temporary_directory.is_symlink():
        raise ProjectionError("Expected an existing temporary directory.")
    if any(temporary_directory.iterdir()):
        raise ProjectionError("The temporary export directory must be empty.")
    tables = tuple(tables)
    names: set[str] = set()
    for table in tables:
        if (
            type(table) is not ProjectedDataset
            or table.dataset not in _COLUMNS
            or table.dataset in names
            or table.columns != _COLUMNS[table.dataset]
            or any(
                len(row) != len(table.columns) or any(type(value) is not str for value in row)
                for row in table.rows
            )
        ):
            raise ProjectionError("Invalid development projection table.")
        names.add(table.dataset)
    if not {"customers", "subscriptions"} <= names:
        raise ProjectionError("The export requires customers and subscriptions.")

    written: dict[str, Path] = {}
    try:
        for table in tables:
            path = temporary_directory / DATASET_FILENAMES[table.dataset]
            with path.open("x", encoding="utf-8", newline="") as handle:
                written[table.dataset] = path
                writer = csv.writer(handle)
                writer.writerow(table.columns)
                writer.writerows(table.rows)
    except BaseException:
        for path in written.values():
            path.unlink(missing_ok=True)
        raise
    return written
