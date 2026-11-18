"""Verify explicit usage and historical snapshot boundaries."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from nowa_customer_intelligence.data.synthetic.billing import BillingFrequency
from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode
from nowa_customer_intelligence.data.synthetic.observations import (
    ObservationError,
    SnapshotRecord,
    UsageRecord,
    validate_snapshots,
    validate_usage,
)

_ID = "aaaaaaaa-1234-4234-8234-123456789abc"
_DAY = date(2024, 2, 1)
_CUTOFF = date(2024, 4, 1)
_AT = datetime(2024, 2, 1, 12, tzinfo=UTC)
_EPISODE = SubscriptionEpisode(_ID, "customer-1", date(2024, 1, 1), EpisodeStatus.ACTIVE)
_USAGE = UsageRecord(_ID, _DAY, _DAY, date(2024, 2, 29), active_users=3, total_users=4)
_SNAPSHOT = SnapshotRecord(
    _ID,
    _DAY,
    EpisodeStatus.TRIAL,
    _AT,
    _AT,
    _AT,
    _AT,
    "launch",
    BillingFrequency.ANNUAL,
    Decimal("71.10"),
    "GBP",
    True,
)


@pytest.mark.parametrize(
    "changes",
    [
        {"subscription_id": ""},
        {"usage_month": "2024-02-01"},
        {"period_end": date(2024, 1, 31)},
        {"active_users": 5},
        {"active_users": True},
        {"sessions_count": -1},
        {"events_count": 2**63},
        {"usage_volume": Decimal("NaN")},
        {"usage_volume": Decimal("-1")},
        {"usage_volume": 1.5},
        {"usage_metric": " "},
    ],
)
def test_invalid_usage_inputs(changes: dict[str, object]) -> None:
    with pytest.raises(ObservationError):
        replace(_USAGE, **changes)


def test_usage_month_uniqueness_temporal_bounds_and_order() -> None:
    march = replace(_USAGE, usage_month=date(2024, 3, 1), period_end=_CUTOFF)
    assert validate_usage([march, _USAGE], [_EPISODE], cutoff=_CUTOFF) == (_USAGE, march)
    with pytest.raises(ObservationError, match="Duplicate"):
        validate_usage(
            [_USAGE, replace(_USAGE, usage_month=date(2024, 2, 2))], [_EPISODE], cutoff=_CUTOFF
        )
    with pytest.raises(ObservationError, match="exceeds"):
        validate_usage([_USAGE], [replace(_EPISODE, end_date=_DAY)], cutoff=_CUTOFF)
    with pytest.raises(ObservationError, match="exceeds"):
        validate_usage([_USAGE], [_EPISODE], cutoff=_DAY)
    with pytest.raises(ObservationError, match="exceeds"):
        validate_usage([_USAGE], [replace(_EPISODE, start_date=date(2024, 2, 2))], cutoff=_CUTOFF)


@pytest.mark.parametrize(
    "changes",
    [
        {"observed_at": _AT.replace(tzinfo=None)},
        {"snapshot_date": date(2024, 1, 31)},
        {"auto_renew": 1},
        {"subscription_status": "unknown"},
        {"currency": None},
        {"recurring_revenue": Decimal("853.20")},
        {"recurring_revenue": Decimal("Infinity")},
    ],
)
def test_invalid_snapshot_fields(changes: dict[str, object]) -> None:
    with pytest.raises(ObservationError):
        replace(_SNAPSHOT, **changes)


@pytest.mark.parametrize("field", ["occurred_at", "effective_at", "available_at"])
def test_rejects_each_form_of_future_evidence(field: str) -> None:
    with pytest.raises(ObservationError, match="beyond the observation"):
        replace(_SNAPSHOT, **{field: _AT + timedelta(seconds=1)})


def test_snapshot_order_and_historical_status_stay_explicit() -> None:
    earlier = replace(
        _SNAPSHOT,
        snapshot_date=date(2024, 1, 1),
        observed_at=_AT.replace(month=1),
        occurred_at=_AT.replace(month=1),
        effective_at=_AT.replace(month=1),
        available_at=_AT.replace(month=1),
    )
    result = validate_snapshots([_SNAPSHOT, earlier], [_EPISODE], cutoff=_CUTOFF)
    assert result == (earlier, _SNAPSHOT)
    assert result[-1].subscription_status is EpisodeStatus.TRIAL
    with pytest.raises(ObservationError, match="Duplicate"):
        validate_snapshots([earlier, earlier], [_EPISODE], cutoff=_CUTOFF)
    with pytest.raises(ObservationError, match="exceeds"):
        validate_snapshots([_SNAPSHOT], [_EPISODE], cutoff=earlier.snapshot_date)


@pytest.mark.parametrize(
    ("records", "episodes", "cutoff", "message"),
    [
        ([_USAGE], [], _CUTOFF, "Unknown"),
        ([_USAGE], [_EPISODE, _EPISODE], _CUTOFF, "unique"),
        ([_SNAPSHOT], [_EPISODE], _CUTOFF, "typed"),
        ([_USAGE], [_EPISODE], "2024-04-01", "cutoff"),
    ],
)
def test_rejects_missing_or_invalid_context(records, episodes, cutoff, message) -> None:
    with pytest.raises(ObservationError, match=message):
        validate_usage(records, episodes, cutoff=cutoff)


def test_usage_availability_is_optional_but_bounded_if_supplied() -> None:
    supplied = replace(_USAGE, available_at=_AT)
    assert validate_usage([supplied], [_EPISODE], cutoff=_CUTOFF) == (supplied,)
    with pytest.raises(ObservationError, match="timezone-aware"):
        replace(_USAGE, available_at=_AT.replace(tzinfo=None))
    with pytest.raises(ObservationError, match="availability exceeds"):
        validate_usage(
            [replace(_USAGE, available_at=_AT.replace(month=5))], [_EPISODE], cutoff=_CUTOFF
        )


def test_snapshot_body_cannot_precede_episode_start() -> None:
    with pytest.raises(ObservationError, match="evidence precedes"):
        validate_snapshots(
            [replace(_SNAPSHOT, effective_at=_AT.replace(year=2023))], [_EPISODE], cutoff=_CUTOFF
        )
