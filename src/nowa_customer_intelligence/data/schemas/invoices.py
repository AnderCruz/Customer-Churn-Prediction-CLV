"""Pandera schema for invoice data validation."""

import pandera.pandas as pa

INVOICE_SCHEMA = pa.DataFrameSchema(
    columns={
        "invoice_id": pa.Column(
            str,
            nullable=False,
            unique=True,
            checks=[
                pa.Check(lambda identifiers: identifiers.str.strip().ne("")),
                pa.Check(lambda identifiers: identifiers.eq(identifiers.str.strip())),
            ],
        ),
        "subscription_id": pa.Column(
            str,
            nullable=False,
            checks=[
                pa.Check(lambda identifiers: identifiers.str.strip().ne("")),
                pa.Check(lambda identifiers: identifiers.eq(identifiers.str.strip())),
            ],
        ),
        "invoice_date": pa.Column(pa.DateTime, nullable=False),
        "due_date": pa.Column(pa.DateTime, nullable=True),
        "paid_date": pa.Column(pa.DateTime, nullable=True),
        "amount": pa.Column(
            float,
            nullable=False,
            checks=pa.Check.ge(0),
        ),
        "currency": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.str_matches(r"^[A-Z]{3}$"),
        ),
        "invoice_status": pa.Column(
            str,
            nullable=False,
            checks=pa.Check.isin(["paid", "pending", "overdue", "failed", "void", "refunded"]),
        ),
    },
    checks=[
        pa.Check(
            lambda frame: frame["due_date"].isna() | frame["due_date"].ge(frame["invoice_date"])
        ),
        pa.Check(
            lambda frame: frame["paid_date"].isna() | frame["paid_date"].ge(frame["invoice_date"])
        ),
    ],
    strict=True,
    coerce=False,
    add_missing_columns=True,
)
