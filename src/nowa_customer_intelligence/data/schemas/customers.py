"""Pandera schema for customer data validation."""

import pandas as pd
import pandera.pandas as pa

CUSTOMER_SCHEMA = pa.DataFrameSchema(
    columns={
        "customer_id": pa.Column(
            str,
            nullable=False,
            unique=True,
            checks=[
                pa.Check(lambda identifiers: identifiers.str.strip().ne("")),
                pa.Check(lambda identifiers: identifiers.eq(identifiers.str.strip())),
            ],
        ),
        "created_at": pa.Column(
            pd.DatetimeTZDtype(unit="ns", tz="UTC"),
            nullable=False,
        ),
        "country": pa.Column(
            str,
            nullable=True,
        ),
        "industry": pa.Column(
            str,
            nullable=True,
        ),
        "company_size": pa.Column(
            str,
            nullable=True,
        ),
        "account_status": pa.Column(
            str,
            nullable=True,
        ),
    },
    strict=True,
    coerce=False,
    add_missing_columns=True,
)
