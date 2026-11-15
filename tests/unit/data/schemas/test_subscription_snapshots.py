"""Unit tests for the subscription snapshot data schema."""

import pandas as pd
import pandera.pandas as pa
import pytest

from nowa_customer_intelligence.data.schemas import SUBSCRIPTION_SNAPSHOT_SCHEMA


@pytest.fixture
def valid_snapshots() -> pd.DataFrame:
    """Return valid snapshots, including multiple dates for the same subscription."""
    return pd.DataFrame(
        {
            "subscription_id": ["S001", "S001", "S002"],
            "snapshot_date": pd.to_datetime(["2025-01-31", "2025-02-28", "2025-01-31"], utc=True),
            "subscription_status": ["active", "paused", "trial"],
            "recurring_revenue": [29.99, 29.99, 0.0],
            "currency": ["USD", "USD", "EUR"],
            "plan_id": ["P001", "P001", None],
            "billing_frequency": ["monthly", "monthly", None],
            "auto_renew": pd.Series([True, None, False], dtype="boolean"),
        }
    )


def test_valid_snapshot_data_passes(valid_snapshots: pd.DataFrame) -> None:
    """Valid snapshot data should pass schema validation."""
    result = SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(valid_snapshots)

    assert len(result) == 3
    assert result["subscription_id"].duplicated().any()


def test_same_subscription_with_different_dates_passes(
    valid_snapshots: pd.DataFrame,
) -> None:
    """A subscription may have snapshots on different dates."""
    result = SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(valid_snapshots.iloc[:2])

    assert result["subscription_id"].tolist() == ["S001", "S001"]


def test_missing_optional_columns_are_added() -> None:
    """Missing optional columns should be added as null columns."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "snapshot_date": pd.to_datetime(["2025-01-31"], utc=True),
            "subscription_status": ["active"],
        }
    )

    result = SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(data)
    optional_columns = [
        "recurring_revenue",
        "currency",
        "plan_id",
        "billing_frequency",
        "auto_renew",
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
            "snapshot_date": pd.to_datetime(["2025-01-31"], utc=True),
            "subscription_status": ["active"],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(data)


@pytest.mark.parametrize("field", ["snapshot_date", "subscription_status"])
def test_null_required_field_fails(field: str) -> None:
    """Required snapshot fields should reject null values."""
    values: dict[str, list[object]] = {
        "subscription_id": ["S001"],
        "snapshot_date": [pd.Timestamp("2025-01-31", tz="UTC")],
        "subscription_status": ["active"],
    }
    values[field] = [None]
    data = pd.DataFrame(values)

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(data)


def test_duplicate_composite_key_fails(valid_snapshots: pd.DataFrame) -> None:
    """Duplicate subscription and snapshot date pairs should fail validation."""
    valid_snapshots.loc[1, "snapshot_date"] = pd.Timestamp("2025-01-31", tz="UTC")

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(valid_snapshots)


@pytest.mark.parametrize("status", ["pending", "ACTIVE", "", None])
def test_invalid_subscription_status_fails(status: str | None) -> None:
    """Statuses outside the contract categories should fail validation."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "snapshot_date": pd.to_datetime(["2025-01-31"], utc=True),
            "subscription_status": [status],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(data)


def test_negative_recurring_revenue_fails(valid_snapshots: pd.DataFrame) -> None:
    """Negative recurring revenue should fail validation."""
    valid_snapshots.loc[0, "recurring_revenue"] = -0.01

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(valid_snapshots)


@pytest.mark.parametrize("currency", ["us", "USd", "USDD", "1US"])
def test_invalid_currency_format_fails(currency: str) -> None:
    """Currency values must contain three uppercase letters."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "snapshot_date": pd.to_datetime(["2025-01-31"], utc=True),
            "subscription_status": ["active"],
            "currency": [currency],
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(data)


def test_nullable_auto_renew_values_pass() -> None:
    """Auto-renew may contain true, false, and null values."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001", "S002", "S003"],
            "snapshot_date": pd.to_datetime(["2025-01-31", "2025-01-31", "2025-01-31"], utc=True),
            "subscription_status": ["active", "active", "active"],
            "auto_renew": pd.Series([True, False, None], dtype="boolean"),
        }
    )

    result = SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(data)

    assert result["auto_renew"].tolist() == [True, False, pd.NA]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("subscription_id", 1001),
        ("snapshot_date", "2025-01-31"),
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
            "snapshot_date": pd.to_datetime(["2025-01-31"], utc=True),
            "subscription_status": ["active"],
        }
    )
    data[field] = [value]

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(data)


def test_unexpected_column_fails(valid_snapshots: pd.DataFrame) -> None:
    """Columns outside the data contract should be rejected."""
    valid_snapshots["unexpected_field"] = "unexpected"

    with pytest.raises(pa.errors.SchemaError):
        SUBSCRIPTION_SNAPSHOT_SCHEMA.validate(valid_snapshots)
