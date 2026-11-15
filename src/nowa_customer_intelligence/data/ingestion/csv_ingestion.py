"""Read contract-compliant CSV datasets while preserving their source values."""

import csv
from pathlib import Path

import pandas as pd

from nowa_customer_intelligence.data.ingestion.header_inspection import (
    inspect_csv_header,
)

DATASET_FILENAMES = {
    "customers": "customers.csv",
    "subscriptions": "subscriptions.csv",
    "subscription_snapshots": "subscription_snapshots.csv",
    "usage_monthly": "usage_monthly.csv",
    "invoices": "invoices.csv",
}
REQUIRED_DATASETS = ("customers", "subscriptions", "subscription_snapshots")
OPTIONAL_DATASETS = ("usage_monthly", "invoices")


class CSVIngestionError(ValueError):
    """Raised when a CSV dataset cannot be read safely."""


def _validate_record_width(file_path: Path, expected_width: int) -> None:
    """Reject malformed CSV records with a different number of fields than the header."""
    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.reader(csv_file, delimiter=",", strict=True)
            next(reader)
            for record_number, record in enumerate(reader, start=2):
                if len(record) != expected_width:
                    raise CSVIngestionError(
                        f"{file_path}: malformed CSV record {record_number}: "
                        f"expected {expected_width} fields, received {len(record)}"
                    )
    except CSVIngestionError:
        raise
    except (OSError, UnicodeError, csv.Error, StopIteration) as exc:
        raise CSVIngestionError(f"{file_path}: unable to validate CSV records: {exc}") from exc


def ingest_csv_dataset(file_path: str | Path, dataset: str) -> pd.DataFrame:
    """Inspect and read one contract dataset, preserving all values as strings.

    Empty CSV fields are represented as empty strings (``""``), not as missing-value
    markers. Dates, numbers, booleans, column names, and source values are not converted.

    Args:
        file_path: Path to the dataset CSV file.
        dataset: Contract dataset identifier, such as ``"customers"``.

    Returns:
        The parsed dataset as a pandas DataFrame with string-typed columns.

    Raises:
        CSVIngestionError: If a data record is malformed or the file cannot be read.

    Header inspection errors from ``inspect_csv_header`` propagate unchanged.
    """
    path = Path(file_path)
    header = inspect_csv_header(path, dataset)
    _validate_record_width(path, len(header))

    try:
        return pd.read_csv(
            path,
            sep=",",
            encoding="utf-8-sig",
            dtype="string",
            keep_default_na=False,
            on_bad_lines="error",
        )
    except (
        OSError,
        UnicodeError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
        ValueError,
    ) as exc:
        raise CSVIngestionError(f"{path}: unable to ingest CSV dataset {dataset!r}: {exc}") from exc


def ingest_client_datasets(data_directory: str | Path) -> dict[str, pd.DataFrame]:
    """Load required and present optional datasets from a client data directory.

    Returns a dictionary keyed by dataset identifier. The three required contract files
    must be present. ``usage_monthly.csv`` and ``invoices.csv`` are included only when
    present; an existing invalid optional file raises an error instead of being skipped.

    Args:
        data_directory: Directory containing the contract-named CSV files.

    Returns:
        Loaded datasets keyed by ``customers``, ``subscriptions``,
        ``subscription_snapshots``, ``usage_monthly``, and/or ``invoices``.

    Raises:
        CSVIngestionError: If the directory is invalid or a required file is missing.

    Header inspection errors from ``inspect_csv_header`` propagate unchanged.
    """
    directory = Path(data_directory)
    if not directory.is_dir():
        raise CSVIngestionError(
            f"{directory}: client data directory does not exist or is not a directory"
        )

    datasets: dict[str, pd.DataFrame] = {}
    for dataset in (*REQUIRED_DATASETS, *OPTIONAL_DATASETS):
        file_path = directory / DATASET_FILENAMES[dataset]
        if dataset in REQUIRED_DATASETS and not file_path.exists():
            raise CSVIngestionError(f"{file_path}: required dataset file is missing")
        if file_path.exists():
            datasets[dataset] = ingest_csv_dataset(file_path, dataset)

    return datasets
