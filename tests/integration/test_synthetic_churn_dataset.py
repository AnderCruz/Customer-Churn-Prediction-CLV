"""Exercise an accepted fictional export through leakage-controlled dataset preparation."""

import json
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.synthetic.billing import InvoiceStatus
from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    ChurnExperiment,
    ExperimentEvidenceError,
    ExperimentObservation,
)
from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.development import (
    DevelopmentGenerationRequest,
    DevelopmentScenario,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import OutcomeState
from nowa_customer_intelligence.data.synthetic.modelling_dataset import (
    ObservationCandidate,
    SimulationFollowUp,
    SplitBoundaries,
    build_modelling_dataset,
    split_modelling_dataset,
)
from nowa_customer_intelligence.data.synthetic.observations import UsageAssumptions
from nowa_customer_intelligence.data.synthetic.provenance import (
    evaluate_development_acceptance,
    run_development_with_provenance,
)

_DOCUMENT = b"""
config_schema_version: 1
base:
  population: {customer_count: 1000, episode_count_min: 1100, episode_count_max: 1400}
  history: {start_date: '2021-04-01', cutoff_date: '2024-03-31'}
  master_seed: 42
  workflow: TEMPORAL
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv, subscription_snapshots.csv,
                      usage_monthly.csv, invoices.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios: {baseline: {scenario_version: 1}}
"""
_E = datetime(2024, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)


def test_prepares_fieldwise_churn_dataset_without_training_or_contract_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_network(*args: object, **kwargs: object) -> None:
        pytest.fail("Synthetic dataset preparation attempted network access.")

    monkeypatch.setattr("socket.socket", no_network)
    export = tmp_path / "development-csvs"
    export.mkdir()
    effective = resolve_configuration(load_configuration(_DOCUMENT), "baseline")
    request = DevelopmentGenerationRequest(
        effective,
        DevelopmentScenario(
            1200, "launch", 25, InvoiceStatus.FAILED, UsageAssumptions(2, 20, 60, 300)
        ),
        tmp_path / "registry.sqlite",
        "fieldwise-fictional",
        "batch08-test",
        _E,
        export,
    )
    run = run_development_with_provenance(request)
    assert evaluate_development_acceptance(run.provenance, directory=export).accepted
    assert len(run.population.customers) == 1000
    assert len(run.population.episodes) == 1200
    before = {file.name: file.read_bytes() for file in export.iterdir()}

    experiment = ChurnExperiment(_E)
    # The fixture author explicitly attests the exhaustively simulated lifecycle ledger,
    # recorded contemporaneously and complete through extraction for this scenario.
    attestation = SimulationFollowUp("fixture-authority:exhaustive-fieldwise-event-ledger", _E)
    candidates = tuple(
        ObservationCandidate(
            row.subscription_id,
            ExperimentObservation(
                row.observed_at, min(row.observed_at + timedelta(days=experiment.horizon_days), _E)
            ),
        )
        for row in run.population.snapshots
    )
    dataset = build_modelling_dataset(
        run,
        export,
        experiment,
        candidates,
        simulation_follow_up=attestation,
    )
    replay = build_modelling_dataset(
        run,
        export,
        experiment,
        reversed(candidates),
        simulation_follow_up=attestation,
    )
    assert replay == dataset
    assert sum(dataset.counts.values()) == len(candidates) == len(run.population.snapshots)
    for row in dataset.labelled:
        assert row.features.latest_evidence_at <= row.observed_at
        assert row.outcome.binary_target in (0, 1)
        assert row.outcome.source_ref is not None
    assert all(
        row.outcome.binary_target is None
        for row in (*dataset.right_censored, *dataset.pending, *dataset.ineligible)
    )

    bounds = SplitBoundaries(
        datetime(2022, 7, 1, tzinfo=UTC),
        datetime(2023, 7, 1, tzinfo=UTC),
        datetime(2024, 4, 1, tzinfo=UTC),
    )
    splits = split_modelling_dataset(dataset, bounds)
    groups = {}
    statistics = {}
    for name, rows, end in (
        ("training", splits.training, bounds.training_end),
        ("validation", splits.validation, bounds.validation_end),
        ("test", splits.test, bounds.test_end),
    ):
        episodes = {row.subscription_id for row in rows}
        customers = {row.customer_id for row in rows}
        assert episodes.isdisjoint(groups)
        groups.update(dict.fromkeys(episodes, name))
        assert all(
            row.observed_at < row.horizon_end < end and row.ascertainment_cutoff < end
            for row in rows
        )
        statistics[name] = {
            "rows": len(rows),
            "episodes": len(episodes),
            "customers": len(customers),
            "positives": sum(row.outcome.binary_target for row in rows),
        }
    assert sum(row["rows"] for row in statistics.values()) + len(splits.excluded) == len(
        dataset.labelled
    )
    customer_split = split_modelling_dataset(
        dataset, SplitBoundaries(bounds.training_end, bounds.validation_end, bounds.test_end, True)
    )
    train_accounts = {row.customer_id for row in customer_split.training}
    validation_accounts = {row.customer_id for row in customer_split.validation}
    test_accounts = {row.customer_id for row in customer_split.test}
    assert train_accounts.isdisjoint(validation_accounts | test_accounts)
    assert validation_accounts.isdisjoint(test_accounts)
    negative = next(
        row for row in dataset.labelled if row.outcome.state is OutcomeState.CONFIRMED_NEGATIVE
    )
    sampled = ObservationCandidate(
        negative.subscription_id,
        ExperimentObservation(negative.observed_at, negative.ascertainment_cutoff),
    )
    unproven = build_modelling_dataset(run, export, experiment, [sampled])
    assert unproven.pending[0].outcome.reason == "missing_ascertained_follow_up"
    assert unproven.labelled == ()
    with pytest.raises(ExperimentEvidenceError, match="Duplicate modelling"):
        build_modelling_dataset(run, export, experiment, [sampled, sampled])
    assert {file.name: file.read_bytes() for file in export.iterdir()} == before
    assert all(b"binary_target" not in data.splitlines()[0] for data in before.values())
    csv = export / "customers.csv"
    csv.write_bytes(before[csv.name] + b"corrupt")
    with pytest.raises(ExperimentEvidenceError, match="current acceptance"):
        build_modelling_dataset(run, export, experiment, [sampled])
    assert csv.read_bytes().endswith(b"corrupt")

    print(
        json.dumps(
            {
                "candidates": len(candidates),
                "labelled": len(dataset.labelled),
                "outcomes": dataset.counts,
                "classification_reasons": dataset.reasons,
                "partitions": statistics,
                "split_exclusions": Counter(row.reason for row in splits.excluded),
                "customer_disjoint_rows": {
                    "training": len(customer_split.training),
                    "validation": len(customer_split.validation),
                    "test": len(customer_split.test),
                    "excluded": len(customer_split.excluded),
                },
            }
        )
    )
