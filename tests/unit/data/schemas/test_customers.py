"""Unit tests for the customer data schema."""

import pandas as pd
import pandera.pandas as pa
import pytest

from nowa_customer_intelligence.data.schemas import CUSTOMER_SCHEMA


@pytest.fixture
def valid_customers() -> pd.DataFrame:
    """Return a valid customer dataset."""
    return pd.DataFrame(
        {
            "customer_id": ["C001", "C002"],
            "created_at": pd.to_datetime(["2025-01-15", "2025-02-20"], utc=True),
            "country": ["UK", "UK"],
            "industry": ["Technology", "Finance"],
            "company_size": ["Small", "Medium"],
            "account_status": ["active", "active"],
        }
    )


def test_valid_customer_data_passes(valid_customers: pd.DataFrame) -> None:
    """Valid customer data should pass schema validation."""
    result = CUSTOMER_SCHEMA.validate(valid_customers)

    assert len(result) == 2
    assert result["customer_id"].is_unique


@pytest.mark.parametrize(
    "customer_id",
    ["", "   ", " C001", "C001 "],
    ids=["empty", "whitespace-only", "leading-whitespace", "trailing-whitespace"],
)
def test_invalid_customer_id_whitespace_fails(customer_id: str) -> None:
    """Empty or edge-whitespace customer identifiers should fail validation."""
    data = pd.DataFrame(
        {
            "customer_id": [customer_id],
            "created_at": pd.to_datetime(["2025-01-15"], utc=True),
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        CUSTOMER_SCHEMA.validate(data)


def test_missing_optional_columns_are_added() -> None:
    """Missing optional columns should be added as null columns."""
    data = pd.DataFrame(
        {
            "customer_id": ["C001"],
            "created_at": pd.to_datetime(["2025-01-15"], utc=True),
        }
    )

    result = CUSTOMER_SCHEMA.validate(data)

    assert "country" in result.columns
    assert "industry" in result.columns
    assert "company_size" in result.columns
    assert "account_status" in result.columns
    assert result["country"].isna().all()


def test_null_customer_id_fails(valid_customers: pd.DataFrame) -> None:
    """Null customer identifiers should fail validation."""
    valid_customers.loc[0, "customer_id"] = None

    with pytest.raises(pa.errors.SchemaError):
        CUSTOMER_SCHEMA.validate(valid_customers)


def test_duplicate_customer_id_fails(valid_customers: pd.DataFrame) -> None:
    """Duplicate customer identifiers should fail validation."""
    valid_customers.loc[1, "customer_id"] = "C001"

    with pytest.raises(pa.errors.SchemaError):
        CUSTOMER_SCHEMA.validate(valid_customers)


def test_null_created_at_fails(valid_customers: pd.DataFrame) -> None:
    """Null creation dates should fail validation."""
    valid_customers.loc[0, "created_at"] = pd.NaT

    with pytest.raises(pa.errors.SchemaError):
        CUSTOMER_SCHEMA.validate(valid_customers)


def test_invalid_customer_id_type_fails() -> None:
    """Non-string customer identifiers should fail validation."""
    data = pd.DataFrame(
        {
            "customer_id": [1001],
            "created_at": pd.to_datetime(["2025-01-15"], utc=True),
        }
    )

    with pytest.raises(pa.errors.SchemaError):
        CUSTOMER_SCHEMA.validate(data)


def test_unexpected_column_fails(valid_customers: pd.DataFrame) -> None:
    """Columns outside the data contract should be rejected."""
    valid_customers["unexpected_field"] = "unexpected"

    with pytest.raises(pa.errors.SchemaError):
        CUSTOMER_SCHEMA.validate(valid_customers)
