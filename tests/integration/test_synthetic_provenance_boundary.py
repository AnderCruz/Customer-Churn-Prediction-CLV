"""Verify scoped acceptance, replay, failure propagation and CSV integrity."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from nowa_customer_intelligence.data.synthetic import development
from nowa_customer_intelligence.data.synthetic.billing import InvoiceStatus
from nowa_customer_intelligence.data.synthetic.configuration import (
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.development import (
    DevelopmentGenerationRequest,
    DevelopmentScenario,
)
from nowa_customer_intelligence.data.synthetic.identity_registry import (
    EpisodeIdentityRegistry,
    IdentityConflict,
)
from nowa_customer_intelligence.data.synthetic.lifecycle import LifecycleKind
from nowa_customer_intelligence.data.synthetic.observations import UsageAssumptions
from nowa_customer_intelligence.data.synthetic.provenance import (
    DevelopmentProvenance,
    GateStatus,
    ProvenancedDevelopment,
    evaluate_development_acceptance,
    run_development_with_provenance,
    verify_development_integrity,
)
from nowa_customer_intelligence.data.synthetic.run_context import SourceMetadata
from nowa_customer_intelligence.data.synthetic.semantic_validation import (
    validate_synthetic_evidence,
)
from nowa_customer_intelligence.data.validation.models import RuleExecutionResult
from nowa_customer_intelligence.pipeline import PipelineWorkflow, execute_pipeline

_DOCUMENT = b"""
config_schema_version: 1
base:
  population: {customer_count: 4, episode_count_min: 4, episode_count_max: 8}
  history: {start_date: '2021-04-01', cutoff_date: '2024-03-31'}
  master_seed: 42
  workflow: TEMPORAL
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv, subscription_snapshots.csv,
                      usage_monthly.csv, invoices.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios: {baseline: {scenario_version: 1}}
"""


def _directory(root: Path, name: str) -> Path:
    folder = root / name
    folder.mkdir()
    return folder


@pytest.fixture
def request_spec(tmp_path: Path) -> DevelopmentGenerationRequest:
    return DevelopmentGenerationRequest(
        resolve_configuration(load_configuration(_DOCUMENT), "baseline"),
        DevelopmentScenario(
            5, "launch", 25, InvoiceStatus.PENDING, UsageAssumptions(2, 20, 60, 300)
        ),
        tmp_path / "registry.sqlite",
        "private-client-sentinel",
        "private-namespace-sentinel",
        datetime(2024, 3, 31, 23, 59, 59, 999999, tzinfo=UTC),
        _directory(tmp_path, "private-path-sentinel"),
    )


@pytest.fixture
def accepted_run(request_spec: DevelopmentGenerationRequest) -> ProvenancedDevelopment:
    run = run_development_with_provenance(
        request_spec, source_metadata=SourceMetadata("58043a3", True)
    )
    assert evaluate_development_acceptance(
        run.provenance, directory=request_spec.export_directory
    ).accepted
    return run


def _gates(
    provenance: DevelopmentProvenance, directory: Path | None = None
) -> dict[str, GateStatus]:
    return {
        row.gate: row.status
        for row in evaluate_development_acceptance(provenance, directory=directory).gates
    }


def test_reopened_registry_preserves_rows_and_safe_provenance(
    accepted_run: ProvenancedDevelopment, request_spec: DevelopmentGenerationRequest, tmp_path: Path
) -> None:
    original = accepted_run.provenance
    replay_dir = _directory(tmp_path, "replay")
    replay = run_development_with_provenance(replace(request_spec, export_directory=replay_dir))
    assert replay.population.tables == accepted_run.population.tables
    assert replay.population.episodes == accepted_run.population.episodes
    assert replay.provenance.parameters == original.parameters
    assert replay.provenance.integrity == original.integrity
    assert replay.provenance.run_id != original.run_id
    assert original.started_at <= original.completed_at
    assert original.source_revision == "58043a3"
    assert original.stream_algorithm == "numpy.PCG64+sha256/nci-stream-v1"
    assert {"numpy", "pandas", "python"} <= dict(original.dependencies).keys()
    assert "sentinel" not in repr(original)
    assert evaluate_development_acceptance(replay.provenance, directory=replay_dir).accepted
    assert _gates(original)["output_integrity"] is GateStatus.NOT_EVALUATED


def test_changed_configuration_is_recorded_without_certifying_replay(
    accepted_run: ProvenancedDevelopment, request_spec: DevelopmentGenerationRequest
) -> None:
    new_effective = resolve_configuration(
        load_configuration(_DOCUMENT),
        "baseline",
        {
            "master_seed": 43,
        },
    )
    changed = run_development_with_provenance(
        replace(
            request_spec,
            effective=new_effective,
            export_directory=None,
            validation_workflows=(),
        )
    ).provenance
    assert changed.parameters.seed_reference != accepted_run.provenance.parameters.seed_reference
    assert changed.certification == "NOT_CERTIFIED"
    assert changed.integrity is None
    assert _gates(changed)["schema_validation"] is GateStatus.NOT_EVALUATED
    assert not evaluate_development_acceptance(changed).accepted


@pytest.mark.parametrize(
    ("defect", "category"),
    [
        ("equal_length", "checksum_mismatch"),
        ("truncate", "size_mismatch"),
        ("remove", "missing_file"),
        ("symlink", "unsupported_file"),
        ("unexpected", None),
    ],
)
def test_single_export_defect_rejects_acceptance_without_repair(
    defect: str,
    category: str | None,
    accepted_run: ProvenancedDevelopment,
    request_spec: DevelopmentGenerationRequest,
    tmp_path: Path,
) -> None:
    original = accepted_run.provenance
    directory = request_spec.export_directory
    original_report = original.integrity
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    target = directory / "customers.csv"
    if defect == "equal_length":
        target.write_bytes(before[target.name].replace(b",GB", b",US", 1))
    elif defect == "truncate":
        target.write_bytes(before[target.name][:-5])
    elif defect == "remove":
        target.unlink()
    elif defect == "symlink":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.write_bytes(before[target.name])
        target.unlink()
        target.symlink_to(elsewhere)
    else:
        (directory / "unexpected.txt").write_text("fixture defect")

    changed = {path.name: path.read_bytes() for path in directory.iterdir()}
    checked = verify_development_integrity(directory, original_report)
    assert not checked.passed and original_report.passed
    if category is None:
        assert checked.unexpected_files == 1
    else:
        assert next(row for row in checked.files if row.dataset == "customers").problem == category
    assert _gates(original, directory)["output_integrity"] is GateStatus.FAILED
    assert not evaluate_development_acceptance(original, directory=directory).accepted
    assert {path.name: path.read_bytes() for path in directory.iterdir()} == changed
    assert original.integrity == original_report


@pytest.mark.parametrize(
    ("defect", "gate", "expected"),
    [
        ("inventory", "dataset_inventory", GateStatus.FAILED),
        ("missing_file_evidence", "output_integrity", GateStatus.NOT_EVALUATED),
        ("missing_integrity", "output_integrity", GateStatus.NOT_EVALUATED),
        ("missing_workflow", "pipeline_workflows", GateStatus.NOT_EVALUATED),
        ("failed_dq_finding", "existing_data_quality", GateStatus.FAILED),
    ],
)
def test_acceptance_rejects_defective_evidence(
    defect: str,
    gate: str,
    expected: GateStatus,
    accepted_run: ProvenancedDevelopment,
    request_spec: DevelopmentGenerationRequest,
) -> None:
    original = accepted_run.provenance
    if defect == "inventory":
        corrupt = replace(original, inventory=original.inventory[:-1])
    elif defect == "missing_file_evidence":
        corrupt = replace(
            original, integrity=replace(original.integrity, files=original.integrity.files[:-1])
        )
    elif defect == "missing_integrity":
        corrupt = replace(original, integrity=None)
    elif defect == "missing_workflow":
        corrupt = replace(original, pipeline=original.pipeline[:-1])
    else:
        evidence = original.pipeline[0]
        rules = tuple(
            (name, RuleExecutionResult.FAIL if name == "RI-001" else status)
            for name, status in evidence.rules
        )
        corrupt = replace(
            original, pipeline=(replace(evidence, rules=rules), *original.pipeline[1:])
        )
    evaluation = evaluate_development_acceptance(corrupt, directory=request_spec.export_directory)
    assert not evaluation.accepted
    assert _gates(corrupt, request_spec.export_directory)[gate] is expected
    assert evaluate_development_acceptance(
        original, directory=request_spec.export_directory
    ).accepted


def test_real_failed_pipeline_cannot_accept_changed_export(
    request_spec: DevelopmentGenerationRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = []

    def corrupt_before_pipeline(request):
        path = request.dataset_sources["customers"]
        data = path.read_bytes()
        original.append(data)
        path.write_bytes(data.replace(b"customer_id,created_at", b"invalid_id,created_at", 1))
        return execute_pipeline(request)

    monkeypatch.setattr(
        "nowa_customer_intelligence.data.synthetic.development.execute_pipeline",
        corrupt_before_pipeline,
    )
    run = run_development_with_provenance(request_spec)
    assert run.provenance.integrity.directory_problem == "validation_window_mismatch"
    gates = _gates(run.provenance, request_spec.export_directory)
    assert gates["pipeline_workflows"] is GateStatus.FAILED
    assert gates["output_integrity"] is GateStatus.FAILED
    assert not evaluate_development_acceptance(
        run.provenance, directory=request_spec.export_directory
    ).accepted
    assert (request_spec.export_directory / "customers.csv").read_bytes() != original[0]


def test_interrupted_export_returns_no_provenance_and_rolls_back(
    request_spec: DevelopmentGenerationRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.open

    def break_second_write(path, *args, **kwargs):
        if path.name == "subscriptions.csv":
            raise OSError("controlled write failure")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", break_second_write)
        with pytest.raises(OSError, match="controlled write failure"):
            run_development_with_provenance(request_spec)
    assert list(request_spec.export_directory.iterdir()) == []
    repaired = run_development_with_provenance(request_spec)
    assert evaluate_development_acceptance(
        repaired.provenance, directory=request_spec.export_directory
    ).accepted
    assert {row.workflow for row in repaired.provenance.pipeline} == set(PipelineWorkflow)


@pytest.mark.parametrize("mode", ["duplicate", "wrong_owner"])
def test_invoice_defects_fail_actual_evidence_gate(
    mode: str, accepted_run: ProvenancedDevelopment, request_spec: DevelopmentGenerationRequest
) -> None:
    population = accepted_run.population
    invoices = tuple(row.invoice for row in population.charges)
    before = tuple(invoices)
    first = invoices[0]
    owners = {row.invoice_id: row.subscription_id for row in invoices}
    if mode == "duplicate":
        defect = (*invoices, first)
        rule = "invoice_facts"
    else:
        wrong = next(
            row.episode.subscription_id
            for row in population.episodes
            if row.episode.subscription_id != first.subscription_id
        )
        defect = (replace(first, subscription_id=wrong), *invoices[1:])
        rule = "invoice_attribution"
    checked = validate_synthetic_evidence(
        population.customers,
        (row.episode for row in population.episodes),
        cutoff=request_spec.observation_cutoff.date(),
        invoices=defect,
        invoice_owners=owners,
    )
    outcome = next(row for row in checked if row.rule == rule)
    assert outcome.status.value == "FAILED"
    assert outcome.reason == (
        "invalid_supplied_facts" if mode == "duplicate" else "contradictory_source_attribution"
    )
    original = accepted_run.provenance
    candidate = replace(
        original, findings=tuple(outcome if row.rule == rule else row for row in original.findings)
    )
    assert not evaluate_development_acceptance(
        candidate, directory=request_spec.export_directory
    ).accepted
    assert tuple(row.invoice for row in population.charges) == before
    assert evaluate_development_acceptance(
        original, directory=request_spec.export_directory
    ).accepted


def test_cross_client_uuid_conflict_preserves_original_mapping(
    accepted_run: ProvenancedDevelopment, request_spec: DevelopmentGenerationRequest
) -> None:
    row = accepted_run.population.episodes[0]
    registry = EpisodeIdentityRegistry(
        request_spec.registry_path, uuid_factory=lambda: UUID(row.episode.subscription_id)
    )
    other_client = replace(row.identity, client="another-fixture-client")
    with pytest.raises(IdentityConflict, match="already allocated") as error:
        registry.allocate_many((other_client,))
    assert row.episode.subscription_id not in str(error.value)
    assert registry.lookup(other_client) is None
    assert registry.lookup(row.identity) == row.episode.subscription_id
    assert evaluate_development_acceptance(
        accepted_run.provenance, directory=request_spec.export_directory
    ).accepted


@pytest.mark.parametrize(
    ("defect", "category"),
    [
        ("duplicate_episode", "Duplicate subscription identifier"),
        ("reactivation_lineage", "overlap or invalid reactivation"),
        ("transition", "Unsupported fictional lifecycle transition"),
        ("billing_boundary", "Invalid explicit billing or payment facts"),
        ("partial_usage", "completed calendar-month"),
        ("future_snapshot", "extends beyond the observation"),
    ],
)
def test_generation_fails_before_export_for_single_defective_fact(
    defect: str,
    category: str,
    accepted_run: ProvenancedDevelopment,
    request_spec: DevelopmentGenerationRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = _directory(tmp_path, "invalid-attempt")
    if defect in ("duplicate_episode", "reactivation_lineage", "transition"):
        original = development.generate_episodes

        def invalid_episodes(*args, **kwargs):
            rows = original(*args, **kwargs)
            if defect == "duplicate_episode":
                # Return one repeated, otherwise valid episode record.
                return (*rows, rows[0])
            if defect == "reactivation_lineage":
                return tuple(
                    replace(row, prior_subscription_id=row.episode.subscription_id)
                    if row.prior_subscription_id
                    else row
                    for row in rows
                )
            first = replace(
                rows[0],
                facts=(replace(rows[0].facts[0], kind=LifecycleKind.RENEWED), *rows[0].facts[1:]),
            )
            return (first, *rows[1:])

        monkeypatch.setattr(development, "generate_episodes", invalid_episodes)
    elif defect == "billing_boundary":
        original = development.schedule_episode_billing

        def invalid_billing(*args, **kwargs):
            rows = original(*args, **kwargs)
            return (replace(rows[0], period_end=rows[0].invoice.invoice_date), *rows[1:])

        monkeypatch.setattr(development, "schedule_episode_billing", invalid_billing)
    else:
        original = development.generate_episode_observations

        def invalid_observations(*args, **kwargs):
            usage, snapshots = original(*args, **kwargs)
            if defect == "partial_usage" and usage:
                usage = (
                    replace(usage[0], period_end=usage[0].period_end - timedelta(days=1)),
                    *usage[1:],
                )
            if defect == "future_snapshot" and snapshots:
                snapshots = (
                    replace(
                        snapshots[0], available_at=snapshots[0].observed_at + timedelta(seconds=1)
                    ),
                    *snapshots[1:],
                )
            return usage, snapshots

        monkeypatch.setattr(development, "generate_episode_observations", invalid_observations)

    before = {path.name: path.read_bytes() for path in request_spec.export_directory.iterdir()}
    with pytest.raises(ValueError, match=category):
        run_development_with_provenance(replace(request_spec, export_directory=directory))
    assert not list(directory.iterdir())
    assert {
        path.name: path.read_bytes() for path in request_spec.export_directory.iterdir()
    } == before
    assert evaluate_development_acceptance(
        accepted_run.provenance, directory=request_spec.export_directory
    ).accepted
