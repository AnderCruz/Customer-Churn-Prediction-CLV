"""Pandera schema for monthly usage data validation."""

import pandas as pd
import pandera.pandas as pa

USAGE_MONTHLY_SCHEMA = pa.DataFrameSchema(
    columns={
        "subscription_id": pa.Column(
            str,
            nullable=False,
            checks=[
                pa.Check(lambda identifiers: identifiers.str.strip().ne("")),
                pa.Check(lambda identifiers: identifiers.eq(identifiers.str.strip())),
            ],
        ),
        "usage_month": pa.Column(pa.DateTime, nullable=False),
        "active_users": pa.Column(pd.Int64Dtype(), nullable=True, checks=pa.Check.ge(0)),
        "total_users": pa.Column(pd.Int64Dtype(), nullable=True, checks=pa.Check.ge(0)),
        "sessions_count": pa.Column(pd.Int64Dtype(), nullable=True, checks=pa.Check.ge(0)),
        "events_count": pa.Column(pd.Int64Dtype(), nullable=True, checks=pa.Check.ge(0)),
        "usage_volume": pa.Column(
            float,
            nullable=True,
            default=float("nan"),
            checks=pa.Check.ge(0),
        ),
        "usage_metric": pa.Column(str, nullable=True),
    },
    checks=pa.Check(
        lambda frame: (
            frame["active_users"].isna()
            | frame["total_users"].isna()
            | frame["active_users"].le(frame["total_users"])
        )
    ),
    unique=["subscription_id", "usage_month"],
    strict=True,
    coerce=False,
    add_missing_columns=True,
)
