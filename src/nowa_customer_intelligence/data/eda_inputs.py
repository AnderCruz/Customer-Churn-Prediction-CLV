"""Reconstruct the accepted Fieldwise reference for local descriptive analysis."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from .synthetic.billing import InvoiceStatus
from .synthetic.churn_experiment import ChurnExperiment, ExperimentObservation
from .synthetic.configuration import load_configuration, resolve_configuration
from .synthetic.development import DevelopmentGenerationRequest, DevelopmentScenario
from .synthetic.modelling_dataset import (
    ModellingDataset,
    ObservationCandidate,
    SimulationFollowUp,
    build_modelling_dataset,
)
from .synthetic.observations import UsageAssumptions
from .synthetic.provenance import (
    ProvenancedDevelopment,
    evaluate_development_acceptance,
    run_development_with_provenance,
)

REFERENCE_CUTOFF = datetime(2024, 3, 31, 23, 59, 59, 999999, tzinfo=UTC)

_CONFIGURATION = b"""
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


@contextmanager
def fieldwise_reference(
    *,
    registry_path: Path | None = None,
    master_seed: int = 42,
    client_scope: str = "fieldwise-fictional",
) -> Iterator[tuple[ProvenancedDevelopment, Path]]:
    """Expose verified Fieldwise outputs using the reference scenario parameters."""
    if type(master_seed) is not int:
        raise ValueError("Expected a whole-number Fieldwise seed.")
    document = _CONFIGURATION.replace(
        b"master_seed: 42", f"master_seed: {master_seed}".encode("ascii")
    )
    configuration = resolve_configuration(load_configuration(document), "baseline")
    with TemporaryDirectory(prefix="nci-fieldwise-eda-") as temporary:
        root = Path(temporary)
        export = root / "export"
        export.mkdir()
        request = DevelopmentGenerationRequest(
            configuration,
            DevelopmentScenario(
                1200, "launch", 25, InvoiceStatus.FAILED, UsageAssumptions(2, 20, 60, 300)
            ),
            registry_path if registry_path is not None else root / "registry.sqlite",
            client_scope,
            "phase04",
            REFERENCE_CUTOFF,
            export,
        )
        run = run_development_with_provenance(request)
        if not evaluate_development_acceptance(run.provenance, directory=export).accepted:
            raise RuntimeError("The Fieldwise reference did not pass development acceptance.")
        yield run, export


def reference_candidates(
    run: ProvenancedDevelopment, experiment: ChurnExperiment
) -> Iterator[ObservationCandidate]:
    """Yield the reference snapshot observations with separate adjudication bounds."""
    horizon = timedelta(days=experiment.horizon_days)
    for row in run.population.snapshots:
        yield ObservationCandidate(
            row.subscription_id,
            ExperimentObservation(
                row.observed_at, min(row.observed_at + horizon, experiment.extraction_cutoff)
            ),
        )


def reference_follow_up() -> SimulationFollowUp:
    """Supply the existing fictional ledger attestation."""
    return SimulationFollowUp(
        "fixture-authority:exhaustive-fieldwise-event-ledger", REFERENCE_CUTOFF
    )


def reference_outcomes(run: ProvenancedDevelopment, export: Path) -> ModellingDataset:
    """Reconstruct the existing synthetic outcome experiment without fitting a model."""
    experiment = ChurnExperiment(REFERENCE_CUTOFF)
    return build_modelling_dataset(
        run,
        export,
        experiment,
        reference_candidates(run, experiment),
        simulation_follow_up=reference_follow_up(),
    )
