"""Exercise source-native loading, offline acquisition and validation failures."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from shutil import copyfile
from urllib.error import URLError
from zipfile import ZipFile

import pytest
from openpyxl import Workbook

from nowa_customer_intelligence.data.public_sources import acquisition
from nowa_customer_intelligence.data.public_sources.acquisition import SourceError
from nowa_customer_intelligence.data.public_sources.misata import load_misata
from nowa_customer_intelligence.data.public_sources.retail import audit_retail, iter_retail_lines

_MISATA = {
    "accounts": "account_id,company_name,industry,country,employee_count,signup_date,plan\n"
    "A1,Example,Software,United Kingdom,2,2025-01-01 00:00:00,Starter\n",
    "subscriptions": "subscription_id,account_id,seats,status,mrr,started_on,ended_on\n"
    "S1,A1,2,active,24.00,2025-01-01 00:00:00,\n",
    "invoices": "invoice_id,account_id,invoice_date,amount,status\n"
    "I1,A1,2025-01-15 00:00:00,24.00,paid\n",
    "support_tickets": "ticket_id,account_id,opened_at,priority,category,satisfaction_score,"
    "resolution_hours,resolved_at\n"
    "T1,A1,2025-01-20 00:00:00,normal,Billing,,,\n",
    "users": "user_id,account_id,full_name,role,email\n"
    "U1,A1,Example User,admin,fixture@example.invalid\n",
}
_FOLDER = "saas-subscription-analytics"
_HEADER = (
    "Invoice",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "Price",
    "Customer ID",
    "Country",
)


@pytest.fixture
def misata_directory(tmp_path: Path) -> Path:
    folder = tmp_path / _FOLDER
    folder.mkdir()
    for name, content in _MISATA.items():
        (folder / f"{name}.csv").write_text(content, encoding="utf-8")
    return tmp_path


def test_misata_preserves_native_identity_and_types(misata_directory: Path) -> None:
    result = load_misata(misata_directory)
    assert result == load_misata(misata_directory)
    row = result.tables["subscriptions"][0]
    assert row["subscription_id"] == "S1" and row["account_id"] == "A1"
    assert row["mrr"] == Decimal("24.00")
    assert row["started_on"] == datetime(2025, 1, 1, tzinfo=UTC)
    assert row["ended_on"] is None
    assert result.quality["invoices"]["orphaned_accounts"] == 0
    assert result.quality["subscriptions"]["primary_key_duplicates"] == 0


@pytest.mark.parametrize(
    ("table", "before", "after", "error"),
    [
        ("accounts", "company_name,", "", "header"),
        ("accounts", "Example,Software", ",Software", "invalid company_name"),
        ("subscriptions", "S1,A1", "S1,Z1", "orphaned"),
        ("invoices", "I1,A1", "I1,Z1", "orphaned"),
        ("invoices", "2025-01-15", "2025-01-14", "billing"),
        ("subscriptions", "active,24.00", "unknown,24.00", "invalid status"),
        ("subscriptions", "active,24.00", "churned,24.00", "inconsistent dates"),
        ("invoices", "paid\n", "paid\nI1,A1,2025-01-15 00:00:00,24.00,paid\n", "duplicate"),
    ],
)
def test_misata_rejects_invalid_source(
    misata_directory: Path, table: str, before: str, after: str, error: str
) -> None:
    path = misata_directory / _FOLDER / f"{table}.csv"
    path.write_text(_MISATA[table].replace(before, after), encoding="utf-8")
    with pytest.raises(SourceError, match=error):
        load_misata(misata_directory)


def test_misata_requires_all_tables(misata_directory: Path) -> None:
    (misata_directory / _FOLDER / "users.csv").unlink()
    with pytest.raises(SourceError, match="users: missing"):
        load_misata(misata_directory)


def _workbook(path: Path, *, header=_HEADER, date=datetime(2009, 12, 1), price=2.55):
    workbook = Workbook()
    first = workbook.active
    first.title = "Year 2009-2010"
    second = workbook.create_sheet("Year 2010-2011")
    first.append(header)
    second.append(_HEADER)
    sale = [489434, 85048, "Item", 12, date, price, 13085, "United Kingdom"]
    first.append(sale)
    first.append(sale)
    second.append(["C536365", "85123A", None, -2, datetime(2010, 12, 1), 2.55, None, "France"])
    workbook.save(path)
    workbook.close()


def test_retail_streams_both_sheets_and_reports_preserved_anomalies(tmp_path: Path) -> None:
    path = tmp_path / "source.xlsx"
    _workbook(path)
    lines = list(iter_retail_lines(path))
    assert lines == list(iter_retail_lines(path))
    assert [row.transaction_value for row in lines] == [
        Decimal("30.60"),
        Decimal("30.60"),
        Decimal("-5.10"),
    ]
    assert lines[0].product_id == "85048" and lines[0].invoice_id == "489434"
    assert lines[2].cancellation and lines[2].customer_id is None
    audit = audit_retail(path)
    assert audit["sheets"] == {"Year 2009-2010": 2, "Year 2010-2011": 1}
    for key in (
        "duplicate_lines",
        "missing_customers",
        "missing_descriptions",
        "negative_quantities",
        "cancellation_lines",
    ):
        assert audit[key] == 1


def test_retail_acquisition_preserves_workbook_and_records_sheet_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "fixture.xlsx"
    _workbook(path)
    fixture = tmp_path / "fixture.zip"
    with ZipFile(fixture, "w") as archive:
        archive.write(path, "online_retail_II.xlsx")
    monkeypatch.setattr(acquisition, "_download", lambda _, target: copyfile(fixture, target))
    destination = acquisition.acquire("uci_online_retail_ii", tmp_path / "external")
    evidence = acquisition.verify_acquisition(destination)
    assert evidence["licence"] == "CC-BY-4.0"
    assert evidence["sheets"] == ["Year 2009-2010", "Year 2010-2011"]
    assert (destination / "online_retail_II.xlsx").read_bytes() == path.read_bytes()


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"header": ("Wrong", *_HEADER[1:])}, "header"),
        ({"date": "malformed"}, "invalid source field"),
        ({"price": "=1+1"}, "unsupported cell"),
    ],
)
def test_retail_rejects_malformed_workbook(tmp_path: Path, kwargs: dict, error: str) -> None:
    path = tmp_path / "source.xlsx"
    _workbook(path, **kwargs)
    with pytest.raises(SourceError, match=error):
        list(iter_retail_lines(path))


def test_acquisition_preserves_original_and_checksums(tmp_path: Path, monkeypatch) -> None:
    fixture = tmp_path / "fixture.zip"
    with ZipFile(fixture, "w") as archive:
        for table, contents in _MISATA.items():
            archive.writestr(f"{_FOLDER}/{table}.csv", contents)
    monkeypatch.setattr(acquisition, "_download", lambda _, path: copyfile(fixture, path))
    root = tmp_path / "external"
    destination = acquisition.acquire("misata_saas", root)
    evidence = acquisition.verify_acquisition(destination)
    assert evidence["source"] == "misata_saas" and evidence["licence"] == "CC0-1.0"
    assert (destination / evidence["archive"]["filename"]).read_bytes() == fixture.read_bytes()
    assert (destination / _FOLDER / "invoices.csv").read_text() == _MISATA["invoices"]
    assert "uci_online_retail_ii" not in {item.name for item in root.iterdir()}
    with pytest.raises(SourceError, match="already exists"):
        acquisition.acquire("misata_saas", root)
    (destination / _FOLDER / "invoices.csv").write_text("changed", encoding="utf-8")
    with pytest.raises(SourceError, match="integrity"):
        acquisition.verify_acquisition(destination)


def test_failed_download_leaves_no_partial_source(tmp_path: Path, monkeypatch) -> None:
    class Unavailable:
        def open(self, *_args, **_kwargs):
            raise URLError("fixture")

    monkeypatch.setattr(acquisition, "build_opener", lambda *_: Unavailable())
    with pytest.raises(SourceError, match="download failed"):
        acquisition.acquire("misata_saas", tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("name", "budget", "message"),
    [
        ("../outside", 10, "Unsafe"),
        ("file.csv", 1, "size budget"),
    ],
)
def test_archive_rejects_unsafe_members(
    tmp_path: Path, name: str, budget: int, message: str
) -> None:
    path = tmp_path / "unsafe.zip"
    with ZipFile(path, "w") as archive:
        archive.writestr(name, "abc")
    with ZipFile(path) as archive, pytest.raises(SourceError, match=message):
        acquisition.safe_members(archive, expanded_limit=budget)
