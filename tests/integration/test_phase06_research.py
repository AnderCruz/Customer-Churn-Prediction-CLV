"""Exercise the research gates and render both notebooks on tiny fictional fixtures."""

import ast
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID

import pytest
from sklearn.pipeline import Pipeline

from nowa_customer_intelligence.data.synthetic.feature_matrix import FEATURE_SPECS, ObservationKey
from nowa_customer_intelligence.models.churn import research
from nowa_customer_intelligence.models.churn.dataset import (
    HOLDOUT_SEED,
    REFERENCE_SEED,
    TRAIN_END,
    VALIDATION_END,
    Bundle,
    ResolvedObservation,
    development_group,
)

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = ROOT / "notebooks/03_churn_modelling"
PATHS = [
    NOTEBOOKS / "05_churn_baseline_models.ipynb",
    NOTEBOOKS / "06_churn_advanced_models.ipynb",
]


def _bundle(*, holdout: bool = False, sparse_validation: bool = False) -> Bundle:
    training_accounts = []
    validation_accounts = []
    for index in range(200):
        customer = f"customer-{index}"
        assigned = (
            training_accounts if development_group(customer) == "training" else validation_accounts
        )
        assigned.append(customer)
    if holdout:
        groups = [(training_accounts[:27], VALIDATION_END, 14)]
    else:
        groups = [
            (training_accounts[:68], TRAIN_END - timedelta(days=50), 32),
            (validation_accounts[:30], TRAIN_END, 8 if sparse_validation else 12),
        ]
    rows = []
    for customers, observed, positives in groups:
        for index, customer in enumerate(customers):
            values = {int: index % 11, float: 0.5, Decimal: Decimal("79.00"), str: "launch"}
            predictors = {
                spec.name: None if spec.nullable and index % 3 == 0 else values[spec.dtype]
                for spec in FEATURE_SPECS
            }
            predictors["billing_frequency"] = "monthly" if index % 2 else "annual"
            predictors["usage_coverage_ratio"] = 0.5 if index % 2 else 2 / 3
            predictors["episode_age_days"] = 110 + 5 * index
            episode = str(UUID(int=(1_000 if holdout else 0) + len(rows) + 1))
            rows.append(
                ResolvedObservation(
                    ObservationKey(episode, observed),
                    customer,
                    observed + timedelta(days=30),
                    observed + timedelta(days=30),
                    int(index < positives),
                    tuple(predictors.values()),
                )
            )
    seed = HOLDOUT_SEED if holdout else REFERENCE_SEED
    return Bundle(
        tuple(rows),
        frozenset(row.key.subscription_id for row in rows),
        seed,
        f"manifest-{seed}",
        f"evidence-{seed}",
        {
            "candidates": len(rows),
            "resolved_eligible": len(rows),
            "prediction_eligible": len(rows),
            "outcomes": {"confirmed_positive": sum(row.target for row in rows)},
            "prediction_exclusions": {},
        },
        {spec.name: (1 if spec.nullable else 0) for spec in FEATURE_SPECS},
        {"50.00%": len(rows)},
    )


def _workspace(directory: Path, monkeypatch: pytest.MonkeyPatch, *, sparse: bool) -> Path:
    directory.mkdir()
    reference = _bundle(sparse_validation=sparse)
    reserve = _bundle(holdout=True)
    design = research.evaluate_design(reference, reserve)
    assert design.audit["confirmation_allowed"] is not sparse
    monkeypatch.setattr(
        research,
        "load_bundle",
        lambda path, *, seed: reserve if seed == HOLDOUT_SEED else reference,
    )
    research._write(directory / "design.json", design.audit)
    return directory


def test_rejects_episode_overlap_across_populations() -> None:
    reference = _bundle()
    reserve = replace(_bundle(holdout=True), episodes=reference.episodes)
    with pytest.raises(ValueError, match="not distinct"):
        research.evaluate_design(reference, reserve)


def test_frozen_holdout_scored_once_after_training(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _workspace(tmp_path / "research", monkeypatch, sparse=False)
    fit = Pipeline.fit
    predict = Pipeline.predict_proba
    holdout_predictions = []

    def train(self, x, y, *args, **kwargs):
        assert len(x) == 68
        return fit(self, x, y, *args, **kwargs)

    def score(self, x, *args, **kwargs):
        if len(x) == 27:
            assert (workspace / "frozen.json").is_file()
            holdout_predictions.append(len(x))
        return predict(self, x, *args, **kwargs)

    monkeypatch.setattr(Pipeline, "fit", train)
    monkeypatch.setattr(Pipeline, "predict_proba", score)
    report = research._run(tmp_path / "reference", workspace)
    assert report["holdout"]["metrics"]["rows"] == 27
    assert holdout_predictions == [27]
    with pytest.raises(FileExistsError):
        research._run(tmp_path / "reference", workspace)
    assert holdout_predictions == [27]


@pytest.fixture(scope="module")
def rendered_results(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("phase06-fixture")
    with pytest.MonkeyPatch.context() as patch:
        workspace = _workspace(root / "research", patch, sparse=True)
        predict = Pipeline.predict_proba

        def no_holdout(self, x, *args, **kwargs):
            assert len(x) != 27
            return predict(self, x, *args, **kwargs)

        patch.setattr(Pipeline, "predict_proba", no_holdout)
        first = research._run(root / "reference", workspace)
        second_path = _workspace(root / "repeat", patch, sparse=True)
        second = research._run(root / "reference", second_path)
        for key in ("candidates", "selected", "validation_intervals", "validation_cohorts"):
            assert first[key] == second[key]
        assert first["holdout"] is None
        assert first["design"]["confirmation_support_failures"] == ["validation"]
    return workspace / "results"


def test_verified_reports_reject_tampering(rendered_results: Path, tmp_path: Path) -> None:
    for path in rendered_results.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    (tmp_path / "baseline.json").write_text("{}")
    with pytest.raises(ValueError, match="integrity failed"):
        research.load_reports(tmp_path)


@pytest.mark.parametrize("path", PATHS)
def test_phase06_notebook_executes_without_fitting(
    path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rendered_results: Path
) -> None:
    nbformat = pytest.importorskip("nbformat")
    nbclient = pytest.importorskip("nbclient")
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    monkeypatch.setenv("NCI_CHURN_RESULTS", str(rendered_results))
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path))
    for cell in notebook.cells:
        if cell.cell_type != "code":
            continue
        assert not cell.outputs and cell.execution_count is None
        assert not {
            node.attr
            for node in ast.walk(ast.parse(cell.source))
            if isinstance(node, ast.Attribute)
        } & {"fit", "fit_transform", "predict_proba"}
    runner = nbclient.NotebookClient(
        notebook,
        kernel_name="python3",
        timeout=60,
        resources={"metadata": {"path": str(NOTEBOOKS)}},
    )
    executed = runner.execute()
    assert any(
        "image/png" in output.get("data", {})
        for cell in executed.cells
        if cell.cell_type == "code"
        for output in cell.outputs
    )
    assert all(
        cell.execution_count is not None for cell in executed.cells if cell.cell_type == "code"
    )
