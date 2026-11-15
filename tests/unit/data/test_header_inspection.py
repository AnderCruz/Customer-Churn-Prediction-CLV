"""Unit tests for contract-based CSV header inspection."""

from pathlib import Path

import pytest

from nowa_customer_intelligence.data.ingestion import (
    DATASET_COLUMNS,
    CSVHeaderError,
    inspect_csv_header,
)

EXPECTED_COLUMNS = {
    "customers": {
        "required": ("customer_id", "created_at"),
        "optional": ("country", "industry", "company_size", "account_status"),
    },
    "subscriptions": {
        "required": (
            "subscription_id",
            "customer_id",
            "start_date",
            "subscription_status",
        ),
        "optional": (
            "plan_id",
            "end_date",
            "billing_frequency",
            "recurring_revenue",
            "currency",
            "auto_renew",
            "cancellation_date",
            "cancellation_reason",
        ),
    },
    "subscription_snapshots": {
        "required": ("subscription_id", "snapshot_date", "subscription_status"),
        "optional": (
            "recurring_revenue",
            "currency",
            "plan_id",
            "billing_frequency",
            "auto_renew",
        ),
    },
    "usage_monthly": {
        "required": ("subscription_id", "usage_month"),
        "optional": (
            "active_users",
            "total_users",
            "sessions_count",
            "events_count",
            "usage_volume",
            "usage_metric",
        ),
    },
    "invoices": {
        "required": (
            "invoice_id",
            "subscription_id",
            "invoice_date",
            "amount",
            "currency",
            "invoice_status",
        ),
        "optional": ("due_date", "paid_date"),
    },
}


@pytest.mark.parametrize("dataset", EXPECTED_COLUMNS)
def test_contract_column_definitions_match(dataset: str) -> None:
    """Centralized header definitions should match the contract fields."""
    assert DATASET_COLUMNS[dataset].required == EXPECTED_COLUMNS[dataset]["required"]
    assert DATASET_COLUMNS[dataset].optional == EXPECTED_COLUMNS[dataset]["optional"]


@pytest.mark.parametrize("dataset", EXPECTED_COLUMNS)
def test_valid_required_header_for_each_dataset(dataset: str, tmp_path: Path) -> None:
    """Each dataset should accept a header containing all required fields."""
    header = ",".join(EXPECTED_COLUMNS[dataset]["required"])
    csv_path = tmp_path / f"{dataset}.csv"
    csv_path.write_text(f"{header}\n", encoding="utf-8")

    assert inspect_csv_header(csv_path, dataset) == tuple(header.split(","))


def test_optional_columns_may_be_absent(tmp_path: Path) -> None:
    """Optional contract columns may be absent from a file header."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id,created_at\n", encoding="utf-8")

    assert inspect_csv_header(csv_path, "customers") == ("customer_id", "created_at")


def test_optional_columns_are_allowed_when_present(tmp_path: Path) -> None:
    """Known optional columns should be accepted when included."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(
        "customer_id,created_at,country,industry,company_size,account_status\n",
        encoding="utf-8",
    )

    assert len(inspect_csv_header(csv_path, "customers")) == 6


def test_missing_required_columns_are_reported(tmp_path: Path) -> None:
    """Missing required columns should identify the file and missing names."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError) as error:
        inspect_csv_header(csv_path, "customers")

    assert str(csv_path) in str(error.value)
    assert "missing required columns: created_at" in str(error.value)


def test_unexpected_columns_are_reported(tmp_path: Path) -> None:
    """Unexpected columns should be rejected and named in the error."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id,created_at,mystery\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match="unexpected columns: mystery"):
        inspect_csv_header(csv_path, "customers")


def test_duplicate_column_names_are_detected(tmp_path: Path) -> None:
    """Duplicate names in the raw header should be rejected."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id,created_at,customer_id\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match=r"duplicate column name\(s\): customer_id"):
        inspect_csv_header(csv_path, "customers")


@pytest.mark.parametrize("header", [",created_at", "customer_id,", "customer_id,,created_at"])
def test_empty_column_names_are_rejected(header: str, tmp_path: Path) -> None:
    """Empty header cells should be reported by position."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(f"{header}\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match="empty column name"):
        inspect_csv_header(csv_path, "customers")


@pytest.mark.parametrize("column", [" customer_id", "created_at "])
def test_whitespace_in_column_names_is_rejected(column: str, tmp_path: Path) -> None:
    """Column names with leading or trailing whitespace should not be normalized."""
    columns = [column, "created_at" if column.startswith(" ") else "customer_id"]
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text(f"{','.join(columns)}\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match="leading or trailing whitespace"):
        inspect_csv_header(csv_path, "customers")


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    """An empty file should report that the required header is missing."""
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match="CSV file is empty; header is missing"):
        inspect_csv_header(csv_path, "customers")


def test_empty_header_row_is_rejected(tmp_path: Path) -> None:
    """A blank first record should be rejected as an empty header row."""
    csv_path = tmp_path / "blank_header.csv"
    csv_path.write_text("\ncustomer_id,created_at\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match="CSV header row is empty"):
        inspect_csv_header(csv_path, "customers")


def test_utf8_bom_is_supported(tmp_path: Path) -> None:
    """A UTF-8 BOM should not become part of the first column name."""
    csv_path = tmp_path / "customers.csv"
    csv_path.write_text("customer_id,created_at\n", encoding="utf-8-sig")

    assert inspect_csv_header(csv_path, "customers") == ("customer_id", "created_at")


def test_alternate_delimiter_is_rejected(tmp_path: Path) -> None:
    """Headers not separated by commas should receive a delimiter error."""
    csv_path = tmp_path / "semicolon.csv"
    csv_path.write_text("customer_id;created_at\n", encoding="utf-8")

    with pytest.raises(CSVHeaderError, match="expected a comma-delimited header"):
        inspect_csv_header(csv_path, "customers")


def test_malformed_csv_header_is_reported(tmp_path: Path) -> None:
    """Malformed CSV quoting should produce a file-specific header error."""
    csv_path = tmp_path / "malformed.csv"
    csv_path.write_text('"customer_id,created_at\n', encoding="utf-8")

    with pytest.raises(CSVHeaderError, match="unable to read CSV header"):
        inspect_csv_header(csv_path, "customers")


def test_invalid_utf8_header_is_reported(tmp_path: Path) -> None:
    """Invalid UTF-8 bytes should produce a clear read error."""
    csv_path = tmp_path / "invalid_utf8.csv"
    csv_path.write_bytes(b"\xff,created_at\n")

    with pytest.raises(CSVHeaderError, match="unable to read CSV header"):
        inspect_csv_header(csv_path, "customers")


def test_nonexistent_file_is_reported(tmp_path: Path) -> None:
    """A missing path should be reported without attempting to read it."""
    csv_path = tmp_path / "missing.csv"

    with pytest.raises(CSVHeaderError, match="file does not exist") as error:
        inspect_csv_header(csv_path, "customers")

    assert str(csv_path) in str(error.value)


def test_unreadable_file_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An OS-level read failure should be reported with the affected path."""
    csv_path = tmp_path / "unreadable.csv"
    csv_path.write_text("customer_id,created_at\n", encoding="utf-8")
    original_open = Path.open

    def raise_permission_error(self: Path, *args: object, **kwargs: object):
        if self == csv_path:
            raise PermissionError("permission denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", raise_permission_error)

    with pytest.raises(CSVHeaderError, match="unable to read CSV header") as error:
        inspect_csv_header(csv_path, "customers")

    assert str(csv_path) in str(error.value)


def test_unsupported_dataset_is_reported(tmp_path: Path) -> None:
    """Unknown dataset keys should fail clearly."""
    csv_path = tmp_path / "customers.csv"

    with pytest.raises(CSVHeaderError, match="unsupported dataset"):
        inspect_csv_header(csv_path, "unknown")
