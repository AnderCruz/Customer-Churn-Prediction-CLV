"""Test explicit episode and establishment invariants."""

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime

import pytest

from nowa_customer_intelligence.data.synthetic.customers import CustomerRecord
from nowa_customer_intelligence.data.synthetic.episodes import (
    EpisodeEvent,
    EpisodeEventType,
    EpisodeStatus,
    EpisodeValidationError,
    SubscriptionEpisode,
    build_episode_population,
)

_DAY = date(2024, 1, 1)
_TIME = datetime(2024, 1, 1, tzinfo=UTC)
_CUSTOMER = CustomerRecord("customer-1", _DAY, "GB")
_ID = "aaaaaaaa-1234-4234-8234-123456789abc"
_LATER_ID = "bbbbbbbb-1234-7234-8234-123456789abc"
_EVENT = EpisodeEvent("event-1", EpisodeEventType.ESTABLISHED, _TIME)
_FIRST = SubscriptionEpisode(_ID, _CUSTOMER.customer_id, _DAY, EpisodeStatus.ACTIVE)


def test_supplied_episodes_are_immutable_and_history_is_preserved() -> None:
    first = replace(
        _FIRST,
        subscription_status=EpisodeStatus.EXPIRED,
        end_date=date(2024, 2, 1),
        establishment=_EVENT,
    )
    second = SubscriptionEpisode(
        _LATER_ID, _CUSTOMER.customer_id, date(2024, 3, 1), EpisodeStatus.ACTIVE
    )
    assert build_episode_population([_CUSTOMER], [second, first]) == (first, second)
    assert build_episode_population([_CUSTOMER], [first, second]) == (first, second)
    assert first.subscription_status is EpisodeStatus.EXPIRED
    assert first.end_date == date(2024, 2, 1)
    with pytest.raises(FrozenInstanceError):
        first.subscription_id = second.subscription_id


@pytest.mark.parametrize(
    "changes",
    [
        {"subscription_id": 42},
        {"subscription_id": "private-sentinel"},
        {"subscription_id": "00000000-0000-0000-0000-000000000000"},
        {"customer_id": " untrimmed"},
        {"subscription_status": "terminated"},
        {"start_date": _TIME},
        {"end_date": date(2023, 12, 31)},
        {"cancellation_date": date(2023, 12, 31)},
        {"establishment": "private-sentinel"},
        {"start_date": date(2024, 1, 2), "establishment": _EVENT},
    ],
)
def test_invalid_episode_fields(changes: dict[str, object]) -> None:
    with pytest.raises(EpisodeValidationError) as caught:
        replace(_FIRST, **changes)
    assert "private-sentinel" not in str(caught.value)


@pytest.mark.parametrize(
    "changes",
    [
        {"event_id": ""},
        {"event_type": "reactivated"},
        {"event_type": "paused"},
        {"occurred_at": None},
        {"effective_at": datetime(2024, 1, 1)},
    ],
)
def test_invalid_event_facts_and_unsupported_transitions(changes: dict[str, object]) -> None:
    with pytest.raises(EpisodeValidationError):
        replace(_EVENT, **changes)


def test_event_keeps_occurrence_effective_and_recorded_times_separate() -> None:
    effective = _TIME.replace(hour=1)
    recorded = _TIME.replace(hour=3)
    event = replace(_EVENT, effective_at=effective, recorded_at=recorded)
    assert (event.occurred_at, event.effective_at, event.recorded_at) == (
        _TIME,
        effective,
        recorded,
    )


@pytest.mark.parametrize(
    ("customers", "episodes"),
    [
        ([], [_FIRST]),
        ([_CUSTOMER, _CUSTOMER], [_FIRST]),
        ([_CUSTOMER], [_FIRST, replace(_FIRST, subscription_id=_ID.upper())]),
        ([_CUSTOMER], [replace(_FIRST, start_date=date(2023, 12, 31))]),
        ([_CUSTOMER], [_FIRST, "private-sentinel"]),
        (
            [_CUSTOMER],
            [
                replace(_FIRST, establishment=_EVENT),
                replace(_FIRST, subscription_id=_LATER_ID, establishment=_EVENT),
            ],
        ),
    ],
)
def test_population_rejects_invalid_relationships(customers: list, episodes: list) -> None:
    with pytest.raises(EpisodeValidationError):
        build_episode_population(customers, episodes)
