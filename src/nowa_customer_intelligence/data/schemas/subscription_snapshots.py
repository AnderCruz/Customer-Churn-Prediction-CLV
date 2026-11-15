"""Pandera schema for subscription snapshot data validation."""

import pandas as pd
import pandera.pandas as pa

SUBSCRIPTION_SNAPSHOT_SCHEMA = pa.DataFrameSchema(
    columns={
        "subscription_id": pa.Column(
            str,
            nullable=False,
            checks=[
                pa.Check(lambda identifiers: identifiers.str.strip().ne("")),
                pa.Check(lambda identifiers: identifiers.eq(identifiers.str.strip())),
            ],
        ),
        "snapshot_date": pa.Column(pd.DatetimeTZDtype(unit="ns", tz="UTC"), nullable=False),
        "subscription_status": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.isin(
                ["active", "trial", "cancelled", "expired", "suspended", "paused"]
            ),
        ),
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
        "plan_id": pa.Column(str, nullable=True),
        "billing_frequency": pa.Column(str, nullable=True),
        "auto_renew": pa.Column(pd.BooleanDtype(), nullable=True),
    },
    unique=["subscription_id", "snapshot_date"],
    strict=True,
    coerce=False,
    add_missing_columns=True,
)
