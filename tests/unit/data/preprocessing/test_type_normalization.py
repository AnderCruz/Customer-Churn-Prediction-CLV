"""Unit tests for explicit and non-destructive dataset type normalization."""

import pandas as pd
import pandera.errors as pa_errors
import pytest

from nowa_customer_intelligence.data.preprocessing import (
    DataTypeNormalizationError,
    normalize_client_datasets,
    normalize_dataset_types,
    type_normalization,
)
from nowa_customer_intelligence.data.schemas import (
    CUSTOMER_SCHEMA,
    INVOICE_SCHEMA,
    SUBSCRIPTION_SCHEMA,
    SUBSCRIPTION_SNAPSHOT_SCHEMA,
    USAGE_MONTHLY_SCHEMA,
)

VALID_DATASETS = {
    "customers": pd.DataFrame(
        {
            "customer_id": ["00123"],
            "created_at": ["2025-01-15"],
            "country": ["UK"],
            "industry": ["SaaS"],
            "company_size": ["small"],
            "account_status": ["active"],
        }
    ),
    "subscriptions": pd.DataFrame(
        {
            "subscription_id": ["0007"],
            "customer_id": ["00123"],
            "plan_id": ["plan-a"],
            "start_date": ["2025-01-15"],
            "end_date": [""],
            "subscription_status": ["active"],
            "billing_frequency": ["monthly"],
            "recurring_revenue": ["29.99"],
            "currency": ["GBP"],
            "auto_renew": ["true"],
            "cancellation_date": [""],
            "cancellation_reason": [""],
        }
    ),
    "subscription_snapshots": pd.DataFrame(
        {
            "subscription_id": ["0007"],
            "snapshot_date": ["2025-01-31"],
            "subscription_status": ["active"],
            "recurring_revenue": ["29.99"],
            "currency": ["GBP"],
            "plan_id": ["plan-a"],
            "billing_frequency": ["monthly"],
            "auto_renew": ["false"],
        }
    ),
    "usage_monthly": pd.DataFrame(
        {
            "subscription_id": ["0007"],
            "usage_month": ["2025-01-01"],
            "active_users": ["2"],
            "total_users": ["3"],
            "sessions_count": ["0"],
            "events_count": ["18"],
            "usage_volume": ["0"],
            "usage_metric": ["requests"],
        }
    ),
    "invoices": pd.DataFrame(
        {
            "invoice_id": ["000045"],
            "subscription_id": ["0007"],
            "invoice_date": ["2025-01-01"],
            "due_date": ["2025-01-15"],
            "paid_date": ["2025-01-10"],
            "amount": ["29.99"],
            "currency": ["GBP"],
            "invoice_status": ["paid"],
        }
    ),
}

SCHEMAS = {
    "customers": CUSTOMER_SCHEMA,
    "subscriptions": SUBSCRIPTION_SCHEMA,
    "subscription_snapshots": SUBSCRIPTION_SNAPSHOT_SCHEMA,
    "usage_monthly": USAGE_MONTHLY_SCHEMA,
    "invoices": INVOICE_SCHEMA,
}


@pytest.mark.parametrize("dataset", VALID_DATASETS)
def test_normalizes_all_supported_datasets(dataset: str) -> None:
    """Every supported dataset should receive its schema-compatible dtypes."""
    normalized = normalize_dataset_types(VALID_DATASETS[dataset], dataset)

    assert normalized is not VALID_DATASETS[dataset]
    SCHEMAS[dataset].validate(normalized)


def test_identifier_strings_preserve_leading_zeros() -> None:
    """Identifiers should remain strings with their original leading zeros."""
    normalized = normalize_dataset_types(VALID_DATASETS["customers"], "customers")

    assert normalized.loc[0, "customer_id"] == "00123"
    assert isinstance(normalized.loc[0, "customer_id"], str)


@pytest.mark.parametrize(
    ("dataset", "column", "dtype"),
    [
        ("subscriptions", "recurring_revenue", "Float64"),
        ("usage_monthly", "usage_volume", "Float64"),
        ("invoices", "amount", "float64"),
    ],
)
def test_empty_nullable_numeric_fields_are_missing(dataset: str, column: str, dtype: str) -> None:
    """Empty numeric fields should use the expected nullable representation."""
    source = VALID_DATASETS[dataset].copy()
    source[column] = ""

    normalized = normalize_dataset_types(source, dataset)

    assert str(normalized[column].dtype) == dtype
    assert pd.isna(normalized.loc[0, column])


@pytest.mark.parametrize(
    ("dataset", "column"),
    [
        ("subscriptions", "end_date"),
        ("subscriptions", "cancellation_date"),
        ("invoices", "due_date"),
        ("invoices", "paid_date"),
    ],
)
def test_empty_nullable_date_fields_become_nat(dataset: str, column: str) -> None:
    """Empty nullable date fields should normalize to timezone-aware NaT."""
    source = VALID_DATASETS[dataset].copy()
    source[column] = ""
    normalized = normalize_dataset_types(source, dataset)

    assert isinstance(normalized[column].dtype, pd.DatetimeTZDtype)
    assert str(normalized[column].dtype.tz) == "UTC"
    assert pd.isna(normalized.loc[0, column])


@pytest.mark.parametrize(
    "column", ["active_users", "total_users", "sessions_count", "events_count"]
)
def test_empty_nullable_integer_fields_use_int64(column: str) -> None:
    """Empty usage counts should use nullable Int64 with pd.NA."""
    source = VALID_DATASETS["usage_monthly"].copy()
    source[column] = ""

    normalized = normalize_dataset_types(source, "usage_monthly")

    assert normalized[column].dtype == pd.Int64Dtype()
    assert normalized.loc[0, column] is pd.NA


@pytest.mark.parametrize("value, expected", [("true", True), ("false", False)])
def test_boolean_values_are_parsed_case_sensitively(value: str, expected: bool) -> None:
    """Only lowercase contract boolean values should be converted."""
    source = VALID_DATASETS["subscriptions"].copy()
    source["auto_renew"] = value

    normalized = normalize_dataset_types(source, "subscriptions")

    assert normalized["auto_renew"].dtype == pd.BooleanDtype()
    assert bool(normalized.loc[0, "auto_renew"]) is expected


def test_empty_nullable_boolean_becomes_pd_na() -> None:
    """An empty boolean field should use pandas nullable BooleanDtype."""
    source = VALID_DATASETS["subscriptions"].copy()
    source["auto_renew"] = ""

    normalized = normalize_dataset_types(source, "subscriptions")

    assert normalized.loc[0, "auto_renew"] is pd.NA
    assert normalized["auto_renew"].dtype == pd.BooleanDtype()


@pytest.mark.parametrize("value", ["TRUE", "False", "yes", "0", " true"])
def test_invalid_boolean_values_raise_contextual_error(value: str) -> None:
    """Unsupported boolean spellings should identify dataset and column."""
    source = VALID_DATASETS["subscriptions"].copy()
    source["auto_renew"] = value

    with pytest.raises(DataTypeNormalizationError, match="subscriptions.*auto_renew"):
        normalize_dataset_types(source, "subscriptions")


@pytest.mark.parametrize(
    ("dataset", "column", "value"),
    [
        ("subscriptions", "recurring_revenue", "GBP 29"),
        ("usage_monthly", "usage_volume", "1,000"),
        ("invoices", "amount", "NaN"),
        ("subscriptions", "recurring_revenue", "Infinity"),
        ("usage_monthly", "usage_volume", "1e400"),
    ],
)
def test_invalid_or_non_finite_numeric_values_raise(dataset: str, column: str, value: str) -> None:
    """Invalid numeric tokens, NaN literals, and infinities must be rejected."""
    source = VALID_DATASETS[dataset].copy()
    source[column] = value

    with pytest.raises(DataTypeNormalizationError, match=f"{dataset}.*{column}"):
        normalize_dataset_types(source, dataset)


@pytest.mark.parametrize("value", ["1.5", "-2.25"])
def test_fractional_integer_values_raise(value: str) -> None:
    """Usage count fields must reject fractional values rather than round."""
    source = VALID_DATASETS["usage_monthly"].copy()
    source["active_users"] = value

    with pytest.raises(DataTypeNormalizationError, match="fractional"):
        normalize_dataset_types(source, "usage_monthly")


@pytest.mark.parametrize(
    "value",
    ["-9223372036854775808", "9223372036854775807"],
)
def test_int64_boundaries_are_accepted(value: str) -> None:
    """The signed Int64 minimum and maximum should normalize exactly."""
    source = VALID_DATASETS["usage_monthly"].copy()
    source["active_users"] = value

    normalized = normalize_dataset_types(source, "usage_monthly")

    assert normalized.loc[0, "active_users"] == int(value)
    assert normalized["active_users"].dtype == pd.Int64Dtype()


@pytest.mark.parametrize(
    "value",
    [
        "-9223372036854775809",
        "9223372036854775808",
        "1e1000000000",
        "-1e1000000000",
    ],
)
def test_int64_out_of_range_values_fail_before_int_conversion(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Out-of-range Decimals must fail before Python int conversion is attempted."""
    source = VALID_DATASETS["usage_monthly"].copy()
    source["active_users"] = value

    def fail_if_converted(_: object) -> int:
        raise AssertionError("out-of-range Decimal was converted to Python int")

    monkeypatch.setattr(type_normalization, "int", fail_if_converted, raising=False)

    with pytest.raises(DataTypeNormalizationError, match="supported Int64 range"):
        normalize_dataset_types(source, "usage_monthly")


@pytest.mark.parametrize("value", ["2025-02-30", "01/02/2025", "2025-1-02"])
def test_invalid_or_ambiguous_dates_raise(value: str) -> None:
    """Non-ISO or impossible calendar dates should not become NaT."""
    source = VALID_DATASETS["customers"].copy()
    source["created_at"] = value

    with pytest.raises(DataTypeNormalizationError, match="customers.*created_at"):
        normalize_dataset_types(source, "customers")


@pytest.mark.parametrize(
    "value",
    [
        "2025-01-01T12:00:00",
        "2025-01-01T12:00:00+01:00",
        "2025-01-01T12:00:00Ztrailing",
    ],
)
def test_invalid_or_non_utc_timestamps_raise(value: str) -> None:
    """Timestamps must be valid ISO 8601 and explicitly UTC."""
    source = VALID_DATASETS["customers"].copy()
    source["created_at"] = value

    with pytest.raises(DataTypeNormalizationError, match="customers.*created_at"):
        normalize_dataset_types(source, "customers")


def test_utc_timestamps_are_preserved_as_utc() -> None:
    """Valid UTC timestamps should retain timezone information after normalization."""
    source = VALID_DATASETS["customers"].copy()
    source["created_at"] = "2025-01-15T12:34:56Z"

    normalized = normalize_dataset_types(source, "customers")

    assert normalized.loc[0, "created_at"] == pd.Timestamp("2025-01-15T12:34:56Z")
    assert str(normalized["created_at"].dtype.tz) == "UTC"
    CUSTOMER_SCHEMA.validate(normalized)


@pytest.mark.parametrize("value", ["NA", "NULL", "NaN", "None", "Unknown"])
def test_literal_missing_like_strings_are_preserved(value: str) -> None:
    """Only empty values become missing; arbitrary literal strings remain intact."""
    source = VALID_DATASETS["customers"].copy()
    source["country"] = value

    normalized = normalize_dataset_types(source, "customers")

    assert normalized.loc[0, "country"] == value
    assert not pd.isna(normalized.loc[0, "country"])


def test_required_blank_string_remains_schema_detectable() -> None:
    """Required identifier blanks become missing values that the schema rejects."""
    source = VALID_DATASETS["customers"].copy()
    source["customer_id"] = ""
    normalized = normalize_dataset_types(source, "customers")

    assert pd.isna(normalized.loc[0, "customer_id"])
    with pytest.raises(pa_errors.SchemaError):
        CUSTOMER_SCHEMA.validate(normalized)


def test_required_blank_datetime_remains_schema_detectable() -> None:
    """Required blank dates become NaT for the schema's non-null check."""
    source = VALID_DATASETS["customers"].copy()
    source["created_at"] = ""
    normalized = normalize_dataset_types(source, "customers")

    assert pd.isna(normalized.loc[0, "created_at"])
    with pytest.raises(pa_errors.SchemaError):
        CUSTOMER_SCHEMA.validate(normalized)


def test_required_blank_amount_remains_schema_detectable() -> None:
    """A blank required amount becomes NaN and remains visible to schema validation."""
    source = VALID_DATASETS["invoices"].copy()
    source["amount"] = ""
    normalized = normalize_dataset_types(source, "invoices")

    assert pd.isna(normalized.loc[0, "amount"])
    with pytest.raises(pa_errors.SchemaError):
        INVOICE_SCHEMA.validate(normalized)


def test_input_values_index_and_column_order_are_preserved() -> None:
    """Normalization should return a new frame and preserve source structure."""
    source = VALID_DATASETS["subscriptions"].copy()
    source.index = pd.Index([8], name="source_row")
    source["unexpected_field"] = "keep"
    before = source.copy(deep=True)
    original_columns = list(source.columns)

    normalized = normalize_dataset_types(source, "subscriptions")

    pd.testing.assert_frame_equal(source, before)
    assert normalized is not source
    assert normalized.index.equals(source.index)
    assert list(normalized.columns) == original_columns
    assert normalized["unexpected_field"].tolist() == ["keep"]


def test_missing_expected_columns_are_not_added() -> None:
    """Absent known fields remain absent for later schema processing."""
    source = pd.DataFrame({"customer_id": ["001"]}, index=[10])

    normalized = normalize_dataset_types(source, "customers")

    assert list(normalized.columns) == ["customer_id"]
    assert normalized.index.tolist() == [10]


def test_unknown_dataset_name_raises_clear_error() -> None:
    """Unsupported dataset identifiers should fail before transforming data."""
    with pytest.raises(DataTypeNormalizationError, match="unknown dataset"):
        normalize_dataset_types(pd.DataFrame(), "unknown")


def test_client_dataset_normalization_returns_new_mapping_and_frames() -> None:
    """The mapping helper should normalize each dataset without mutating its inputs."""
    source = {"customers": VALID_DATASETS["customers"].copy()}
    before = source["customers"].copy(deep=True)

    normalized = normalize_client_datasets(source)

    assert normalized is not source
    assert normalized["customers"] is not source["customers"]
    pd.testing.assert_frame_equal(source["customers"], before)
