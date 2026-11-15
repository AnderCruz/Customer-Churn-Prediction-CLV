"""Normalize contract dataset values into explicit pandas dtypes."""

from __future__ import annotations

import math
import re
from decimal import Decimal, DecimalException
from typing import Literal

import numpy as np
import pandas as pd

ColumnType = Literal["string", "datetime", "float", "required_float", "integer", "boolean"]

DATASET_COLUMN_TYPES: dict[str, dict[str, ColumnType]] = {
    "customers": {
        "customer_id": "string",
        "created_at": "datetime",
        "country": "string",
        "industry": "string",
        "company_size": "string",
        "account_status": "string",
    },
    "subscriptions": {
        "subscription_id": "string",
        "customer_id": "string",
        "plan_id": "string",
        "start_date": "datetime",
        "end_date": "datetime",
        "subscription_status": "string",
        "billing_frequency": "string",
        "recurring_revenue": "float",
        "currency": "string",
        "auto_renew": "boolean",
        "cancellation_date": "datetime",
        "cancellation_reason": "string",
    },
    "subscription_snapshots": {
        "subscription_id": "string",
        "snapshot_date": "datetime",
        "subscription_status": "string",
        "recurring_revenue": "float",
        "currency": "string",
        "plan_id": "string",
        "billing_frequency": "string",
        "auto_renew": "boolean",
    },
    "usage_monthly": {
        "subscription_id": "string",
        "usage_month": "datetime",
        "active_users": "integer",
        "total_users": "integer",
        "sessions_count": "integer",
        "events_count": "integer",
        "usage_volume": "float",
        "usage_metric": "string",
    },
    "invoices": {
        "invoice_id": "string",
        "subscription_id": "string",
        "invoice_date": "datetime",
        "due_date": "datetime",
        "paid_date": "datetime",
        "amount": "required_float",
        "currency": "string",
        "invoice_status": "string",
    },
}

_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
_UTC_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|\+00:00)\Z"
)
_NUMBER_PATTERN = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?\Z")
_BOOLEAN_VALUES = {"true": True, "false": False}
_INT64_MIN = Decimal(-(2**63))
_INT64_MAX = Decimal(2**63 - 1)


class DataTypeNormalizationError(ValueError):
    """Raised when a dataset value cannot be normalized without data loss."""


def _is_missing(value: object) -> bool:
    """Return whether a scalar is a pandas or Python missing value."""
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    return isinstance(value, (float, np.floating)) and math.isnan(float(value))


def _display_value(value: object) -> str:
    """Return a bounded representation suitable for a data error message."""
    rendered = repr(value)
    return rendered if len(rendered) <= 80 else f"{rendered[:77]}..."


def _fail(dataset: str, column: str, value: object, reason: str) -> DataTypeNormalizationError:
    return DataTypeNormalizationError(
        f"dataset {dataset!r}, column {column!r}: {reason}; value {_display_value(value)}"
    )


def _normalize_string(series: pd.Series, dataset: str, column: str) -> pd.Series:
    """Use pandas string dtype and represent empty values as missing."""
    values: list[object] = []
    for value in series.tolist():
        if _is_missing(value) or value == "":
            values.append(pd.NA)
        elif isinstance(value, str):
            values.append(value)
        else:
            raise _fail(dataset, column, value, "expected a string value")
    return pd.Series(pd.array(values, dtype="string"), index=series.index, name=series.name)


def _parse_decimal(value: object, dataset: str, column: str) -> Decimal:
    """Parse a strict decimal token, rejecting whitespace and non-finite values."""
    if not isinstance(value, str) or not _NUMBER_PATTERN.fullmatch(value):
        try:
            decimal_value = Decimal(value) if isinstance(value, str) else None
        except DecimalException:
            decimal_value = None
        if decimal_value is not None and not decimal_value.is_finite():
            raise _fail(dataset, column, value, "numeric value must be finite")
        raise _fail(
            dataset,
            column,
            value,
            "expected a numeric value using a period decimal separator",
        )
    try:
        decimal_value = Decimal(value)
    except DecimalException as exc:
        raise _fail(dataset, column, value, "expected a valid numeric value") from exc
    if not decimal_value.is_finite():
        raise _fail(dataset, column, value, "numeric value must be finite")
    return decimal_value


def _normalize_float(series: pd.Series, dataset: str, column: str, *, required: bool) -> pd.Series:
    """Convert decimal text to float, using missing values without inferring NA tokens."""
    values: list[object] = []
    for value in series.tolist():
        if _is_missing(value) or value == "":
            values.append(np.nan if required else pd.NA)
            continue
        try:
            number = float(_parse_decimal(value, dataset, column))
        except OverflowError as exc:
            raise _fail(
                dataset, column, value, "numeric value is outside the finite float range"
            ) from exc
        if not math.isfinite(number):
            raise _fail(dataset, column, value, "numeric value is outside the finite float range")
        values.append(number)

    dtype = "float64" if required else "Float64"
    return pd.Series(pd.array(values, dtype=dtype), index=series.index, name=series.name)


def _normalize_integer(series: pd.Series, dataset: str, column: str) -> pd.Series:
    """Convert exact integer values to pandas nullable Int64."""
    values: list[object] = []
    for value in series.tolist():
        if _is_missing(value) or value == "":
            values.append(pd.NA)
            continue
        number = _parse_decimal(value, dataset, column)
        if number != number.to_integral_value():
            raise _fail(dataset, column, value, "integer value cannot be fractional")
        if number < _INT64_MIN or number > _INT64_MAX:
            raise _fail(
                dataset, column, value, "integer value is outside the supported Int64 range"
            )
        try:
            values.append(int(number))
        except (OverflowError, ValueError) as exc:
            raise _fail(
                dataset, column, value, "integer value is outside the supported range"
            ) from exc

    try:
        return pd.Series(pd.array(values, dtype="Int64"), index=series.index, name=series.name)
    except (OverflowError, TypeError, ValueError) as exc:
        bad_value = next(
            value for value in series.tolist() if not _is_missing(value) and value != ""
        )
        raise _fail(
            dataset, column, bad_value, "integer value is outside the supported Int64 range"
        ) from exc


def _normalize_boolean(series: pd.Series, dataset: str, column: str) -> pd.Series:
    """Parse only lowercase ``true`` and ``false`` into nullable BooleanDtype."""
    values: list[object] = []
    for value in series.tolist():
        if _is_missing(value) or value == "":
            values.append(pd.NA)
        elif value in _BOOLEAN_VALUES:
            values.append(_BOOLEAN_VALUES[value])
        else:
            raise _fail(dataset, column, value, "expected lowercase 'true' or 'false'")
    return pd.Series(pd.array(values, dtype="boolean"), index=series.index, name=series.name)


def _normalize_datetime(series: pd.Series, dataset: str, column: str) -> pd.Series:
    """Parse ISO dates or UTC ISO timestamps into timezone-aware UTC datetimes."""
    values: list[object] = []
    for value in series.tolist():
        if _is_missing(value) or value == "":
            values.append(pd.NA)
            continue
        if not isinstance(value, str):
            raise _fail(dataset, column, value, "expected an ISO 8601 date or UTC timestamp")
        if not (_DATE_PATTERN.fullmatch(value) or _UTC_TIMESTAMP_PATTERN.fullmatch(value)):
            raise _fail(
                dataset,
                column,
                value,
                "expected YYYY-MM-DD or an ISO 8601 timestamp explicitly in UTC",
            )
        values.append(value)

    try:
        normalized = pd.to_datetime(pd.Series(values), format="ISO8601", utc=True, errors="raise")
    except (TypeError, ValueError, OverflowError) as exc:
        invalid_value = next(
            value
            for value in values
            if value is not pd.NA
            and pd.isna(pd.to_datetime(value, format="ISO8601", utc=True, errors="coerce"))
        )
        raise _fail(dataset, column, invalid_value, "invalid calendar date or timestamp") from exc

    return pd.Series(normalized.array, index=series.index, name=series.name)


def normalize_dataset_types(dataframe: pd.DataFrame, dataset: str) -> pd.DataFrame:
    """Return a normalized copy of one contract dataset without validating its schema.

    Known columns are converted only when present. Missing expected columns and unexpected
    columns are preserved as-is for subsequent schema validation. Empty values in known
    string, nullable numeric, boolean, and datetime columns become pandas missing values.

    Args:
        dataframe: Source DataFrame, normally returned by CSV ingestion.
        dataset: Contract dataset identifier.

    Returns:
        A new DataFrame preserving input row order, index, and column order.

    Raises:
        DataTypeNormalizationError: If the dataset name or a known column value is invalid.
    """
    if dataset not in DATASET_COLUMN_TYPES:
        raise DataTypeNormalizationError(f"unknown dataset {dataset!r}")
    if not isinstance(dataframe, pd.DataFrame):
        raise DataTypeNormalizationError(f"dataset {dataset!r}: expected a pandas DataFrame")

    normalized = dataframe.copy(deep=True)
    for column, column_type in DATASET_COLUMN_TYPES[dataset].items():
        if column not in normalized.columns:
            continue
        source = normalized[column]
        if column_type == "string":
            result = _normalize_string(source, dataset, column)
        elif column_type == "datetime":
            result = _normalize_datetime(source, dataset, column)
        elif column_type in ("float", "required_float"):
            result = _normalize_float(
                source, dataset, column, required=column_type == "required_float"
            )
        elif column_type == "integer":
            result = _normalize_integer(source, dataset, column)
        else:
            result = _normalize_boolean(source, dataset, column)
        normalized[column] = result

    return normalized


def normalize_client_datasets(
    datasets: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Normalize a mapping of dataset identifiers to DataFrames without mutating inputs."""
    normalized: dict[str, pd.DataFrame] = {}
    for dataset, dataframe in datasets.items():
        normalized[dataset] = normalize_dataset_types(dataframe, dataset)
    return normalized
