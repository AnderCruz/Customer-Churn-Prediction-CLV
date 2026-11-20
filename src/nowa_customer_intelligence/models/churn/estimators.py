"""Fit and evaluate the fixed Phase 06 model menu on development data."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import MissingIndicator, SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ...data.synthetic.feature_matrix import FEATURE_SPECS
from .dataset import ResolvedObservation, model_inputs

MODEL_SEED = 42
BASELINES = ("Dummy prior", "Logistic L2", "Logistic L2 balanced")
ADVANCED = (
    "Random Forest depth 4",
    "Random Forest depth 8",
    "Gradient Boosting 7 leaves",
    "Gradient Boosting 15 leaves balanced",
)
NUMERIC = [spec.name for spec in FEATURE_SPECS if spec.dtype is not str]
CATEGORICAL = [spec.name for spec in FEATURE_SPECS if spec.dtype is str]
NULLABLE = [spec.name for spec in FEATURE_SPECS if spec.nullable]


def build_pipeline(name: str) -> Pipeline:
    """Build a fresh train-only pipeline for a declared candidate."""
    models = {
        BASELINES[0]: DummyClassifier(strategy="prior"),
        BASELINES[1]: LogisticRegression(C=1, max_iter=1000, random_state=MODEL_SEED),
        BASELINES[2]: LogisticRegression(
            C=1, max_iter=1000, random_state=MODEL_SEED, class_weight="balanced"
        ),
    }
    forest = dict(
        n_estimators=120,
        min_samples_leaf=20,
        class_weight="balanced_subsample",
        random_state=MODEL_SEED,
        n_jobs=1,
    )
    models[ADVANCED[0]] = RandomForestClassifier(max_depth=4, **forest)
    models[ADVANCED[1]] = RandomForestClassifier(max_depth=8, **forest)
    boosting = dict(
        max_iter=100,
        min_samples_leaf=30,
        learning_rate=0.05,
        l2_regularization=1,
        early_stopping=False,
        random_state=MODEL_SEED,
    )
    models[ADVANCED[2]] = HistGradientBoostingClassifier(max_leaf_nodes=7, **boosting)
    models[ADVANCED[3]] = HistGradientBoostingClassifier(
        max_leaf_nodes=15, class_weight="balanced", **boosting
    )
    numeric_steps = [("median", SimpleImputer(strategy="median", keep_empty_features=True))]
    if name in BASELINES[1:]:
        numeric_steps.append(("scale", StandardScaler()))
    preprocessing = ColumnTransformer(
        [
            ("numeric", Pipeline(numeric_steps), NUMERIC),
            ("missing", MissingIndicator(features="all"), NULLABLE),
            ("category", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
        ]
    )
    steps = [("preprocessing", preprocessing)]
    if name != BASELINES[0]:
        steps.append(("constant_filter", VarianceThreshold()))
    return Pipeline([*steps, ("model", models[name])])


def churn_scores(pipeline: Pipeline, predictors: pd.DataFrame) -> np.ndarray:
    """Return the probability of confirmed churn (class 1) in input row order."""
    classes = np.asarray(pipeline.classes_)
    if classes.shape != (2,) or set(classes) != {0, 1}:
        raise ValueError("Expected a fitted classifier with binary churn classes 0 and 1.")
    positive_column = int(np.flatnonzero(classes == 1)[0])
    return pipeline.predict_proba(predictors)[:, positive_column]


def metrics(target: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    """Summarise row-level performance, with undefined rank metrics as missing."""
    tn, fp, fn, tp = map(int, confusion_matrix(target, scores >= threshold, labels=[0, 1]).ravel())
    both_classes = len(np.unique(target)) == 2
    return {
        "rows": len(target),
        "positives": tp + fn,
        "prevalence": float(target.mean()),
        "average_precision": float(average_precision_score(target, scores))
        if both_classes
        else None,
        "roc_auc": float(roc_auc_score(target, scores)) if both_classes else None,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0,
        "brier": float(brier_score_loss(target, scores)),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
    }


def threshold_sweep(target: np.ndarray, scores: np.ndarray) -> list[dict]:
    """Use each distinct validation score and the all-negative decision."""
    precision, recall, thresholds = precision_recall_curve(target, scores)
    points = []
    for p, r, threshold in zip(precision[:-1], recall[:-1], thresholds, strict=True):
        points.append(
            {
                "threshold": float(threshold),
                "precision": float(p),
                "recall": float(r),
                "f1": float(2 * p * r / (p + r)) if p + r else 0.0,
            }
        )
    points.append(
        {
            "threshold": float(np.nextafter(scores.max(), np.inf)),
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
        }
    )
    return points


def select_threshold(points: list[dict]) -> float:
    """Maximise validation F1 and favour the higher threshold within a tie."""
    best = max(point["f1"] for point in points)
    return max(point["threshold"] for point in points if point["f1"] >= best - 1e-12)


def select_candidate(results: list[dict]) -> str:
    """Choose validation AP, with candidate order as the simplicity tie-break."""
    best = max(result["validation"]["average_precision"] for result in results)
    return next(
        result["name"]
        for result in results
        if result["validation"]["average_precision"] >= best - 1e-12
    )


def _calibration(target: np.ndarray, scores: np.ndarray) -> list[dict]:
    edges = np.array([0, 0.01, 0.05, 0.15, 0.35, 1])
    groups = np.searchsorted(edges[1:-1], scores, side="right")
    return [
        {
            "bin": f"{left:.0%}–{right:.0%}",
            "count": int(mask.sum()),
            "positives": int(target[mask].sum()),
            "mean_score": float(scores[mask].mean()) if mask.any() else None,
            "observed_rate": float(target[mask].mean()) if mask.any() else None,
        }
        for index, (left, right) in enumerate(zip(edges[:-1], edges[1:], strict=True))
        for mask in [groups == index]
    ]


def diagnostics(target: np.ndarray, scores: np.ndarray) -> dict:
    """Summarise ranking curves and reliability on a population with both classes."""
    precision, recall, _ = precision_recall_curve(target, scores)
    false_positive, true_positive, _ = roc_curve(target, scores)
    return {
        "pr": {"recall": recall.tolist(), "precision": precision.tolist()},
        "roc": {
            "false_positive_rate": false_positive.tolist(),
            "true_positive_rate": true_positive.tolist(),
        },
        "calibration": _calibration(target, scores),
    }


def cohort_errors(
    rows: tuple[ResolvedObservation, ...], scores: np.ndarray, threshold: float
) -> list[dict]:
    """Reconcile cohort error counts with visible class and account support."""
    features = model_inputs(rows)
    cohorts = pd.DataFrame(
        {
            "quarter": [
                f"{r.key.observed_at.year}-Q{(r.key.observed_at.month - 1) // 3 + 1}" for r in rows
            ],
            "episode_age": pd.cut(
                features["episode_age_days"],
                [0, 180, 365, np.inf],
                right=False,
                labels=["Under 180 days", "180–364 days", "365 days or more"],
            ),
            "billing_frequency": features["billing_frequency"],
            "usage_coverage": pd.cut(
                features["usage_coverage_ratio"],
                [-0.01, 0.5, 1],
                labels=["Up to 50%", "Above 50%"],
            )
            .astype(object)
            .fillna("Unavailable"),
        }
    )
    target = np.array([row.target for row in rows])
    report = []
    for field in cohorts:
        for key, indexes in cohorts.groupby(field, observed=True, sort=True).indices.items():
            positive_accounts = len({rows[i].customer for i in indexes if target[i]})
            actual = target[indexes] == 1
            flagged = scores[indexes] >= threshold
            report.append(
                {
                    "cohort": field,
                    "level": str(key),
                    "rows": len(indexes),
                    "positive_accounts": positive_accounts,
                    "positives": int(actual.sum()),
                    "tp": int((flagged & actual).sum()),
                    "fp": int((flagged & ~actual).sum()),
                    "fn": int((~flagged & actual).sum()),
                    "recall": float(flagged[actual].mean()) if positive_accounts >= 10 else None,
                }
            )
    return report


def account_intervals(
    rows: tuple[ResolvedObservation, ...], scores: np.ndarray, threshold: float
) -> dict:
    """Resample whole accounts with replacement and record usable draws."""
    groups = defaultdict(list)
    for index, row in enumerate(rows):
        groups[row.customer].append(index)
    members = list(groups.values())
    target = np.array([row.target for row in rows])
    rng = np.random.default_rng(MODEL_SEED)
    estimates: dict[str, list[float]] = {"average_precision": [], "recall": []}
    for _ in range(400):
        draw = rng.integers(0, len(members), size=len(members))
        indexes = np.concatenate([members[i] for i in draw])
        actual = target[indexes]
        positive = actual == 1
        if not positive.any() or positive.all():
            continue
        predicted = scores[indexes]
        estimates["average_precision"].append(float(average_precision_score(actual, predicted)))
        estimates["recall"].append(float((predicted[positive] >= threshold).mean()))
    return {
        name: {"draws": len(values), "interval_95": np.percentile(values, [2.5, 97.5]).tolist()}
        if values
        else {"draws": 0, "interval_95": None}
        for name, values in estimates.items()
    }


@dataclass(slots=True)
class FittedCandidate:
    """Keep the frozen fitted pipeline and validation-only evidence together."""

    pipeline: Pipeline
    report: dict[str, Any]
    validation_scores: np.ndarray


def fit_candidates(
    names: tuple[str, ...],
    training: tuple[ResolvedObservation, ...],
    validation: tuple[ResolvedObservation, ...],
) -> dict[str, FittedCandidate]:
    """Fit on the training partition and evaluate the same validation rows."""
    train_x, validation_x = model_inputs(training), model_inputs(validation)
    train_y = np.array([row.target for row in training])
    validation_y = np.array([row.target for row in validation])
    fitted = {}
    for name in names:
        pipeline = build_pipeline(name)
        pipeline.fit(train_x, train_y)
        train_scores = churn_scores(pipeline, train_x)
        scores = churn_scores(pipeline, validation_x)
        sweep = threshold_sweep(validation_y, scores)
        threshold = select_threshold(sweep)
        report = {
            "name": name,
            "parameters": pipeline.named_steps["model"].get_params(),
            "threshold": threshold,
            "training": metrics(train_y, train_scores, threshold),
            "validation": metrics(validation_y, scores, threshold),
            "threshold_sweep": sweep,
            **diagnostics(validation_y, scores),
        }
        fitted[name] = FittedCandidate(pipeline, report, scores)
    return fitted
