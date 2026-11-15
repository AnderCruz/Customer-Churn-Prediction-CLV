"""Unit tests for the invoice data schema."""

import pandas as pd
import pandera.pandas as pa
import pytest

from nowa_customer_intelligence.data.schemas import INVOICE_SCHEMA


@pytest.fixture
def valid_invoices() -> pd.DataFrame:
    """Return valid invoice records, including repeated subscription IDs."""
    return pd.DataFrame(
        {
            "invoice_id": ["I001", "I002"],
            "subscription_id": ["S001", "S001"],
            "invoice_date": pd.to_datetime(["2025-01-01", "2025-02-01"]),
            "due_date": pd.to_datetime(["2025-01-15", "2025-02-15"]),
            "paid_date": pd.to_datetime(["2025-01-10", None]),
            "amount": [99.99, 100.0],
            "currency": ["USD", "EUR"],
            "invoice_status": ["paid", "pending"],
        }
    )


def test_valid_invoice_data_passes(valid_invoices: pd.DataFrame) -> None:
    """Valid invoice data should pass schema validation."""
    result = INVOICE_SCHEMA.validate(valid_invoices)

    assert len(result) == 2
    assert result["invoice_id"].is_unique
    assert result["subscription_id"].tolist() == ["S001", "S001"]


def test_missing_optional_columns_are_added() -> None:
    """Missing due and paid dates should be added as null columns."""
    data = pd.DataFrame(
        {
            "invoice_id": ["I001"],
            "subscription_id": ["S001"],
            "invoice_date": pd.to_datetime(["2025-01-01"]),
            "amount": [99.99],
            "currency": ["USD"],
            "invoice_status": ["pending"],
        }
    )

    result = INVOICE_SCHEMA.validate(data)

    assert "due_date" in result.columns
    assert "paid_date" in result.columns
    assert result[["due_date", "paid_date"]].isna().all().all()


@pytest.mark.parametrize(
    "required_column",
    [
        "invoice_id",
        "subscription_id",
        "invoice_date",
        "amount",
        "currency",
        "invoice_status",
    ],
)
def test_missing_required_column_fails(required_column: str) -> None:
    """Missing required columns are added as null and then rejected."""
    data = pd.DataFrame(
        {
            "invoice_id": ["I001"],
            "subscription_id": ["S001"],
            "invoice_date": pd.to_datetime(["2025-01-01"]),
            "amount": [99.99],
            "currency": ["USD"],
            "invoice_status": ["pending"],
        }
    ).drop(columns=required_column)

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(data)


@pytest.mark.parametrize(
    "field",
    ["invoice_id", "subscription_id", "invoice_date", "amount", "currency", "invoice_status"],
)
def test_null_required_field_fails(field: str) -> None:
    """Required invoice fields should reject null values."""
    values: dict[str, list[object]] = {
        "invoice_id": ["I001"],
        "subscription_id": ["S001"],
        "invoice_date": [pd.Timestamp("2025-01-01")],
        "amount": [99.99],
        "currency": ["USD"],
        "invoice_status": ["pending"],
    }
    values[field] = [None]
    data = pd.DataFrame(values)

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(data)


@pytest.mark.parametrize(
    ("field", "identifier"),
    [
        ("invoice_id", ""),
        ("invoice_id", "   "),
        ("invoice_id", " I001"),
        ("invoice_id", "I001 "),
        ("subscription_id", ""),
        ("subscription_id", "   "),
        ("subscription_id", " S001"),
        ("subscription_id", "S001 "),
    ],
    ids=[
        "invoice-empty",
        "invoice-whitespace-only",
        "invoice-leading-space",
        "invoice-trailing-space",
        "subscription-empty",
        "subscription-whitespace-only",
        "subscription-leading-space",
        "subscription-trailing-space",
    ],
)
def test_invalid_identifier_fails(field: str, identifier: str) -> None:
    """Empty or edge-whitespace identifiers should fail validation."""
    data = pd.DataFrame(
        {
            "invoice_id": ["I001"],
            "subscription_id": ["S001"],
            "invoice_date": pd.to_datetime(["2025-01-01"]),
            "amount": [99.99],
            "currency": ["USD"],
            "invoice_status": ["pending"],
        }
    )
    data[field] = [identifier]

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(data)


def test_duplicate_invoice_id_fails(valid_invoices: pd.DataFrame) -> None:
    """Duplicate invoice identifiers should fail validation."""
    valid_invoices.loc[1, "invoice_id"] = "I001"

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(valid_invoices)


def test_nullable_dates_accept_null_values(valid_invoices: pd.DataFrame) -> None:
    """Optional due and paid dates should accept null values."""
    valid_invoices.loc[:, "due_date"] = pd.NaT
    valid_invoices.loc[:, "paid_date"] = pd.NaT

    result = INVOICE_SCHEMA.validate(valid_invoices)

    assert result[["due_date", "paid_date"]].isna().all().all()


@pytest.mark.parametrize("field", ["due_date", "paid_date"])
def test_date_must_not_precede_invoice_date(field: str, valid_invoices: pd.DataFrame) -> None:
    """Due and paid dates should not precede the invoice date."""
    valid_invoices.loc[0, field] = pd.Timestamp("2024-12-31")

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(valid_invoices)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("invoice_id", 1001),
        ("subscription_id", 1001),
        ("invoice_date", "2025-01-01"),
        ("due_date", "2025-01-15"),
        ("amount", "99.99"),
        ("currency", 840),
        ("invoice_status", 1),
    ],
)
def test_invalid_field_type_fails(field: str, value: object) -> None:
    """Values with types outside the schema should fail without coercion."""
    data = pd.DataFrame(
        {
            "invoice_id": ["I001"],
            "subscription_id": ["S001"],
            "invoice_date": pd.to_datetime(["2025-01-01"]),
            "amount": [99.99],
            "currency": ["USD"],
            "invoice_status": ["pending"],
        }
    )
    data[field] = [value]

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(data)


def test_negative_amount_fails() -> None:
    """Negative invoice amounts should fail validation."""
    data = pd.DataFrame(
        {
            "invoice_id": ["I001"],
            "subscription_id": ["S001"],
            "invoice_date": pd.to_datetime(["2025-01-01"]),
            "amount": [-0.01],
            "currency": ["USD"],
            "invoice_status": ["pending"],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(data)


@pytest.mark.parametrize("currency", ["us", "USd", "USDD", "1US"])
def test_invalid_currency_format_fails(currency: str) -> None:
    """Currency values must contain three uppercase letters."""
    data = pd.DataFrame(
        {
            "invoice_id": ["I001"],
            "subscription_id": ["S001"],
            "invoice_date": pd.to_datetime(["2025-01-01"]),
            "amount": [99.99],
            "currency": [currency],
            "invoice_status": ["pending"],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(data)


@pytest.mark.parametrize("status", ["processing", "PAID", "", None])
def test_invalid_invoice_status_fails(status: str | None) -> None:
    """Statuses outside the contract categories should fail validation."""
    data = pd.DataFrame(
        {
            "invoice_id": ["I001"],
            "subscription_id": ["S001"],
            "invoice_date": pd.to_datetime(["2025-01-01"]),
            "amount": [99.99],
            "currency": ["USD"],
            "invoice_status": [status],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(data)


def test_unexpected_column_fails(valid_invoices: pd.DataFrame) -> None:
    """Columns outside the data contract should be rejected."""
    valid_invoices["unexpected_field"] = "unexpected"

    with pytest.raises(pa.errors.SchemaError):
        INVOICE_SCHEMA.validate(valid_invoices)
