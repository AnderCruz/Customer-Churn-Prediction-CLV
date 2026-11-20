"""Verify the Batch 09 pre-Phase 06 experimental technical spike."""

import json
from collections import Counter
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sklearn.pipeline import Pipeline

from nowa_customer_intelligence.data.synthetic.billing import InvoiceStatus
from nowa_customer_intelligence.data.synthetic.churn_baseline import (
    evaluate_first_churn_baselines,
    evaluate_model_dataset,
)
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
from nowa_customer_intelligence.data.synthetic.modelling_dataset import (
    ObservationCandidate,
    SimulationFollowUp,
    SplitBoundaries,
    build_modelling_dataset,
    split_modelling_dataset,
)
from nowa_customer_intelligence.data.synthetic.observations import UsageAssumptions
from nowa_customer_intelligence.data.synthetic.provenance import (
    GateStatus,
    run_development_with_provenance,
)

_SCENARIO = b"""
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


def test_first_classical_baselines_use_train_only_fit_and_one_test_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    effective = resolve_configuration(load_configuration(_SCENARIO), "baseline")
    extract = datetime(2024, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)
    directory = tmp_path / "export"
    directory.mkdir()
    request = DevelopmentGenerationRequest(
        effective,
        DevelopmentScenario(
            1200, "launch", 25, InvoiceStatus.FAILED, UsageAssumptions(2, 20, 60, 300)
        ),
        tmp_path / "registry.sqlite",
        "synthetic",
        "batch09-integration",
        extract,
        directory,
    )
    run = run_development_with_provenance(request)
    experiment = ChurnExperiment(extract)
    candidates = tuple(
        ObservationCandidate(
            row.subscription_id,
            ExperimentObservation(
                row.observed_at,
                min(row.observed_at + timedelta(days=experiment.horizon_days), extract),
            ),
        )
        for row in run.population.snapshots
    )
    ledger = SimulationFollowUp("fixture-authority:exhaustive-fieldwise-event-ledger", extract)
    data = build_modelling_dataset(
        run, directory, experiment, candidates, simulation_follow_up=ledger
    )
    replay = build_modelling_dataset(
        run, directory, experiment, reversed(candidates), simulation_follow_up=ledger
    )
    assert len(data.labelled) == 14363
    selected = SplitBoundaries(
        datetime(2023, 4, 1, tzinfo=UTC),
        datetime(2023, 9, 1, tzinfo=UTC),
        datetime(2024, 4, 1, tzinfo=UTC),
    )
    recorded = replace(
        selected,
        training_end=datetime(2022, 7, 1, tzinfo=UTC),
        validation_end=datetime(2023, 7, 1, tzinfo=UTC),
    )

    positives = [row for row in data.labelled if row.outcome.binary_target == 1]
    assert len(positives) == len({row.subscription_id for row in positives}) == 151
    assert min(row.observed_at for row in positives).date().isoformat() == "2022-09-30"

    alternatives = (
        (recorded, (0, 40, 27), (966, 7590)),
        (replace(recorded, customer_disjoint=True), (0, 40, 27), (966, 8215)),
        (
            replace(recorded, training_end=datetime(2023, 1, 1, tzinfo=UTC)),
            (40, 5, 27),
            (1085, 6568),
        ),
        (selected, (66, 10, 19), (1248, 5754)),
        (
            replace(
                selected,
                training_end=datetime(2023, 5, 1, tzinfo=UTC),
                validation_end=datetime(2023, 10, 1, tzinfo=UTC),
            ),
            (76, 20, 16),
            (1302, 5450),
        ),
        (
            replace(
                selected,
                training_end=datetime(2023, 7, 1, tzinfo=UTC),
                validation_end=datetime(2023, 11, 1, tzinfo=UTC),
            ),
            (99, 11, 5),
            (1373, 4559),
        ),
    )
    for boundaries, expected_support, (horizon_excluded, group_excluded) in alternatives:
        candidate = split_modelling_dataset(data, boundaries)
        acceptance = evaluate_model_dataset(
            data, candidate, experiment, boundaries, reconstructed=replay
        )
        assert tuple(row.positive_episodes for row in acceptance.support) == expected_support
        assert Counter(row.reason for row in candidate.excluded) == {
            "outcome_horizon_crosses_boundary": horizon_excluded,
            "group_assigned_to_earlier_partition": group_excluded,
        }
        statuses = {gate.gate: gate.status for gate in acceptance.gates}
        for gate in (
            "split_accounting",
            "chronological_ordering",
            "label_maturity",
            "episode_disjointness",
        ):
            assert statuses[gate] is GateStatus.PASSED
        if boundaries.customer_disjoint:
            assert statuses["customer_disjointness"] is GateStatus.PASSED

    calls: list[tuple[str, int]] = []
    original_fit = Pipeline.fit
    original_predict = Pipeline.predict_proba

    def fit_spy(self, X, y=None, **kwargs):
        if "classifier" in self.named_steps:
            assert not set(X.columns) & {
                "subscription_id",
                "customer_id",
                "observed_at",
                "outcome",
                "label",
            }
            calls.append(("fit", len(X)))
        return original_fit(self, X, y, **kwargs)

    def predict_spy(self, X, **kwargs):
        if "classifier" in self.named_steps:
            calls.append(("score", len(X)))
        return original_predict(self, X, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", fit_spy)
    monkeypatch.setattr(Pipeline, "predict_proba", predict_spy)
    with pytest.raises(ExperimentEvidenceError, match="both_classes_in_each_partition"):
        evaluate_first_churn_baselines(data, experiment, recorded, reconstructed=replay)
    with pytest.raises(ExperimentEvidenceError, match="deterministic_reconstruction"):
        evaluate_first_churn_baselines(data, experiment, selected)
    assert calls == []

    split = split_modelling_dataset(data, selected)
    missing = replace(split, test=split.test[:-1])
    rejected = evaluate_model_dataset(data, missing, experiment, selected, reconstructed=replay)
    assert not rejected.accepted
    assert {gate.gate: gate.status for gate in rejected.gates}[
        "split_accounting"
    ] is GateStatus.FAILED

    result = evaluate_first_churn_baselines(data, experiment, selected, reconstructed=replay)
    counts = [row.positive_episodes for row in result.acceptance.support]
    assert counts == [66, 10, 19]
    assert result.acceptance.accepted
    assert calls == [("fit", len(split.training)), ("score", len(split.validation))] * 3 + [
        ("score", len(split.test))
    ]
    assert {row.model for row in result.validation} == {
        "dummy_prior",
        "logistic_unweighted",
        "logistic_balanced",
    }
    selected_metrics = result.selected.metrics
    assert selected_metrics.average_precision == max(
        row.metrics.average_precision for row in result.validation
    )
    print(json.dumps(asdict(result)))
