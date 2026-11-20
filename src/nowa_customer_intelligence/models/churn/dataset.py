"""Validate the Phase 05 export and partition eligible, resolved observations."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from json import loads
from math import isfinite
from pathlib import Path
from uuid import UUID

import pandas as pd

from ...data.synthetic.feature_matrix import (
    FEATURE_BUNDLE_VERSION,
    FEATURE_SPEC_VERSION,
    FEATURE_SPECS,
    ObservationKey,
    Predictor,
)

COLUMNS = tuple(spec.name for spec in FEATURE_SPECS)
TRAIN_END = datetime(2023, 4, 1, tzinfo=UTC)
VALIDATION_END = datetime(2023, 9, 1, tzinfo=UTC)
HOLDOUT_END = datetime(2024, 4, 1, tzinfo=UTC)
EXTRACTION = HOLDOUT_END - timedelta(microseconds=1)
REFERENCE_SEED = 42
HOLDOUT_SEED = 2027
GROUP_SALT = "nci-phase06-v1"
TRAIN_GROUP_PERCENT = 70
MIN_POSITIVE_ACCOUNTS = {"training": 30, "validation": 10, "holdout": 10}
STATES = {
    "confirmed_positive": 1,
    "confirmed_negative": 0,
    "right_censored": None,
    "pending_ascertainment": None,
    "ineligible": None,
}
FILES = ("observations", "predictors", "prediction_eligibility", "outcomes")


@dataclass(frozen=True, slots=True)
class ResolvedObservation:
    """Resolved outcome and separate, ordered point-in-time predictors."""

    key: ObservationKey
    customer: str
    horizon: datetime
    ascertainment: datetime
    target: int
    predictors: tuple[Predictor, ...]


@dataclass(frozen=True, slots=True)
class Bundle:
    """Verified input with counts and provenance for reporting."""

    rows: tuple[ResolvedObservation, ...]
    episodes: frozenset[str]
    seed: int
    manifest_hash: str
    evidence_hash: str
    inventory: dict
    feature_missingness: dict[str, int]
    coverage: dict[str, int]


def _time(value: str) -> datetime:
    instant = datetime.fromisoformat(value)
    if instant.utcoffset() != timedelta(0):
        raise ValueError("Expected an explicit UTC timestamp.")
    return instant


def _key(record: dict) -> ObservationKey:
    value = record["key"]["subscription_id"]
    if str(UUID(value)) != value:
        raise ValueError("Expected a canonical episode UUID.")
    observed = _time(record["key"]["observed_at"])
    if observed > EXTRACTION:
        raise ValueError("Observation exceeds extraction cutoff.")
    return ObservationKey(value, observed)


def _ordered(records: list[dict]) -> list[ObservationKey]:
    keys = [_key(row) for row in records]
    if len(set(keys)) != len(keys) or keys != sorted(
        keys, key=lambda key: (key.observed_at, key.subscription_id)
    ):
        raise ValueError("Duplicate or unordered observation keys.")
    return keys


def _decode(row: dict) -> tuple[Predictor, ...]:
    if tuple(row) != COLUMNS:
        raise ValueError("Predictors must match the ordered Phase 05 registry.")
    decoded = []
    for spec, value in zip(FEATURE_SPECS, row.values(), strict=True):
        if value is None and spec.nullable:
            decoded.append(None)
            continue
        if spec.dtype is Decimal and type(value) is str:
            value = Decimal(value)
        if (
            type(value) is not spec.dtype
            or spec.dtype is str
            and not value
            or spec.dtype is not str
            and (not isfinite(value) or not spec.signed and value < 0)
            or spec.name == "usage_coverage_ratio"
            and value > 1
        ):
            raise ValueError(f"Invalid Phase 05 predictor: {spec.name}.")
        decoded.append(value)
    return tuple(decoded)


def load_bundle(directory: Path, *, seed: int) -> Bundle:
    """Check file integrity, provenance and Phase 05 alignment before modelling."""
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = loads(manifest_bytes)
    configuration = manifest["configuration"]
    seed_reference = sha256(
        b"nowa.synthetic.seed-reference.v1\0" + seed.to_bytes(8, "big")
    ).hexdigest()
    experiment = configuration["experiment"]
    generation = configuration["generation"]
    if (
        manifest["bundle_version"] != FEATURE_BUNDLE_VERSION
        or manifest["feature_spec_version"] != FEATURE_SPEC_VERSION
        or manifest["scope"] != "fieldwise-fictional-development"
        or tuple(manifest["predictor_columns"]) != COLUMNS
        or generation["seed_reference"] != seed_reference
        or (generation["scenario_id"], generation["scenario_version"]) != ("baseline", 1)
        or (experiment["history_days"], experiment["horizon_days"]) != (90, 30)
        or _time(experiment["extraction_cutoff"]) != EXTRACTION
        or set(manifest["files"]) != {f"{name}.jsonl" for name in FILES}
    ):
        raise ValueError("Incompatible Phase 05 bundle provenance or version.")
    ledgers = {}
    for name in FILES:
        filename = f"{name}.jsonl"
        content = (directory / filename).read_bytes()
        file = manifest["files"][filename]
        if (len(content), sha256(content).hexdigest()) != (file["bytes"], file["sha256"]):
            raise ValueError(f"Feature bundle integrity failed: {filename}.")
        ledgers[name] = [loads(line) for line in content.splitlines()]
    roster = ledgers["prediction_eligibility"]
    outcomes = ledgers["outcomes"]
    observations = ledgers["observations"]
    candidate_keys = _ordered(roster)
    eligible_keys = [
        key for key, row in zip(candidate_keys, roster, strict=True) if row["exclusion"] is None
    ]
    predictors = [_decode(row) for row in ledgers["predictors"]]
    if (
        _ordered(outcomes) != candidate_keys
        or _ordered(observations) != eligible_keys
        or len(predictors) != len(eligible_keys)
    ):
        raise ValueError("Prediction and outcome ledgers do not align.")
    eligible = dict(zip(eligible_keys, zip(observations, predictors, strict=True), strict=True))
    owners = {}
    missing = Counter({name: 0 for name in COLUMNS})
    coverage = Counter()
    coverage_index = COLUMNS.index("usage_coverage_ratio")
    states = Counter()
    rows = []
    for key, outcome in zip(candidate_keys, outcomes, strict=True):
        state = outcome["outcome"]["state"]
        target = STATES[state]
        horizon = _time(outcome["horizon_end"])
        ascertainment = _time(outcome["ascertainment_cutoff"])
        trainable = key in eligible and target is not None
        if (
            type(target) is not type(outcome["binary_target"])
            or target != outcome["binary_target"]
            or outcome["retrospective_training_eligible"] is not trainable
            or horizon != key.observed_at + timedelta(days=30)
            or not key.observed_at <= ascertainment <= EXTRACTION
            or target is not None
            and (horizon > ascertainment or not outcome["outcome"]["source_ref"])
        ):
            raise ValueError("Outcome, maturity or training eligibility is inconsistent.")
        states[state] += 1
        if key not in eligible:
            continue
        metadata, values = eligible[key]
        customer = metadata["customer_id"]
        if (
            type(customer) is not str
            or not customer
            or owners.setdefault(key.subscription_id, customer) != customer
            or _time(metadata["latest_evidence_at"]) > key.observed_at
        ):
            raise ValueError("Inconsistent account ownership or future predictor evidence.")
        missing.update(name for name, value in zip(COLUMNS, values, strict=True) if value is None)
        ratio = values[coverage_index]
        coverage["No expected months" if ratio is None else f"{ratio:.2%}"] += 1
        if trainable:
            rows.append(ResolvedObservation(key, customer, horizon, ascertainment, target, values))
    inventory = {
        "candidates": len(roster),
        "prediction_eligible": len(eligible),
        "resolved_eligible": len(rows),
        "outcomes": dict(states),
        "prediction_exclusions": dict(Counter(r["exclusion"] for r in roster if r["exclusion"])),
    }
    return Bundle(
        tuple(rows),
        frozenset(key.subscription_id for key in candidate_keys),
        seed,
        sha256(manifest_bytes).hexdigest(),
        manifest["internal_evidence_sha256"],
        inventory,
        dict(missing),
        dict(coverage),
    )


def development_group(customer: str) -> str:
    """Allocate a fictional account without consulting its labels or episode IDs."""
    value = sha256(f"{GROUP_SALT}:{customer}".encode()).digest()
    return (
        "training" if int.from_bytes(value[:8], "big") % 100 < TRAIN_GROUP_PERCENT else "validation"
    )


def partition(
    bundle: Bundle, *, fresh: bool
) -> tuple[dict[str, tuple[ResolvedObservation, ...]], dict[str, int]]:
    """Apply exclusive UTC maturity boundaries and fixed account allocation."""
    expected_seed = HOLDOUT_SEED if fresh else REFERENCE_SEED
    if bundle.seed != expected_seed:
        raise ValueError("Unexpected partition source seed.")
    partitions = {"holdout": []} if fresh else {"training": [], "validation": []}
    excluded = Counter()
    for row in bundle.rows:
        observed = row.key.observed_at
        if fresh:
            if not VALIDATION_END <= observed < HOLDOUT_END:
                excluded["outside_holdout_window"] += 1
                continue
            name, end = "holdout", HOLDOUT_END
        else:
            if observed >= VALIDATION_END:
                excluded["previously_examined_period_or_later"] += 1
                continue
            name, end = (
                ("training", TRAIN_END) if observed < TRAIN_END else ("validation", VALIDATION_END)
            )
        if max(row.horizon, row.ascertainment) >= end:
            excluded["label_not_mature_at_boundary"] += 1
        elif not fresh and development_group(row.customer) != name:
            excluded["account_allocated_to_other_partition"] += 1
        else:
            partitions[name].append(row)
    ordered = {
        name: tuple(
            sorted(
                rows, key=lambda row: (row.key.observed_at, row.customer, row.key.subscription_id)
            )
        )
        for name, rows in partitions.items()
    }
    return ordered, dict(excluded)


def support(rows: tuple[ResolvedObservation, ...]) -> dict:
    """Count observations and independent account and episode support."""
    positive = [row for row in rows if row.target]
    concentration = Counter(row.customer for row in positive)
    return {
        "rows": len(rows),
        "positives": len(positive),
        "negatives": len(rows) - len(positive),
        "prevalence": len(positive) / len(rows) if rows else None,
        "customers": len({row.customer for row in rows}),
        "episodes": len({row.key.subscription_id for row in rows}),
        "positive_customers": len(concentration),
        "positive_episodes": len({row.key.subscription_id for row in positive}),
        "max_positives_per_customer": max(concentration.values(), default=0),
        "first_observation": min((row.key.observed_at.isoformat() for row in rows), default=None),
        "last_observation": max((row.key.observed_at.isoformat() for row in rows), default=None),
    }


def model_inputs(rows: tuple[ResolvedObservation, ...]) -> pd.DataFrame:
    """Convert exact GBP amounts at the numeric model boundary only."""
    frame = pd.DataFrame.from_records((row.predictors for row in rows), columns=COLUMNS)
    for spec in FEATURE_SPECS:
        if spec.dtype is not str:
            frame[spec.name] = frame[spec.name].astype(float)
    return frame
