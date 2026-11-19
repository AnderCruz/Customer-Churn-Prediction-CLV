"""Verify the reference matrix, isolated exports and unmodified acquisition inputs."""

from collections import Counter
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from json import loads
from pathlib import Path

import pytest

from nowa_customer_intelligence.data.eda_inputs import (
    REFERENCE_CUTOFF,
    fieldwise_reference,
    reference_candidates,
    reference_follow_up,
)
from nowa_customer_intelligence.data.synthetic.churn_experiment import (
    ChurnExperiment,
    ExperimentEvidenceError,
    ExperimentObservation,
    IneligibilityReason,
)
from nowa_customer_intelligence.data.synthetic.feature_exports import write_feature_bundle
from nowa_customer_intelligence.data.synthetic.feature_matrix import (
    FEATURE_SPECS,
    assess_feature_quality,
    build_feature_matrix,
)
from nowa_customer_intelligence.data.synthetic.ground_truth import OutcomeState
from nowa_customer_intelligence.data.synthetic.lifecycle import LifecycleKind
from nowa_customer_intelligence.data.synthetic.modelling_dataset import ObservationCandidate


def test_reference_feature_bundles_are_deterministic_and_source_is_immutable(
    tmp_path: Path,
) -> None:
    experiment = ChurnExperiment(REFERENCE_CUTOFF)
    follow_up = reference_follow_up()
    with fieldwise_reference() as (run, source):
        original = {path.name: sha256(path.read_bytes()).hexdigest() for path in source.iterdir()}
        candidates = tuple(reference_candidates(run, experiment))
        matrix = build_feature_matrix(
            run, source, experiment, candidates, simulation_follow_up=follow_up
        )
        reversed_matrix = build_feature_matrix(
            run, source, experiment, reversed(candidates), simulation_follow_up=follow_up
        )
        assert len(matrix.inputs) == 5 and len(candidates) == 18661
        assert matrix == reversed_matrix
        first, second = tmp_path / "first", tmp_path / "second"
        report = write_feature_bundle(matrix, first)
        write_feature_bundle(reversed_matrix, second)
        assert report["input_observations"] == 18661 and report["rows"] == 15258
        assert report["features"] == 25 and report["duplicate_keys"] == 0
        assert report["prediction_exclusions"] == {"insufficient_observation_history": 3403}
        assert report["retrospective_training_rows"] == 14363
        assert report["outcomes"] == {
            "confirmed_positive": 151,
            "confirmed_negative": 14212,
            "right_censored": 895,
            "ineligible": 3403,
        }
        for path in first.iterdir():
            assert path.read_bytes() == (second / path.name).read_bytes()
        manifest = loads((first / "manifest.json").read_text())
        assert {entry["sha256_hex"] for entry in manifest["inputs"]} == set(original.values())
        assert all(
            sha256((first / name).read_bytes()).hexdigest() == evidence["sha256"]
            for name, evidence in manifest["files"].items()
        )
        with (first / "predictors.jsonl").open() as predictions:
            assert all(
                tuple(loads(line)) == tuple(spec.name for spec in FEATURE_SPECS)
                for line in predictions
            )
        assert not set(manifest["predictor_columns"]) & {
            "binary_target",
            "observed_at",
            "customer_id",
            "subscription_id",
            "outcome",
            "horizon_end",
            "ascertainment_cutoff",
            "source_ref",
        }
        with (first / "outcomes.jsonl").open() as outcomes:
            assert sum(loads(line)["binary_target"] == 1 for line in outcomes) == 151
        assert matrix.outcomes is not None
        prediction_keys = {row.key for row in matrix.observations}
        censored = [
            row for row in matrix.outcomes if row.outcome.state is OutcomeState.RIGHT_CENSORED
        ]
        assert len(censored) == 895
        assert all(
            row.key in prediction_keys and not row.retrospective_training_eligible
            for row in censored
        )
        indexes = {spec.name: i for i, spec in enumerate(FEATURE_SPECS)}
        usage_pairs = Counter(
            (row[indexes["expected_usage_months"]], row[indexes["observed_usage_months"]])
            for row in matrix.predictors
        )
        assert usage_pairs == {(2, 1): 12836, (3, 2): 2422}
        for name in ("active_users_change", "sessions_change", "events_change"):
            assert all(
                (row[indexes[name]] is None) == (row[indexes["observed_usage_months"]] < 2)
                for row in matrix.predictors
            )
        with pytest.raises(ExperimentEvidenceError, match="already exists"):
            write_feature_bundle(matrix, first)
        with pytest.raises(ExperimentEvidenceError, match="alignment"):
            assess_feature_quality(
                replace(
                    matrix,
                    observations=(
                        matrix.observations[0],
                        *matrix.observations,
                    ),
                )
            )
        broken = list(matrix.predictors[0])
        broken[0] = float("inf")
        with pytest.raises(ExperimentEvidenceError, match="Invalid feature value"):
            assess_feature_quality(
                replace(
                    matrix,
                    predictors=(
                        tuple(broken),
                        *matrix.predictors[1:],
                    ),
                )
            )
        assert original == {
            path.name: sha256(path.read_bytes()).hexdigest() for path in source.iterdir()
        }
        path = source / "customers.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        with pytest.raises(ExperimentEvidenceError, match="acceptance evidence"):
            build_feature_matrix(
                run, source, experiment, candidates, simulation_follow_up=follow_up
            )


def test_late_termination_changes_adjudication_without_changing_prediction_roster(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    experiment = ChurnExperiment(REFERENCE_CUTOFF)
    with fieldwise_reference() as (run, source):
        chosen, termination = next(
            (episode, fact)
            for episode in run.population.episodes
            for fact in episode.facts
            if fact.kind is LifecycleKind.TERMINATED
            and (fact.effective_at.date() - episode.paid_activation).days > 120
            and fact.effective_at + timedelta(days=1) < REFERENCE_CUTOFF
        )
        t = termination.effective_at
        late = replace(termination, available_at=t + timedelta(days=1))
        amended = replace(chosen, facts=(*chosen.facts[:-1], late))
        replay = replace(
            run,
            population=replace(
                run.population,
                episodes=tuple(
                    amended if row == chosen else row for row in run.population.episodes
                ),
            ),
        )
        identifier = chosen.episode.subscription_id
        at_observation = ObservationCandidate(identifier, ExperimentObservation(t, t))
        after_recording = replace(
            at_observation, window=ExperimentObservation(t, late.available_at)
        )
        early = build_feature_matrix(replay, source, experiment, (at_observation,))
        later = build_feature_matrix(replay, source, experiment, (after_recording,))
        assert early.eligibility == later.eligibility
        assert early.observations == later.observations
        assert early.predictors == later.predictors
        assert len(later.predictors) == 1
        assert early.outcomes is not None and later.outcomes is not None
        assert early.outcomes[0].outcome.state is OutcomeState.PENDING_ASCERTAINMENT
        assert later.outcomes[0].outcome.reason is IneligibilityReason.NOT_ACTIVE
        assert not later.outcomes[0].retrospective_training_eligible
        known_closed = build_feature_matrix(
            run, source, experiment, (at_observation,), include_outcomes=False
        )
        assert known_closed.eligibility[0].exclusion is IneligibilityReason.NOT_ACTIVE
        assert not known_closed.predictors

        def refuse_adjudication(*args, **kwargs):
            pytest.fail("Inference-only feature generation must not invoke adjudication.")

        monkeypatch.setattr(
            "nowa_customer_intelligence.data.synthetic.feature_matrix.build_modelling_dataset",
            refuse_adjudication,
        )
        unlabelled = build_feature_matrix(
            replay,
            source,
            experiment,
            (at_observation,),
            include_outcomes=False,
        )
        assert unlabelled.outcomes is None
        assert unlabelled.eligibility == later.eligibility
        assert unlabelled.predictors == later.predictors
        without_termination = replace(
            replay,
            population=replace(
                replay.population,
                episodes=tuple(
                    replace(row, facts=row.facts[:-1]) if row == amended else row
                    for row in replay.population.episodes
                ),
            ),
        )
        without_evidence = build_feature_matrix(
            without_termination, source, experiment, (at_observation,), include_outcomes=False
        )
        assert without_evidence.eligibility == unlabelled.eligibility
        assert without_evidence.predictors == unlabelled.predictors
        inference = tmp_path / "inference"
        write_feature_bundle(unlabelled, inference)
        assert not (inference / "outcomes.jsonl").exists()
        assert (inference / "prediction_eligibility.jsonl").is_file()
