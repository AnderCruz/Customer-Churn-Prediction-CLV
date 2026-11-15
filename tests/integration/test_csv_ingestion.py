"""Integration tests for loading a client's contract datasets."""

from pathlib import Path

import pandas as pd
import pytest

from nowa_customer_intelligence.data.ingestion import (
    DATASET_COLUMNS,
    DATASET_FILENAMES,
    CSVHeaderError,
    CSVIngestionError,
    ingest_client_datasets,
)

REQUIRED_DATASETS = ("customers", "subscriptions", "subscription_snapshots")
OPTIONAL_DATASETS = ("usage_monthly", "invoices")


def write_dataset(directory: Path, dataset: str, *, include_row: bool = True) -> Path:
    """Write a small contract-shaped fixture for one dataset."""
    columns = DATASET_COLUMNS[dataset]
    header = (*columns.required, *columns.optional)
    rows = {
        "customers": ("customer-1", "2025-01-01", "", "", "", ""),
        "subscriptions": (
            "subscription-1",
            "customer-1",
            "",
            "2025-01-01",
            "",
            "active",
            "",
            "",
            "",
            "",
            "",
            "",
        ),
        "subscription_snapshots": (
            "subscription-1",
            "2025-02-01",
            "active",
            "",
            "",
            "",
            "",
            "",
        ),
        "usage_monthly": ("subscription-1", "2025-02-01", "", "", "", "", "", ""),
        "invoices": (
            "invoice-1",
            "subscription-1",
            "2025-02-01",
            "",
            "",
            "pending",
            "",
            "",
        ),
    }[dataset]
    file_path = directory / DATASET_FILENAMES[dataset]
    content = ",".join(header) + "\n"
    if include_row:
        content += ",".join(rows) + "\n"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def test_loads_all_required_datasets(tmp_path: Path) -> None:
    """The three required datasets should load when optional files are absent."""
    for dataset in REQUIRED_DATASETS:
        write_dataset(tmp_path, dataset)

    loaded = ingest_client_datasets(tmp_path)

    assert set(loaded) == set(REQUIRED_DATASETS)
    assert all(isinstance(frame, pd.DataFrame) for frame in loaded.values())


def test_loads_all_five_datasets(tmp_path: Path) -> None:
    """All known datasets should be loaded when every file is present."""
    all_datasets = (*REQUIRED_DATASETS, *OPTIONAL_DATASETS)
    for dataset in all_datasets:
        write_dataset(tmp_path, dataset)

    loaded = ingest_client_datasets(tmp_path)

    assert set(loaded) == set(all_datasets)


def test_optional_datasets_may_both_be_absent(tmp_path: Path) -> None:
    """Missing optional files should be omitted from the returned mapping."""
    for dataset in REQUIRED_DATASETS:
        write_dataset(tmp_path, dataset)

    loaded = ingest_client_datasets(tmp_path)

    assert not set(OPTIONAL_DATASETS).intersection(loaded)


@pytest.mark.parametrize("present_optional", OPTIONAL_DATASETS)
def test_one_optional_dataset_can_be_present_alone(present_optional: str, tmp_path: Path) -> None:
    """Each optional dataset should load independently of the other."""
    for dataset in REQUIRED_DATASETS:
        write_dataset(tmp_path, dataset)
    write_dataset(tmp_path, present_optional)

    loaded = ingest_client_datasets(tmp_path)

    assert present_optional in loaded
    absent_optional = set(OPTIONAL_DATASETS) - {present_optional}
    assert not absent_optional.intersection(loaded)


@pytest.mark.parametrize("missing_dataset", REQUIRED_DATASETS)
def test_missing_required_dataset_fails(missing_dataset: str, tmp_path: Path) -> None:
    """Each missing required file should identify its expected path."""
    for dataset in set(REQUIRED_DATASETS) - {missing_dataset}:
        write_dataset(tmp_path, dataset)

    with pytest.raises(CSVIngestionError, match=DATASET_FILENAMES[missing_dataset]):
        ingest_client_datasets(tmp_path)


def test_invalid_required_dataset_fails(tmp_path: Path) -> None:
    """An invalid header in a required dataset should stop client loading."""
    for dataset in REQUIRED_DATASETS:
        write_dataset(tmp_path, dataset)
    write_dataset(tmp_path, "subscriptions").write_text(
        "subscription_id,unknown\n", encoding="utf-8"
    )

    with pytest.raises(CSVHeaderError, match="unexpected columns"):
        ingest_client_datasets(tmp_path)


def test_invalid_optional_dataset_fails(tmp_path: Path) -> None:
    """An existing but invalid optional file must not be silently skipped."""
    for dataset in REQUIRED_DATASETS:
        write_dataset(tmp_path, dataset)
    write_dataset(tmp_path, "invoices").write_text("invoice_id,unexpected\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match="unexpected columns"):
        ingest_client_datasets(tmp_path)


def test_header_only_required_dataset_loads_as_empty_dataframe(tmp_path: Path) -> None:
    """A required file with a valid header and no records should load empty."""
    for dataset in REQUIRED_DATASETS:
        write_dataset(tmp_path, dataset, include_row=dataset != "customers")

    loaded = ingest_client_datasets(tmp_path)

    assert loaded["customers"].empty
    assert list(loaded["customers"].columns) == list(DATASET_COLUMNS["customers"].required) + list(
        DATASET_COLUMNS["customers"].optional
    )


def test_dataset_contents_are_preserved(tmp_path: Path) -> None:
    """Identifier formatting, dates, numeric-looking values, and empty fields persist."""
    write_dataset(tmp_path, "customers").write_text(
        "customer_id,created_at,country\n00123,2025-03-04,\n", encoding="utf-8"
    )
    for dataset in set(REQUIRED_DATASETS) - {"customers"}:
        write_dataset(tmp_path, dataset)

    loaded = ingest_client_datasets(tmp_path)

    assert loaded["customers"].iloc[0].to_dict() == {
        "customer_id": "00123",
        "created_at": "2025-03-04",
        "country": "",
    }
