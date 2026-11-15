"""Inspect CSV headers against the approved dataset contracts."""

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


class CSVHeaderError(ValueError):
    """Raised when a CSV file header is unreadable or violates its contract."""


@dataclass(frozen=True)
class DatasetColumns:
    """Required and optional columns for one contract dataset."""

    required: tuple[str, ...]
    optional: tuple[str, ...]


DATASET_COLUMNS: dict[str, DatasetColumns] = {
    "customers": DatasetColumns(
        required=("customer_id", "created_at"),
        optional=("country", "industry", "company_size", "account_status"),
    ),
    "subscriptions": DatasetColumns(
        required=(
            "subscription_id",
            "customer_id",
            "start_date",
            "subscription_status",
        ),
        optional=(
            "plan_id",
            "end_date",
            "billing_frequency",
            "recurring_revenue",
            "currency",
            "auto_renew",
            "cancellation_date",
            "cancellation_reason",
        ),
    ),
    "subscription_snapshots": DatasetColumns(
        required=("subscription_id", "snapshot_date", "subscription_status"),
        optional=(
            "recurring_revenue",
            "currency",
            "plan_id",
            "billing_frequency",
            "auto_renew",
        ),
    ),
    "usage_monthly": DatasetColumns(
        required=("subscription_id", "usage_month"),
        optional=(
            "active_users",
            "total_users",
            "sessions_count",
            "events_count",
            "usage_volume",
            "usage_metric",
        ),
    ),
    "invoices": DatasetColumns(
        required=(
            "invoice_id",
            "subscription_id",
            "invoice_date",
            "amount",
            "currency",
            "invoice_status",
        ),
        optional=("due_date", "paid_date"),
    ),
}


def inspect_csv_header(file_path: str | Path, dataset: str) -> tuple[str, ...]:
    """Validate and return a CSV header without loading its data rows.

    Args:
        file_path: Path to the CSV file.
        dataset: Contract dataset key, such as ``"customers"``.

    Raises:
        CSVHeaderError: If the file or its header violates the dataset contract.
    """
    path = Path(file_path)
    columns = DATASET_COLUMNS.get(dataset)
    if columns is None:
        raise CSVHeaderError(f"{path}: unsupported dataset {dataset!r}")

    if not path.exists():
        raise CSVHeaderError(f"{path}: file does not exist")
    if not path.is_file():
        raise CSVHeaderError(f"{path}: path is not a regular file")

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file, delimiter=",", strict=True)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise CSVHeaderError(f"{path}: CSV file is empty; header is missing") from exc
    except CSVHeaderError:
        raise
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CSVHeaderError(f"{path}: unable to read CSV header: {exc}") from exc

    if not header:
        raise CSVHeaderError(f"{path}: CSV header row is empty")

    empty_columns = [index + 1 for index, name in enumerate(header) if name == ""]
    if empty_columns:
        positions = ", ".join(str(position) for position in empty_columns)
        raise CSVHeaderError(f"{path}: empty column name at header position(s): {positions}")

    if (
        len(header) == 1
        and len(columns.required) > 1
        and any(delimiter in header[0] for delimiter in (";", "|", "\t"))
    ):
        raise CSVHeaderError(
            f"{path}: expected a comma-delimited header; parsed one column instead"
        )

    whitespace_columns = [name for name in header if name != name.strip()]
    if whitespace_columns:
        names = ", ".join(repr(name) for name in whitespace_columns)
        raise CSVHeaderError(f"{path}: leading or trailing whitespace in column name(s): {names}")

    duplicate_columns = sorted(name for name, count in Counter(header).items() if count > 1)
    if duplicate_columns:
        names = ", ".join(duplicate_columns)
        raise CSVHeaderError(f"{path}: duplicate column name(s): {names}")

    received = set(header)
    missing = sorted(set(columns.required) - received)
    unexpected = sorted(received - set(columns.required) - set(columns.optional))
    problems = []
    if missing:
        problems.append(f"missing required columns: {', '.join(missing)}")
    if unexpected:
        problems.append(f"unexpected columns: {', '.join(unexpected)}")
    if problems:
        raise CSVHeaderError(f"{path}: " + "; ".join(problems))

    return tuple(header)
