"""Pandera schema for subscription data validation."""

import pandas as pd
import pandera.pandas as pa

SUBSCRIPTION_SCHEMA = pa.DataFrameSchema(
    columns={
        "subscription_id": pa.Column(
            str,
            nullable=False,
            unique=True,
            checks=[
                pa.Check(lambda identifiers: identifiers.str.strip().ne("")),
                pa.Check(lambda identifiers: identifiers.eq(identifiers.str.strip())),
            ],
        ),
        "customer_id": pa.Column(
            str,
            nullable=False,
            checks=[
                pa.Check(lambda identifiers: identifiers.str.strip().ne("")),
                pa.Check(lambda identifiers: identifiers.eq(identifiers.str.strip())),
            ],
        ),
        "plan_id": pa.Column(str, nullable=True),
        "start_date": pa.Column(pa.DateTime, nullable=False),
        "end_date": pa.Column(pa.DateTime, nullable=True),
        "subscription_status": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.isin(
                ["active", "trial", "cancelled", "expired", "suspended", "paused"]
            ),
        ),
        "billing_frequency": pa.Column(str, nullable=True),
        "recurring_revenue": pa.Column(
            float,
            nullable=True,
            default=float("nan"),
            checks=pa.Check.ge(0),
        ),
        "currency": pa.Column(
            str,
            nullable=True,
            checks=pa.Check.str_matches(r"^[A-Z]{3}$"),
        ),
        "auto_renew": pa.Column(pd.BooleanDtype(), nullable=True),
        "cancellation_date": pa.Column(pa.DateTime, nullable=True),
        "cancellation_reason": pa.Column(str, nullable=True),
    },
    strict=True,
    coerce=False,
    add_missing_columns=True,
)
