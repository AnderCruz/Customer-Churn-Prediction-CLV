"""Unit tests for the monthly usage data schema."""

import pandas as pd
import pandera.pandas as pa
import pytest

from nowa_customer_intelligence.data.schemas import USAGE_MONTHLY_SCHEMA


@pytest.fixture
def valid_usage() -> pd.DataFrame:
    """Return valid usage records, including multiple months per subscription."""
    return pd.DataFrame(
        {
            "subscription_id": ["S001", "S001", "S002"],
            "usage_month": pd.to_datetime(["2025-01-01", "2025-02-01", "2025-01-01"]),
            "active_users": pd.Series([4, 5, 2], dtype="Int64"),
            "total_users": pd.Series([6, 6, 2], dtype="Int64"),
            "sessions_count": pd.Series([120, 135, 40], dtype="Int64"),
            "events_count": pd.Series([400, 450, 90], dtype="Int64"),
            "usage_volume": [125.5, 140.0, 42.25],
            "usage_metric": ["GB", "GB", "GB"],
        }
    )


def test_valid_usage_data_passes(valid_usage: pd.DataFrame) -> None:
    """Valid usage data should pass schema validation."""
    result = USAGE_MONTHLY_SCHEMA.validate(valid_usage)

    assert len(result) == 3
    assert result["subscription_id"].duplicated().any()


def test_same_subscription_with_different_months_passes(
    valid_usage: pd.DataFrame,
) -> None:
    """A subscription may have usage records for different months."""
    result = USAGE_MONTHLY_SCHEMA.validate(valid_usage.iloc[:2])

    assert result["subscription_id"].tolist() == ["S001", "S001"]


def test_missing_optional_columns_are_added() -> None:
    """Missing optional columns should be added as null columns."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "usage_month": pd.to_datetime(["2025-01-01"]),
        }
    )
    optional_columns = [
        "active_users",
        "total_users",
        "sessions_count",
        "events_count",
        "usage_volume",
        "usage_metric",
    ]

    result = USAGE_MONTHLY_SCHEMA.validate(data)

    assert set(optional_columns).issubset(result.columns)
    assert result[optional_columns].isna().all().all()


@pytest.mark.parametrize("required_column", ["subscription_id", "usage_month"])
def test_missing_required_column_fails(required_column: str) -> None:
    """Missing required columns are added as null and then rejected."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "usage_month": pd.to_datetime(["2025-01-01"]),
        }
    ).drop(columns=required_column)

    with pytest.raises(pa.errors.SchemaError):
        USAGE_MONTHLY_SCHEMA.validate(data)


@pytest.mark.parametrize("field", ["subscription_id", "usage_month"])
def test_null_required_field_fails(field: str) -> None:
    """Required usage fields should reject null values."""
    values: dict[str, list[object]] = {
        "subscription_id": ["S001"],
        "usage_month": [pd.Timestamp("2025-01-01")],
    }
    values[field] = [None]
    data = pd.DataFrame(values)

    with pytest.raises(pa.errors.SchemaError):
        USAGE_MONTHLY_SCHEMA.validate(data)


def test_nullable_fields_accept_null_values() -> None:
    """Optional usage fields should accept null values."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "usage_month": pd.to_datetime(["2025-01-01"]),
            "active_users": pd.Series([None], dtype="Int64"),
            "total_users": pd.Series([None], dtype="Int64"),
            "sessions_count": pd.Series([None], dtype="Int64"),
            "events_count": pd.Series([None], dtype="Int64"),
            "usage_volume": pd.Series([None], dtype="float64"),
            "usage_metric": [None],
        }
    )

    result = USAGE_MONTHLY_SCHEMA.validate(data)

    assert result.iloc[0].drop(labels=["subscription_id", "usage_month"]).isna().all()


@pytest.mark.parametrize(
    "subscription_id",
    ["", "   ", " S001", "S001 "],
    ids=["empty", "whitespace-only", "leading-whitespace", "trailing-whitespace"],
)
def test_invalid_subscription_id_fails(subscription_id: str) -> None:
    """Empty or edge-whitespace subscription identifiers should fail."""
    data = pd.DataFrame(
        {
            "subscription_id": [subscription_id],
            "usage_month": pd.to_datetime(["2025-01-01"]),
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        USAGE_MONTHLY_SCHEMA.validate(data)


def test_duplicate_composite_key_fails(valid_usage: pd.DataFrame) -> None:
    """Duplicate subscription and month pairs should fail validation."""
    valid_usage.loc[1, "usage_month"] = pd.Timestamp("2025-01-01")

    with pytest.raises(pa.errors.SchemaError):
        USAGE_MONTHLY_SCHEMA.validate(valid_usage)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("usage_month", "2025-01-01"),
        ("active_users", "4"),
        ("sessions_count", 1.5),
        ("usage_volume", "125.5"),
    ],
)
def test_invalid_field_type_fails(field: str, value: object) -> None:
    """Values with types outside the contract should fail without coercion."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "usage_month": pd.to_datetime(["2025-01-01"]),
        }
    )
    data[field] = [value]

    with pytest.raises(pa.errors.SchemaError):
        USAGE_MONTHLY_SCHEMA.validate(data)


@pytest.mark.parametrize(
    "field",
    ["active_users", "total_users", "sessions_count", "events_count", "usage_volume"],
)
def test_negative_usage_value_fails(field: str, valid_usage: pd.DataFrame) -> None:
    """Negative counts and usage volume should fail validation."""
    valid_usage.loc[0, field] = -1

    with pytest.raises(pa.errors.SchemaError):
        USAGE_MONTHLY_SCHEMA.validate(valid_usage)


def test_active_users_cannot_exceed_total_users(valid_usage: pd.DataFrame) -> None:
    """Active users must not exceed total users when both are provided."""
    valid_usage.loc[0, "active_users"] = 7

    with pytest.raises(pa.errors.SchemaError):
        USAGE_MONTHLY_SCHEMA.validate(valid_usage)


def test_active_users_may_exceed_total_users_when_one_is_missing() -> None:
    """The count comparison applies only when both counts are available."""
    data = pd.DataFrame(
        {
            "subscription_id": ["S001"],
            "usage_month": pd.to_datetime(["2025-01-01"]),
            "active_users": pd.Series([7], dtype="Int64"),
            "total_users": pd.Series([None], dtype="Int64"),
        }
    )

    result = USAGE_MONTHLY_SCHEMA.validate(data)

    assert result.loc[0, "active_users"] == 7


def test_unexpected_column_fails(valid_usage: pd.DataFrame) -> None:
    """Columns outside the data contract should be rejected."""
    valid_usage["unexpected_field"] = "unexpected"

    with pytest.raises(pa.errors.SchemaError):
        USAGE_MONTHLY_SCHEMA.validate(valid_usage)
