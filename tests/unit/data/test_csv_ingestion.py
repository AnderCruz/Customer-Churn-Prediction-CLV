"""Unit tests for single-dataset CSV ingestion."""

from pathlib import Path

import pandas as pd
import pytest

from nowa_customer_intelligence.data.ingestion import (
    CSVHeaderError,
    CSVIngestionError,
    csv_ingestion,
    ingest_csv_dataset,
)


def test_valid_csv_is_read_as_string_values(tmp_path: Path) -> None:
    """Identifiers, dates, and numbers should remain source strings."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "customer_id,created_at,country\n00123,2025-02-03,UK\n",
        encoding="utf-8",
    )

    result = ingest_csv_dataset(csv_path, "customers")

    assert result.to_dict(orient="records") == [
        {"customer_id": "00123", "created_at": "2025-02-03", "country": "UK"}
    ]
    assert all(isinstance(dtype, pd.StringDtype) for dtype in result.dtypes)


def test_ingestion_calls_header_inspection_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The existing header inspector should run before pandas reads the file."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id,created_at\n001,2025-01-01\n", encoding="utf-8")
    original_inspect = csv_ingestion.inspect_csv_header
    inspected: list[tuple[Path, str]] = []

    def record_inspection(file_path: str | Path, dataset: str) -> tuple[str, ...]:
        inspected.append((Path(file_path), dataset))
        return original_inspect(file_path, dataset)

    monkeypatch.setattr(csv_ingestion, "inspect_csv_header", record_inspection)

    ingest_csv_dataset(csv_path, "customers")

    assert inspected == [(csv_path, "customers")]


def test_utf8_bom_is_supported(tmp_path: Path) -> None:
    """A UTF-8 BOM should not become part of the first column name or value."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id,created_at\n001,2025-01-01\n", encoding="utf-8-sig")

    result = ingest_csv_dataset(csv_path, "customers")

    assert list(result.columns) == ["customer_id", "created_at"]
    assert result.iloc[0].tolist() == ["001", "2025-01-01"]


def test_empty_fields_remain_empty_strings(tmp_path: Path) -> None:
    """Empty CSV fields should be preserved as empty strings, not NA values."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id,created_at,country\n001,2025-01-01,\n", encoding="utf-8")

    result = ingest_csv_dataset(csv_path, "customers")

    assert result.loc[0, "country"] == ""
    assert not result.isna().any().any()


def test_dates_and_numeric_looking_values_are_not_converted(tmp_path: Path) -> None:
    """Date and numeric fields should retain their original string representation."""
    csv_path = tmp_path / "usage_monthly.csv"
    csv_path.write_text(
        "subscription_id,usage_month,active_users\n0007,2025-03-01,004\n",
        encoding="utf-8",
    )

    result = ingest_csv_dataset(csv_path, "usage_monthly")

    assert result.loc[0, "subscription_id"] == "0007"
    assert result.loc[0, "usage_month"] == "2025-03-01"
    assert result.loc[0, "active_users"] == "004"
    assert all(isinstance(dtype, pd.StringDtype) for dtype in result.dtypes)


@pytest.mark.parametrize(
    "contents",
    [
        'customer_id,created_at\n"unterminated,2025-01-01\n',
        "customer_id,created_at\n001,2025-01-01,extra\n",
        "customer_id,created_at\n001\n",
    ],
)
def test_malformed_csv_records_are_rejected(contents: str, tmp_path: Path) -> None:
    """Malformed quoting and rows with the wrong field count should fail."""
    csv_path = tmp_path / "malformed.csv"
    csv_path.write_text(contents, encoding="utf-8")

    with pytest.raises(CSVIngestionError, match=str(csv_path)):
        ingest_csv_dataset(csv_path, "customers")


def test_missing_file_is_reported(tmp_path: Path) -> None:
    """A missing dataset file should produce a path-specific header error."""
    csv_path = tmp_path / "missing.csv"

    with pytest.raises(CSVHeaderError, match="file does not exist"):
        ingest_csv_dataset(csv_path, "customers")


@pytest.mark.parametrize(
    ("header", "message"),
    [
        ("customer_id", "missing required columns"),
        ("customer_id,created_at,unknown", "unexpected columns"),
        ("customer_id,created_at,customer_id", "duplicate column"),
    ],
)
def test_invalid_headers_are_rejected(header: str, message: str, tmp_path: Path) -> None:
    """Invalid headers should be rejected by the integrated header inspector."""
    csv_path = tmp_path / "invalid_header.csv"
    csv_path.write_text(f"{header}\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match=message):
        ingest_csv_dataset(csv_path, "customers")


def test_invalid_encoding_in_data_is_reported(tmp_path: Path) -> None:
    """Invalid UTF-8 should produce a path-specific read or ingestion error."""
    csv_path = tmp_path / "invalid_encoding.csv"
    csv_path.write_bytes(b"customer_id,created_at\n001,\xff\n")

    with pytest.raises((CSVHeaderError, CSVIngestionError)) as error:
        ingest_csv_dataset(csv_path, "customers")

    assert str(csv_path) in str(error.value)
