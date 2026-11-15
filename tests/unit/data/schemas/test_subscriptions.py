"""Unit tests for the subscription data schema."""

import pandas as pd
import pandera.pandas as pa
import pytest

from nowa_customer_intelligence.data.schemas import SUBSCRIPTION_SCHEMA


@pytest.fixture
def valid_subscriptions() -> pd.DataFrame:
    """Return a valid subscription dataset."""
    return pd.DataFrame(
        {
            "subscription_id": ["S001", "S002"],
            "customer_id": ["C001", "C001"],
            "plan_id": ["P001", None],
            "start_date": pd.to_datetime(["2025-01-15", "2025-02-20"]),
            "end_date": [pd.NaT, pd.NaT],
            "subscription_status": ["active", "trial"],
            "billing_frequency": ["monthly", None],
            "recurring_revenue": [29.99, 0],
            "currency": ["USD", "EUR"],
            "auto_renew": pd.Series([True, False], dtype="boolean"),
            "cancellation_date": [pd.NaT, pd.NaT],
            "cancellation_reason": [None, None],
        }
    )


def test_valid_subscription_data_passes(valid_subscriptions: pd.DataFrame) -> None:
    """Valid subscription data should pass schema validation."""
    result = SUBSCRIPTION_SCHEMA.validate(valid_subscriptions)

    assert len(result) == 2
    assert result["subscription_id"].is_unique


def test_missing_optional_columns_are_added() -> None:
    """Missing optional columns should be added as null columns."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "customer_id": ["C001"],
            "start_date": pd.to_datetime(["2025-01-15"]),
            "subscription_status": ["active"],
        }
    )

    result = SUBSCRIPTION_SCHEMA.validate(data)

    optional_columns = [
        "plan_id",
        "end_date",
        "billing_frequency",
        "recurring_revenue",
        "currency",
        "auto_renew",
        "cancellation_date",
        "cancellation_reason",
    ]
    assert set(optional_columns).issubset(result.columns)
    assert result[optional_columns].isna().all().all()


@pytest.mark.parametrize(
    "subscription_id",
    [None, "", "   ", " S001", "S001 "],
    ids=["null", "empty", "whitespace-only", "leading-whitespace", "trailing-whitespace"],
)
def test_invalid_subscription_id_fails(subscription_id: str | None) -> None:
    """Invalid subscription identifiers should fail validation."""
    data = pd.DataFrame(
        {
            "subscription_id": [subscription_id],
            "customer_id": ["C001"],
            "start_date": pd.to_datetime(["2025-01-15"]),
            "subscription_status": ["active"],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(data)


@pytest.mark.parametrize(
    "customer_id",
    [None, "", "   ", " C001", "C001 "],
    ids=["null", "empty", "whitespace-only", "leading-whitespace", "trailing-whitespace"],
)
def test_invalid_customer_id_fails(customer_id: str | None) -> None:
    """Invalid customer identifiers should fail validation."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "customer_id": [customer_id],
            "start_date": pd.to_datetime(["2025-01-15"]),
            "subscription_status": ["active"],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(data)


def test_duplicate_subscription_id_fails(valid_subscriptions: pd.DataFrame) -> None:
    """Duplicate subscription identifiers should fail validation."""
    valid_subscriptions.loc[1, "subscription_id"] = "S001"

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(valid_subscriptions)


@pytest.mark.parametrize("status", ["pending", "ACTIVE", "", None])
def test_invalid_subscription_status_fails(status: str | None) -> None:
    """Statuses outside the approved values should fail validation."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "customer_id": ["C001"],
            "start_date": pd.to_datetime(["2025-01-15"]),
            "subscription_status": [status],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(data)


def test_negative_recurring_revenue_fails(valid_subscriptions: pd.DataFrame) -> None:
    """Negative recurring revenue should fail validation."""
    valid_subscriptions.loc[0, "recurring_revenue"] = -0.01

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(valid_subscriptions)


@pytest.mark.parametrize("currency", ["us", "USd", "USDD", "1US"])
def test_invalid_currency_format_fails(currency: str) -> None:
    """Currency values must contain three uppercase letters."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "customer_id": ["C001"],
            "start_date": pd.to_datetime(["2025-01-15"]),
            "subscription_status": ["active"],
            "currency": [currency],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(data)


@pytest.mark.parametrize("field", ["start_date", "subscription_status"])
def test_null_required_field_fails(field: str) -> None:
    """Required subscription fields should reject null values."""
    values: dict[str, list[object]] = {
        "subscription_id": ["S001"],
        "customer_id": ["C001"],
        "start_date": [pd.Timestamp("2025-01-15")],
        "subscription_status": ["active"],
    }
    values[field] = [None]
    data = pd.DataFrame(values)

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subscription_id", 1001),
        ("start_date", "2025-01-15"),
        ("subscription_status", 1),
        ("recurring_revenue", "29.99"),
        ("auto_renew", "true"),
    ],
)
def test_invalid_field_type_fails(field: str, value: object) -> None:
    """Values with types outside the schema should fail without coercion."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "customer_id": ["C001"],
            "start_date": pd.to_datetime(["2025-01-15"]),
            "subscription_status": ["active"],
        }
    )
    data[field] = [value]

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(data)


def test_unexpected_column_fails(valid_subscriptions: pd.DataFrame) -> None:
    """Columns outside the data contract should be rejected."""
    valid_subscriptions["unexpected_field"] = "unexpected"

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SCHEMA.validate(valid_subscriptions)
