"""Generate in-memory fictional customer accounts for development."""

from dataclasses import dataclass
from datetime import date, timedelta

from pandas import Timestamp

from nowa_customer_intelligence.data.synthetic.configuration import EffectiveConfiguration
from nowa_customer_intelligence.data.synthetic.random_streams import create_random_stream

CUSTOMER_DATE_STREAM = "customer.created-at"
# The existing customer schema requires UTC nanosecond timestamps after normalisation.
_FIRST_DATE = Timestamp.min.date() + timedelta(days=1)
_LAST_DATE = Timestamp.max.date()


class CustomerGenerationError(ValueError):
    """The effective configuration cannot produce the supported customer records."""


@dataclass(frozen=True, slots=True)
class CustomerRecord:
    """One fictional account, with fields drawn from the customer contract."""

    customer_id: str
    created_at: date
    country: str


def generate_customers(effective: EffectiveConfiguration) -> tuple[CustomerRecord, ...]:
    """Generate ordered accounts with dates sampled across the inclusive history window."""
    if type(effective) is not EffectiveConfiguration:
        raise CustomerGenerationError("Expected a resolved effective configuration.")
    start = date.fromisoformat(effective.history.start_date)
    cutoff = date.fromisoformat(effective.history.cutoff_date)
    if not _FIRST_DATE <= start < cutoff <= _LAST_DATE:
        raise CustomerGenerationError("The history dates are outside the supported customer range.")

    stream = create_random_stream(
        effective.master_seed, CUSTOMER_DATE_STREAM, namespace=effective.scenario_id
    )
    count = effective.population.customer_count
    offsets = stream.integers(0, (cutoff - start).days + 1, size=count)
    return tuple(
        CustomerRecord(
            customer_id=f"synthetic-customer-{ordinal:06d}",
            created_at=start + timedelta(days=int(offset)),
            country="GB",
        )
        for ordinal, offset in enumerate(offsets, start=1)
    )
