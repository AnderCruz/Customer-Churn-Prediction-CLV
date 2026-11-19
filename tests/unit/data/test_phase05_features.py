"""Exercise as-known feature boundaries without training or splitting."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from nowa_customer_intelligence.data.synthetic.billing import (
    BillingFrequency,
    InvoiceStatus,
    schedule_episode_billing,
)
from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    ChurnExperiment,
    ExperimentEvidenceError,
    ExperimentObservation,
)
from nowa_customer_intelligence.data.synthetic.episodes import EpisodeStatus, SubscriptionEpisode
from nowa_customer_intelligence.data.synthetic.feature_matrix import (
    FEATURE_SPECS,
    extract_feature_row,
)
from nowa_customer_intelligence.data.synthetic.identity_registry import EpisodeIdentity
from nowa_customer_intelligence.data.synthetic.lifecycle import (
    GeneratedEpisode,
    LifecycleFact,
    LifecycleKind,
)
from nowa_customer_intelligence.data.synthetic.observations import SnapshotRecord, UsageRecord

_ID = "aaaaaaaa-1234-4234-8234-123456789abc"
_OTHER = "bbbbbbbb-1234-4234-8234-123456789abc"
_OPEN = datetime(2024, 1, 1, tzinfo=UTC)
_T = datetime(2024, 5, 1, tzinfo=UTC)
_LATER = _T + timedelta(days=1)
_EXPERIMENT = ChurnExperiment(datetime(2024, 8, 1, tzinfo=UTC))


def _episode(identifier: str, opened: datetime, owner: str = "account") -> GeneratedEpisode:
    return GeneratedEpisode(
        EpisodeIdentity("fixture", "phase05", identifier, f"establishment:{identifier}"),
        SubscriptionEpisode(identifier, owner, opened.date(), EpisodeStatus.ACTIVE),
        opened.date(),
        tuple(
            LifecycleFact(identifier, kind, opened, opened, opened)
            for kind in (LifecycleKind.ESTABLISHED, LifecycleKind.ACTIVATED)
        ),
    )


_EPISODE = _episode(_ID, _OPEN)
_SNAPSHOT_AT = _T - timedelta(microseconds=1)
_SNAPSHOT = SnapshotRecord(
    _ID,
    _SNAPSHOT_AT.date(),
    EpisodeStatus.ACTIVE,
    _SNAPSHOT_AT,
    _SNAPSHOT_AT,
    _SNAPSHOT_AT,
    _SNAPSHOT_AT,
    "launch",
    BillingFrequency.MONTHLY,
    Decimal("79.00"),
    "GBP",
)
_CHARGES = schedule_episode_billing(
    _EPISODE.episode,
    paid_activation=_OPEN.date(),
    cutoff=date(2024, 6, 30),
    plan_id="launch",
    frequency=BillingFrequency.MONTHLY,
    subsequent_payment=InvoiceStatus.FAILED,
)
_APRIL = UsageRecord(
    _ID,
    date(2024, 4, 1),
    date(2024, 4, 1),
    date(2024, 4, 30),
    active_users=0,
    sessions_count=5,
    events_count=8,
    available_at=_T,
)
_MARCH = replace(
    _APRIL,
    usage_month=date(2024, 3, 1),
    period_start=date(2024, 3, 1),
    period_end=date(2024, 3, 31),
    active_users=4,
    sessions_count=2,
    events_count=1,
    available_at=datetime(2024, 4, 1, tzinfo=UTC),
)


def _extract(t: datetime = _T, episode: GeneratedEpisode = _EPISODE, **changes):
    args = {
        "history_start": _OPEN.date(),
        "snapshots": (_SNAPSHOT,),
        "usage": (_MARCH, _APRIL),
        "billing": _CHARGES,
    }
    metadata, values = extract_feature_row(
        episode,
        ExperimentObservation(t, t + timedelta(days=30)),
        _EXPERIMENT,
        **(args | changes),
    )
    return metadata, dict(zip((spec.name for spec in FEATURE_SPECS), values, strict=True))


def test_future_and_late_issued_invoices_cannot_backfill_features() -> None:
    future = replace(_CHARGES[-1], invoice=replace(_CHARGES[-1].invoice, amount=Decimal(9000)))
    assert _extract(billing=(*_CHARGES[:-1], future)) == _extract()
    may = _CHARGES[-2]
    late = replace(may, payment_event=replace(may.payment_event, available_at=_LATER))
    assert _extract(billing=(*_CHARGES[:-2], late)) == _extract(billing=_CHARGES[:-2])
    assert _extract(_LATER, billing=(late,))[1]["issued_amount_gbp"] == Decimal("79.00")


def test_future_or_unknown_usage_is_indistinguishable_from_absence_at_cutoff() -> None:
    absent = _extract(usage=(_MARCH,))
    late = replace(_APRIL, available_at=_LATER, active_users=999)
    unknown = replace(_APRIL, available_at=None, active_users=999)
    assert _extract(usage=(_MARCH, late)) == absent
    assert _extract(usage=(_MARCH, unknown)) == absent
    future = replace(
        _APRIL,
        usage_month=date(2024, 5, 1),
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 31),
        available_at=datetime(2024, 6, 1, tzinfo=UTC),
    )
    assert _extract(usage=(_MARCH, _APRIL, future)) == _extract()


def test_future_termination_and_successor_do_not_change_predecessor() -> None:
    terminal = LifecycleFact(_ID, LifecycleKind.TERMINATED, _LATER, _LATER, _LATER)
    retired = replace(
        _EPISODE,
        episode=replace(
            _EPISODE.episode, end_date=_LATER.date(), subscription_status=EpisodeStatus.EXPIRED
        ),
        facts=(*_EPISODE.facts, terminal),
    )
    assert _extract(episode=retired) == _extract()
    successor = replace(_episode(_OTHER, _LATER + timedelta(days=1)), prior_subscription_id=_ID)
    assert _extract(episode=retired, customer_episodes=(retired, successor)) == _extract()


def test_exact_lookback_observation_month_and_availability_boundaries() -> None:
    assert _T - timedelta(days=90) == datetime(2024, 2, 1, tzinfo=UTC)
    _, values = _extract()
    assert values["issued_invoice_count"] == 4  # Includes 1 February and 1 May, excludes 1 January.
    assert values["expected_usage_months"] == 3  # February is whole; May is partial.
    assert values["observed_usage_months"] == 2
    assert values["active_users_change"] == -4
    assert values["sessions_change"] == 3 and values["events_change"] == 7
    _, earlier = _extract(_T - timedelta(microseconds=1))
    assert earlier["issued_invoice_count"] == 3
    assert earlier["observed_usage_months"] == 1
    assert earlier["latest_active_users"] == 4


def test_zero_missing_and_insufficient_trend_have_distinct_values() -> None:
    _, zero = _extract(usage=(_APRIL,), billing=())
    _, absent = _extract(usage=(), billing=())
    assert zero["latest_active_users"] == 0 and zero["zero_active_user_months"] == 1
    assert absent["latest_active_users"] is None and absent["zero_active_user_months"] == 0
    assert absent["usage_coverage_ratio"] == 0 and absent["issued_amount_gbp"] is None
    assert zero["active_users_change"] is None
    incomplete = replace(_APRIL, active_users=None)
    assert _extract(usage=(_MARCH, incomplete))[1]["active_users_change"] is None


def test_prior_count_requires_canonical_ownership_and_as_known_completion() -> None:
    opened = datetime(2023, 1, 1, tzinfo=UTC)
    ended = _OPEN - timedelta(days=1)
    prior = _episode(_OTHER, opened)
    fact = LifecycleFact(_OTHER, LifecycleKind.TERMINATED, ended, ended, _T)
    prior = replace(prior, facts=(*prior.facts, fact))
    assert _extract(customer_episodes=(prior,))[1]["prior_completed_episodes"] == 1
    assert _extract(_SNAPSHOT_AT, customer_episodes=(prior,))[1]["prior_completed_episodes"] == 0
    unrelated = replace(prior, episode=replace(prior.episode, customer_id="unrelated"))
    with pytest.raises(ExperimentEvidenceError, match="ownership"):
        _extract(customer_episodes=(unrelated,))
    with pytest.raises(ExperimentEvidenceError, match="different episode"):
        _extract(usage=(replace(_APRIL, subscription_id=_OTHER),))


def test_duplicate_available_usage_and_invoice_keys_block_extraction() -> None:
    with pytest.raises(ExperimentEvidenceError, match="usage evidence"):
        _extract(usage=(_APRIL, _APRIL))
    with pytest.raises(ExperimentEvidenceError, match="invoice attribution"):
        _extract(billing=(_CHARGES[1], _CHARGES[1]))


def test_future_commercial_state_and_ascertainment_do_not_change_predictors() -> None:
    future = replace(
        _SNAPSHOT,
        plan_id="growth",
        recurring_revenue=Decimal("249.00"),
        snapshot_date=_LATER.date(),
        observed_at=_LATER,
        available_at=_LATER,
    )
    assert _extract(snapshots=(_SNAPSHOT, future)) == _extract()
    assert extract_feature_row(
        _EPISODE,
        ExperimentObservation(_T, _T),
        _EXPERIMENT,
        history_start=_OPEN.date(),
        snapshots=(_SNAPSHOT,),
        usage=(_MARCH, _APRIL),
        billing=_CHARGES,
    )[1] == tuple(_extract()[1].values())
