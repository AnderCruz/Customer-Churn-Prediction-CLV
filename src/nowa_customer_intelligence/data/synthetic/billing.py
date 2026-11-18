"""Calculate fictional Fieldwise catalogue charges and validate supplied invoice facts."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, localcontext
from enum import StrEnum

from nowa_customer_intelligence.data.synthetic.episodes import SubscriptionEpisode

_PRICES = {
    "launch": Decimal("79.00"),
    "growth": Decimal("249.00"),
    "scale": Decimal("699.00"),
    "enterprise": Decimal("1800.00"),
}
_PENNY = Decimal("0.01")


class BillingValidationError(ValueError):
    """An explicit billing input violates a supported invariant."""


class BillingFrequency(StrEnum):
    """Supported fictional billing frequencies."""

    MONTHLY = "monthly"
    ANNUAL = "annual"


class InvoiceStatus(StrEnum):
    """Controlled invoice categories from Customer Data Contract v1.1."""

    PAID = "paid"
    PENDING = "pending"
    OVERDUE = "overdue"
    FAILED = "failed"
    VOID = "void"
    REFUNDED = "refunded"


@dataclass(frozen=True, slots=True)
class CatalogueCharge:
    """Full invoice amount and monthly-normalised recurring revenue in GBP."""

    invoice_amount: Decimal
    recurring_revenue: Decimal
    currency: str = "GBP"


def calculate_catalogue_charge(plan_id: str, frequency: BillingFrequency) -> CatalogueCharge:
    """Calculate exact penny amounts for the approved fictional catalogue."""
    if type(plan_id) is not str or plan_id not in _PRICES:
        raise BillingValidationError("Expected a supported catalogue plan.")
    if type(frequency) is not BillingFrequency:
        raise BillingValidationError("Expected a supported billing frequency.")
    monthly = _PRICES[plan_id]
    if frequency is BillingFrequency.MONTHLY:
        return CatalogueCharge(monthly, monthly)
    with localcontext(Context(prec=28)):
        annual = (monthly * 12 * Decimal("0.90")).quantize(_PENNY)
        return CatalogueCharge(annual, (annual / 12).quantize(_PENNY))


@dataclass(frozen=True, slots=True)
class InvoiceFact:
    """Explicit GBP invoice data without schedule or payment inference."""

    invoice_id: str
    subscription_id: str
    invoice_date: date
    amount: Decimal
    invoice_status: InvoiceStatus
    due_date: date | None = None
    paid_date: date | None = None
    currency: str = "GBP"

    def __post_init__(self) -> None:
        for identifier in (self.invoice_id, self.subscription_id):
            if type(identifier) is not str or not identifier or identifier.strip() != identifier:
                raise BillingValidationError("Expected a non-empty invoice and subscription ID.")
        if type(self.invoice_date) is not date:
            raise BillingValidationError("Expected an invoice issue date.")
        for boundary in (self.due_date, self.paid_date):
            if boundary is not None and (
                type(boundary) is not date or boundary < self.invoice_date
            ):
                raise BillingValidationError("An invoice date is invalid or precedes issue.")
        if type(self.amount) is not Decimal or not self.amount.is_finite() or self.amount < 0:
            raise BillingValidationError("Expected a finite non-negative Decimal amount.")
        if type(self.invoice_status) is not InvoiceStatus:
            raise BillingValidationError("Expected a supported invoice status.")
        if self.currency != "GBP":
            raise BillingValidationError("Only GBP is supported by the fictional baseline.")


def validate_invoice_relationships(
    episodes: Iterable[SubscriptionEpisode], invoices: Iterable[InvoiceFact]
) -> tuple[InvoiceFact, ...]:
    """Validate explicit ownership and invoice uniqueness, then order by invoice ID."""
    subscriptions: set[str] = set()
    identities: set[str] = set()
    for episode in episodes:
        if (
            type(episode) is not SubscriptionEpisode
            or episode.subscription_id.lower() in identities
        ):
            raise BillingValidationError("Expected unique typed subscription episodes.")
        subscriptions.add(episode.subscription_id)
        identities.add(episode.subscription_id.lower())
    records: dict[str, InvoiceFact] = {}
    for invoice in invoices:
        if type(invoice) is not InvoiceFact:
            raise BillingValidationError("Expected typed invoice facts.")
        if invoice.invoice_id in records:
            raise BillingValidationError("Duplicate invoice identifier.")
        if invoice.subscription_id not in subscriptions:
            raise BillingValidationError("Unknown invoice subscription.")
        records[invoice.invoice_id] = invoice
    return tuple(records[key] for key in sorted(records))
