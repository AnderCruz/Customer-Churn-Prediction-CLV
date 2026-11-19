"""Typed, source-native access to Misata Studio's fictional SaaS tables."""

import csv
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .acquisition import SourceError

_FOLDER = "saas-subscription-analytics"
_COLUMNS = {
    "accounts": "account_id company_name industry country employee_count signup_date plan",
    "subscriptions": "subscription_id account_id seats status mrr started_on ended_on",
    "invoices": "invoice_id account_id invoice_date amount status",
    "support_tickets": (
        "ticket_id account_id opened_at priority category satisfaction_score "
        "resolution_hours resolved_at"
    ),
    "users": "user_id account_id full_name role email",
}
REQUIRED_FILES = {f"{_FOLDER}/{table}.csv" for table in _COLUMNS}
_OPTIONAL = {"ended_on", "satisfaction_score", "resolution_hours", "resolved_at"}
_DATES = {"signup_date", "started_on", "ended_on", "invoice_date", "opened_at", "resolved_at"}
_INTEGERS = {"employee_count", "seats", "satisfaction_score"}
_DECIMALS = {"mrr", "amount", "resolution_hours"}
_PRICES = {"Starter": 12, "Growth": 24, "Business": 44, "Enterprise": 79}
_CATEGORIES = {
    ("accounts", "plan"): _PRICES.keys(),
    ("accounts", "industry"): {
        "Education",
        "Financial Services",
        "Healthcare",
        "Logistics",
        "Manufacturing",
        "Retail",
        "Software",
    },
    ("accounts", "country"): {
        "Australia",
        "Brazil",
        "Canada",
        "France",
        "Germany",
        "Ireland",
        "Japan",
        "Netherlands",
        "United Kingdom",
        "United States",
    },
    ("subscriptions", "status"): {"active", "churned", "past_due", "trialing"},
    ("invoices", "status"): {"open", "paid", "uncollectible", "void"},
    ("support_tickets", "priority"): {"high", "low", "normal", "urgent"},
    ("support_tickets", "category"): {
        "Billing",
        "Bug Report",
        "Feature Request",
        "Integrations",
        "Onboarding",
        "Performance",
    },
    ("users", "role"): {"admin", "member", "viewer"},
}


@dataclass(frozen=True)
class MisataData:
    """Independent tables with original identifiers, exact decimals and UTC timestamps."""

    tables: dict[str, list[dict]]
    quality: dict


def _value(column: str, value: str):
    if not value.strip():
        if column in _OPTIONAL:
            return None
        raise ValueError
    if column in _DATES:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    if column in _INTEGERS:
        number = int(value)
        if number < 1 or (column == "satisfaction_score" and number > 5):
            raise ValueError
        return number
    if column in _DECIMALS:
        number = Decimal(value)
        if not number.is_finite() or number < 0 or number.as_tuple().exponent < -2:
            raise ValueError
        return number
    return value


def _load_table(path: Path, table: str, columns: list[str]) -> list[dict]:
    rows = []
    keys = set()
    try:
        if path.stat().st_size > 4_194_304:
            raise SourceError(f"{table}: file exceeds size budget.")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            if next(reader, None) != columns:
                raise SourceError(f"{table}: unexpected source header.")
            for index, values in enumerate(reader, 2):
                if len(values) != len(columns):
                    raise SourceError(f"{table}: wrong field count at row {index}.")
                row = {}
                for column, raw in zip(columns, values, strict=True):
                    try:
                        value = _value(column, raw)
                        allowed = _CATEGORIES.get((table, column))
                        if allowed is not None and value not in allowed:
                            raise ValueError
                    except (ValueError, InvalidOperation):
                        raise SourceError(f"{table}: invalid {column} at row {index}.") from None
                    row[column] = value
                key = row[columns[0]]
                if key in keys:
                    raise SourceError(f"{table}: duplicate primary key at row {index}.")
                keys.add(key)
                rows.append(row)
    except (OSError, UnicodeError, csv.Error):
        raise SourceError(f"{table}: missing or malformed source CSV.") from None
    if not rows:
        raise SourceError(f"{table}: no source records.")
    return rows


def load_misata(directory: Path) -> MisataData:
    """Load the verified archive layout and reject structural or relationship failures."""
    tables = {
        name: _load_table(directory / _FOLDER / f"{name}.csv", name, fields.split())
        for name, fields in _COLUMNS.items()
    }
    accounts = {row["account_id"]: row for row in tables["accounts"]}
    subscriptions = {row["account_id"]: row for row in tables["subscriptions"]}
    for table in ("subscriptions", "invoices", "support_tickets", "users"):
        if any(row["account_id"] not in accounts for row in tables[table]):
            raise SourceError(f"{table}: orphaned account reference.")
    if subscriptions.keys() != accounts.keys() or len(subscriptions) != len(
        tables["subscriptions"]
    ):
        raise SourceError("subscriptions: expected exactly one source subscription per account.")
    for index, row in enumerate(tables["subscriptions"], 2):
        account = accounts[row["account_id"]]
        end = row["ended_on"]
        if (
            row["started_on"] < account["signup_date"]
            or (row["status"] == "churned") != (end is not None)
            or (end is not None and end < row["started_on"])
            or row["mrr"] != row["seats"] * _PRICES[account["plan"]]
        ):
            raise SourceError(f"subscriptions: inconsistent dates, status or MRR at row {index}.")
    monthly = set()
    for table, date_column in (("invoices", "invoice_date"), ("support_tickets", "opened_at")):
        for index, row in enumerate(tables[table], 2):
            account_id = row["account_id"]
            subscription = subscriptions[account_id]
            date = row[date_column]
            end = subscription["ended_on"]
            if date < subscription["started_on"] or (end is not None and date > end):
                raise SourceError(f"{table}: date outside source subscription at row {index}.")
            if table == "invoices":
                month = (account_id, date.year, date.month)
                price = _PRICES[accounts[account_id]["plan"]]
                if (
                    date < subscription["started_on"] + timedelta(days=14)
                    or month in monthly
                    or row["amount"] <= 0
                    or row["amount"] % price
                ):
                    raise SourceError(f"invoices: inconsistent billing at row {index}.")
                monthly.add(month)
            else:
                resolved = row["resolved_at"]
                if (
                    (resolved is None) != (row["resolution_hours"] is None)
                    or (resolved is None and row["satisfaction_score"] is not None)
                    or (resolved is not None and resolved < date)
                ):
                    raise SourceError(f"support_tickets: inconsistent resolution at row {index}.")
    seats = Counter(row["account_id"] for row in tables["users"])
    if any(
        not seats[key] <= row["seats"] <= accounts[key]["employee_count"]
        for key, row in subscriptions.items()
    ):
        raise SourceError("subscriptions: inconsistent seat capacity.")
    quality = {}
    for table, rows in tables.items():
        ranges = {}
        for column in rows[0].keys() & _DATES:
            dates = [row[column] for row in rows if row[column] is not None]
            ranges[column] = (min(dates), max(dates)) if dates else None
        quality[table] = {
            "rows": len(rows),
            "primary_key_duplicates": 0,
            "orphaned_accounts": 0 if table != "accounts" else None,
            "missing": {column: sum(row[column] is None for row in rows) for column in rows[0]},
            "date_ranges": ranges,
        }
    return MisataData(tables, quality)
