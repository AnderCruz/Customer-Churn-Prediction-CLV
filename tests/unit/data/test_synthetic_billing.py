"""Test exact catalogue arithmetic and policy-independent invoice checks."""

from dataclasses import replace
from datetime import date
from decimal import Decimal, localcontext

import pytest

from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    BillingValidationError,
    InvoiceFact,
    InvoiceStatus,
    calculate_catalogue_charge,
    validate_invoice_relationships,
)
from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode

_DAY = date(2024, 1, 1)
_EPISODE = SubscriptionEpisode(
    "aaaaaaaa-1234-4234-8234-123456789abc", "customer-1", _DAY, EpisodeStatus.ACTIVE
)
_INVOICE = InvoiceFact(
    "invoice-1",
    _EPISODE.subscription_id,
    _DAY,
    Decimal("853.20"),
    InvoiceStatus.PAID,
)


@pytest.mark.parametrize(
    ("plan", "monthly", "annual", "normalised"),
    [
        ("launch", "79.00", "853.20", "71.10"),
        ("growth", "249.00", "2689.20", "224.10"),
        ("scale", "699.00", "7549.20", "629.10"),
        ("enterprise", "1800.00", "19440.00", "1620.00"),
    ],
)
def test_catalogue_arithmetic_uses_exact_pennies(
    plan: str, monthly: str, annual: str, normalised: str
) -> None:
    with localcontext() as context:
        context.prec = 2
        monthly_charge = calculate_catalogue_charge(plan, BillingFrequency.MONTHLY)
        annual_charge = calculate_catalogue_charge(plan, BillingFrequency.ANNUAL)
    assert str(monthly_charge.invoice_amount) == str(monthly_charge.recurring_revenue) == monthly
    assert str(annual_charge.invoice_amount) == annual
    assert str(annual_charge.recurring_revenue) == normalised
    assert monthly_charge.currency == annual_charge.currency == "GBP"
    assert annual_charge == calculate_catalogue_charge(plan, BillingFrequency.ANNUAL)


@pytest.mark.parametrize(
    ("plan", "frequency"),
    [
        ("private-sentinel", BillingFrequency.MONTHLY),
        ("launch", "monthly"),
        ([], BillingFrequency.ANNUAL),
    ],
)
def test_rejects_invalid_catalogue_inputs(plan: str, frequency: BillingFrequency) -> None:
    with pytest.raises(BillingValidationError) as caught:
        calculate_catalogue_charge(plan, frequency)
    assert "private-sentinel" not in str(caught.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"invoice_id": ""},
        {"subscription_id": " untrimmed"},
        {"invoice_date": "2024-01-01"},
        {"due_date": date(2023, 12, 31)},
        {"paid_date": date(2023, 12, 31)},
        {"amount": Decimal("-0.01")},
        {"amount": Decimal("NaN")},
        {"amount": Decimal("Infinity")},
        {"amount": 12.5},
        {"currency": "USD"},
        {"invoice_status": "unexpected"},
    ],
)
def test_rejects_invalid_invoice_facts(changes: dict[str, object]) -> None:
    with pytest.raises(BillingValidationError):
        replace(_INVOICE, **changes)


def test_invoice_fields_remain_explicit_and_ordered() -> None:
    second = replace(
        _INVOICE,
        invoice_id="invoice-2",
        invoice_status=InvoiceStatus.PENDING,
        due_date=date(2024, 1, 15),
    )
    assert validate_invoice_relationships([_EPISODE], [second, _INVOICE]) == (_INVOICE, second)
    assert _INVOICE.paid_date is None
    assert second.invoice_status is InvoiceStatus.PENDING
    assert _EPISODE.subscription_status is EpisodeStatus.ACTIVE


@pytest.mark.parametrize(
    ("episodes", "invoices"),
    [
        ([], [_INVOICE]),
        ([_EPISODE], [_INVOICE, _INVOICE]),
        ([_EPISODE], ["invoice-1"]),
        ([_EPISODE, replace(_EPISODE, subscription_id=_EPISODE.subscription_id.upper())], []),
        (["subscription"], [_INVOICE]),
    ],
)
def test_rejects_missing_or_duplicated_invoice_relationships(
    episodes: list, invoices: list
) -> None:
    with pytest.raises(BillingValidationError):
        validate_invoice_relationships(episodes, invoices)
