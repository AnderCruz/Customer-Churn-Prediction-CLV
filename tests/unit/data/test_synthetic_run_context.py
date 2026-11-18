"""Verify in-memory scope, provenance and stage evidence."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from nowa_customer_intelligence.data.synthetic.configuration import (
    EffectiveConfiguration,
    load_configuration,
    resolve_configuration,
)
from nowa_customer_intelligence.data.synthetic.run_context import (
    RunContextError,
    SourceMetadata,
    StageDiagnostic,
    StageExecutionError,
    StageId,
    StageStatus,
    StageTracker,
    StageTransitionError,
    create_run_context,
)
from nowa_customer_intelligence.pipeline.models import PipelineWorkflow

_DOCUMENT = b"""
config_schema_version: 1
base:
  population: {customer_count: 3, episode_count_min: 3, episode_count_max: 5}
  history: {start_date: '2023-01-01', cutoff_date: '2026-01-01'}
  master_seed: 0
  workflow: BASIC
  execution_scope: configuration_only
  requested_outputs: [customers.csv, subscriptions.csv]
  policy_refs: {contract_version: '1.1', business_model_version: '0.2', snapshot_decision: PD-006}
scenarios: {baseline: {scenario_version: 1}}
"""
_ID = UUID("12345678-1234-4234-8234-123456789abc")
_START = datetime(2026, 11, 18, 12, tzinfo=UTC)


@pytest.fixture
def effective() -> EffectiveConfiguration:
    return resolve_configuration(load_configuration(_DOCUMENT), "baseline")


def test_context_captures_immutable_scope_and_provenance(effective: EffectiveConfiguration) -> None:
    metadata = SourceMetadata("93bb092", True)
    context = create_run_context(
        effective,
        clock=lambda: _START.astimezone(timezone(timedelta(hours=-3))),
        run_id_factory=lambda: _ID,
        source_metadata=metadata,
    )
    assert context.run_id == f"gen-{_ID}"
    assert context.started_at_utc == _START and context.started_at_utc.tzinfo is UTC
    assert context.source_metadata == metadata
    assert context.python_version
    assert context.effective_configuration.workflow is PipelineWorkflow.BASIC
    assert context.effective_configuration.scenario_version == 1
    assert context.effective_configuration.policy_refs.snapshot_decision == "PD-006"
    assert (
        context.planned_inventory
        == context.required_inputs
        == ("customers.csv", "subscriptions.csv")
    )
    assert context.generated_inventory == ()
    gates = {gate.gate_id: gate.applicability for gate in context.gates}
    assert gates["contract_schema"] == gates["publication_authorisation"] == "outside_scope"
    assert gates["configuration_validation"] == "required"
    with pytest.raises(FrozenInstanceError):
        context.source_metadata.dirty = False
    with pytest.raises(FrozenInstanceError):
        context.run_id = "different"


def test_run_id_is_independent_of_master_seed(effective: EffectiveConfiguration) -> None:
    changed = resolve_configuration(load_configuration(_DOCUMENT), "baseline", {"master_seed": 12})
    assert (
        create_run_context(effective, run_id_factory=lambda: _ID).run_id
        == create_run_context(changed, run_id_factory=lambda: _ID).run_id
    )
    first, second = create_run_context(effective), create_run_context(effective)
    assert first.run_id != second.run_id
    assert UUID(first.run_id.removeprefix("gen-")).version == 4
    assert first.source_metadata == SourceMetadata()


@pytest.mark.parametrize("invalid", [b"{}", {}, load_configuration(_DOCUMENT)])
def test_context_rejects_unresolved_configuration(invalid: object) -> None:
    with pytest.raises(RunContextError, match="resolved"):
        create_run_context(invalid)


def test_context_rejects_invalid_clock_and_identifier(effective: EffectiveConfiguration) -> None:
    with pytest.raises(RunContextError, match="timezone-aware"):
        create_run_context(effective, clock=lambda: _START.replace(tzinfo=None))
    with pytest.raises(RunContextError, match="UUID4"):
        create_run_context(effective, run_id_factory=lambda: "sensitive-sentinel")
    assert create_run_context(effective, run_id_factory=uuid4).started_at_utc.tzinfo is UTC


@pytest.mark.parametrize("kwargs", [{"revision": "/sentinel/private"}, {"dirty": 1}])
def test_source_metadata_rejects_unrestricted_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(RunContextError) as caught:
        SourceMetadata(**kwargs)
    assert "sentinel" not in str(caught.value)


@pytest.fixture
def tracker(effective: EffectiveConfiguration) -> StageTracker:
    return StageTracker(create_run_context(effective, clock=lambda: _START), clock=lambda: _START)


def _outcome(tracker: StageTracker, stage_id: StageId):
    return next(row for row in tracker.snapshot().stage_outcomes if row.stage_id is stage_id)


def test_success_and_immutable_snapshots(tracker: StageTracker) -> None:
    before = tracker.snapshot()
    tracker.start(StageId.INVENTORY_REVIEW)
    running = _outcome(tracker, StageId.INVENTORY_REVIEW)
    tracker.succeed(StageId.INVENTORY_REVIEW)
    assert running.status is StageStatus.RUNNING
    assert before.stage_outcomes[2].status is StageStatus.NOT_RUN
    assert _outcome(tracker, StageId.INVENTORY_REVIEW).completed_at_utc == _START
    assert tracker.run_stage(StageId.SCOPE_REVIEW, lambda: 42) == 42
    assert _outcome(tracker, StageId.SCOPE_REVIEW).status is StageStatus.SUCCEEDED
    with pytest.raises(FrozenInstanceError):
        running.status = StageStatus.FAILED


def test_invalid_transitions_do_not_mutate_stage_evidence(tracker: StageTracker) -> None:
    stage = StageId.INVENTORY_REVIEW
    with pytest.raises(StageTransitionError, match="Unknown"):
        tracker.start("raw-sentinel")
    with pytest.raises(StageTransitionError, match="prerequisites"):
        tracker.start(StageId.SCOPE_REVIEW)
    with pytest.raises(StageTransitionError, match="transition"):
        tracker.succeed(stage)
    with pytest.raises(StageTransitionError, match="starts before"):
        tracker.start(stage, at=_START - timedelta(seconds=1))
    tracker.start(stage)
    with pytest.raises(StageTransitionError, match="transition"):
        tracker.start(stage)
    with pytest.raises(StageTransitionError, match="precedes"):
        tracker.fail(stage, at=_START - timedelta(seconds=1))
    assert _outcome(tracker, stage).status is StageStatus.RUNNING
    tracker.succeed(stage)
    with pytest.raises(StageTransitionError, match="transition"):
        tracker.fail(stage)


def test_failure_blocks_dependants_and_preserves_independent_stages(
    tracker: StageTracker, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level("INFO")

    def fail_with_sensitive_payload() -> None:
        raise RuntimeError("/private/raw-sentinel with seed and raw YAML")

    with pytest.raises(StageExecutionError) as caught:
        tracker.run_stage(StageId.INVENTORY_REVIEW, fail_with_sensitive_payload)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "raw-sentinel" not in str(caught.value) + repr(vars(caught.value)) + caplog.text
    failed = _outcome(tracker, StageId.INVENTORY_REVIEW)
    blocked = _outcome(tracker, StageId.SCOPE_REVIEW)
    assert failed.status is StageStatus.FAILED
    assert failed.diagnostic is StageDiagnostic.EXECUTION_FAILED
    assert blocked.status is StageStatus.BLOCKED and blocked.blocked_by is failed.stage_id
    assert blocked.started_at_utc is None and blocked.completed_at_utc is None
    assert _outcome(tracker, StageId.DIAGNOSTICS_PREPARATION).status is StageStatus.NOT_RUN
    with pytest.raises(StageTransitionError, match="transition"):
        tracker.start(StageId.SCOPE_REVIEW)
    tracker.run_stage(StageId.DIAGNOSTICS_PREPARATION, lambda: None)
    assert _outcome(tracker, StageId.DIAGNOSTICS_PREPARATION).status is StageStatus.SUCCEEDED
    assert [r.message for r in caplog.records] == [
        "generator_stage_started",
        "generator_stage_failed",
        "generator_stage_blocked",
        "generator_stage_started",
        "generator_stage_succeeded",
    ]
    assert caplog.records[1].generator_diagnostic_code == "STAGE_EXECUTION_FAILED"
    assert not any(record.exc_info for record in caplog.records)


def test_warning_level_keeps_failures_visible(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO")
    effective = resolve_configuration(
        load_configuration(_DOCUMENT), "baseline", {"diagnostics": {"level": "WARNING"}}
    )
    tracker = StageTracker(
        create_run_context(effective, clock=lambda: _START), clock=lambda: _START
    )
    tracker.start(StageId.INVENTORY_REVIEW)
    tracker.fail(StageId.INVENTORY_REVIEW)
    assert [record.message for record in caplog.records] == [
        "generator_stage_failed",
        "generator_stage_blocked",
    ]


def test_plan_rejects_cycles_and_unknown_dependencies(effective: EffectiveConfiguration) -> None:
    context = create_run_context(effective)
    with pytest.raises(StageTransitionError, match="cycle"):
        StageTracker(context, stages={StageId.SCOPE_REVIEW: (StageId.SCOPE_REVIEW,)})
    with pytest.raises(StageTransitionError, match="dependency"):
        StageTracker(context, stages={StageId.SCOPE_REVIEW: (StageId.INVENTORY_REVIEW,)})


def test_operation_failure_remains_visible_when_completion_clock_regresses(
    effective: EffectiveConfiguration,
) -> None:
    ticks = iter((_START, _START - timedelta(seconds=1)))
    tracker = StageTracker(
        create_run_context(effective, clock=lambda: _START), clock=lambda: next(ticks)
    )

    def operation() -> None:
        raise RuntimeError("private operation diagnostic")

    with pytest.raises(StageExecutionError):
        tracker.run_stage(StageId.INVENTORY_REVIEW, operation)
    result = _outcome(tracker, StageId.INVENTORY_REVIEW)
    assert result.status is StageStatus.FAILED
    assert result.completed_at_utc is None
    assert _outcome(tracker, StageId.SCOPE_REVIEW).status is StageStatus.BLOCKED
