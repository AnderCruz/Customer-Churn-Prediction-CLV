"""Calculate fictional Fieldwise catalogue charges and validate supplied invoice facts."""

from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
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


@dataclass(frozen=True, slots=True)
class PlanChange:
    """A caller-supplied request to apply a catalogue plan at the next boundary."""

    requested_on: date
    plan_id: str


@dataclass(frozen=True, slots=True)
class PaymentEvent:
    """Internal fictional payment fact, separate from contract projection."""

    invoice_id: str
    status: InvoiceStatus
    occurred_at: datetime
    effective_at: datetime
    available_at: datetime


@dataclass(frozen=True, slots=True)
class ScheduledCharge:
    """An invoice and its internal, half-open service period."""

    invoice: InvoiceFact
    period_end: date
    plan_id: str
    frequency: BillingFrequency
    recurring_revenue: Decimal
    payment_event: PaymentEvent


def billing_anniversary(anchor: date, period: int, frequency: BillingFrequency) -> date:
    """Return an anniversary, clamping from the original anchor in short months."""
    if type(period) is not int or period < 0 or type(anchor) is not date:
        raise BillingValidationError("Expected a date anchor and non-negative period number.")
    if type(frequency) is not BillingFrequency:
        raise BillingValidationError("Expected a supported billing frequency.")
    months = period * (12 if frequency is BillingFrequency.ANNUAL else 1)
    year, month = divmod(anchor.year * 12 + anchor.month - 1 + months, 12)
    if year > date.max.year:
        raise BillingValidationError("The billing anniversary exceeds the supported date range.")
    return date(year, month + 1, min(anchor.day, monthrange(year, month + 1)[1]))


def schedule_episode_billing(
    episode: SubscriptionEpisode,
    *,
    paid_activation: date,
    cutoff: date,
    plan_id: str,
    frequency: BillingFrequency,
    subsequent_payment: InvoiceStatus,
    plan_changes: tuple[PlanChange, ...] = (),
) -> tuple[ScheduledCharge, ...]:
    """Build advance invoices from supplied fictional activation and payment facts.

    The activation charge is paid. Subsequent payment states are explicit scenario
    inputs; failed charges do not affect episode status.
    """
    if (
        type(episode) is not SubscriptionEpisode
        or type(paid_activation) is not date
        or type(cutoff) is not date
        or not episode.start_date <= paid_activation <= cutoff
        or (episode.end_date is not None and paid_activation >= episode.end_date)
    ):
        raise BillingValidationError("Paid activation falls outside the supported episode period.")
    if type(subsequent_payment) is not InvoiceStatus or subsequent_payment not in (
        InvoiceStatus.PAID,
        InvoiceStatus.PENDING,
        InvoiceStatus.FAILED,
    ):
        raise BillingValidationError("Expected a supported explicit payment state.")
    if type(plan_changes) is not tuple or any(
        type(change) is not PlanChange
        or type(change.requested_on) is not date
        or change.requested_on < paid_activation
        or change.requested_on > cutoff
        or (episode.end_date is not None and change.requested_on >= episode.end_date)
        for change in plan_changes
    ):
        raise BillingValidationError("A supplied plan change is outside the supported episode.")
    ordered_changes = sorted(plan_changes, key=lambda change: change.requested_on)
    if len({change.requested_on for change in ordered_changes}) != len(ordered_changes):
        raise BillingValidationError("Conflicting plan changes share a request date.")
    amounts = calculate_catalogue_charge(plan_id, frequency)
    for change in ordered_changes:
        calculate_catalogue_charge(change.plan_id, frequency)

    charges = []
    period = change_index = 0
    start = paid_activation
    while start <= cutoff and (episode.end_date is None or start < episode.end_date):
        while (
            change_index < len(ordered_changes)
            and ordered_changes[change_index].requested_on < start
        ):
            plan_id = ordered_changes[change_index].plan_id
            amounts = calculate_catalogue_charge(plan_id, frequency)
            change_index += 1
        next_start = billing_anniversary(paid_activation, period + 1, frequency)
        status = InvoiceStatus.PAID if period == 0 else subsequent_payment
        invoice = InvoiceFact(
            f"fixture-invoice:{episode.subscription_id}:{start.isoformat()}",
            episode.subscription_id,
            start,
            amounts.invoice_amount,
            status,
            paid_date=start if status is InvoiceStatus.PAID else None,
        )
        end = min(next_start, episode.end_date) if episode.end_date is not None else next_start
        at = datetime.combine(start, time.min, tzinfo=UTC)
        event = PaymentEvent(invoice.invoice_id, status, at, at, at)
        charges.append(
            ScheduledCharge(invoice, end, plan_id, frequency, amounts.recurring_revenue, event)
        )
        period += 1
        start = next_start
    return tuple(charges)
