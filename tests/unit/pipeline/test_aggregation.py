"""Unit tests for pipeline overall status aggregation."""

from collections.abc import Sequence
from itertools import permutations

import pytest

from nowa_customer_intelligence.pipeline import (
    PipelineOverallStatus,
    StageExecutionResult,
    StageExecutionStatus,
    StageRequirement,
    determine_pipeline_overall_status,
)


def make_stage(
    status: StageExecutionStatus,
    requirement: StageRequirement = StageRequirement.REQUIRED,
    *,
    stage_id: str = "stage",
) -> StageExecutionResult:
    """Create a valid stage result for aggregation tests."""
    return StageExecutionResult(stage_id=stage_id, status=status, requirement=requirement)


def make_unvalidated_stage(**updates: object) -> StageExecutionResult:
    """Bypass dataclass validation to exercise malformed object handling."""
    values: dict[str, object] = {
        "stage_id": "stage",
        "status": StageExecutionStatus.SUCCEEDED,
        "requirement": StageRequirement.REQUIRED,
    }
    values.update(updates)
    stage = object.__new__(StageExecutionResult)
    for field_name, value in values.items():
        object.__setattr__(stage, field_name, value)
    return stage


@pytest.mark.parametrize(
    ("stage_status", "expected"),
    [
        (StageExecutionStatus.SUCCEEDED, PipelineOverallStatus.SUCCEEDED),
        (StageExecutionStatus.FAILED, PipelineOverallStatus.FAILED),
        (StageExecutionStatus.BLOCKED, PipelineOverallStatus.BLOCKED),
        (StageExecutionStatus.PARTIAL, PipelineOverallStatus.PARTIAL),
        (StageExecutionStatus.SKIPPED, PipelineOverallStatus.PARTIAL),
        (StageExecutionStatus.NOT_IMPLEMENTED, PipelineOverallStatus.BLOCKED),
    ],
)
def test_required_stage_status_maps_to_approved_overall_status(
    stage_status: StageExecutionStatus, expected: PipelineOverallStatus
) -> None:
    assert determine_pipeline_overall_status([make_stage(stage_status)]) is expected


@pytest.mark.parametrize(
    "stage_status",
    [
        StageExecutionStatus.SUCCEEDED,
        StageExecutionStatus.FAILED,
        StageExecutionStatus.PARTIAL,
        StageExecutionStatus.BLOCKED,
        StageExecutionStatus.SKIPPED,
        StageExecutionStatus.NOT_IMPLEMENTED,
    ],
)
def test_all_optional_stage_statuses_are_neutral(stage_status: StageExecutionStatus) -> None:
    stage = make_stage(stage_status, StageRequirement.OPTIONAL)

    assert determine_pipeline_overall_status([stage]) is PipelineOverallStatus.SUCCEEDED


def test_not_applicable_stage_is_neutral() -> None:
    stage = make_stage(
        StageExecutionStatus.NOT_APPLICABLE,
        StageRequirement.NOT_APPLICABLE,
    )

    assert determine_pipeline_overall_status([stage]) is PipelineOverallStatus.SUCCEEDED


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((StageExecutionStatus.FAILED, StageExecutionStatus.BLOCKED), PipelineOverallStatus.FAILED),
        ((StageExecutionStatus.FAILED, StageExecutionStatus.PARTIAL), PipelineOverallStatus.FAILED),
        (
            (StageExecutionStatus.BLOCKED, StageExecutionStatus.PARTIAL),
            PipelineOverallStatus.BLOCKED,
        ),
        (
            (StageExecutionStatus.PARTIAL, StageExecutionStatus.SUCCEEDED),
            PipelineOverallStatus.PARTIAL,
        ),
        (
            (
                StageExecutionStatus.SUCCEEDED,
                StageExecutionStatus.PARTIAL,
                StageExecutionStatus.FAILED,
                StageExecutionStatus.BLOCKED,
            ),
            PipelineOverallStatus.FAILED,
        ),
        (
            (
                StageExecutionStatus.SUCCEEDED,
                StageExecutionStatus.PARTIAL,
                StageExecutionStatus.BLOCKED,
            ),
            PipelineOverallStatus.BLOCKED,
        ),
    ],
)
def test_required_stage_precedence(
    statuses: tuple[StageExecutionStatus, ...], expected: PipelineOverallStatus
) -> None:
    stages = [
        make_stage(status, stage_id=f"stage-{index}") for index, status in enumerate(statuses)
    ]

    assert determine_pipeline_overall_status(stages) is expected


def test_empty_stage_sequence_is_blocked() -> None:
    assert determine_pipeline_overall_status(()) is PipelineOverallStatus.BLOCKED


def test_all_optional_stages_are_succeeded() -> None:
    stages = [
        make_stage(StageExecutionStatus.FAILED, StageRequirement.OPTIONAL, stage_id="optional-a"),
        make_stage(
            StageExecutionStatus.NOT_IMPLEMENTED, StageRequirement.OPTIONAL, stage_id="optional-b"
        ),
    ]

    assert determine_pipeline_overall_status(stages) is PipelineOverallStatus.SUCCEEDED


def test_all_not_applicable_stages_are_succeeded() -> None:
    stages = [
        make_stage(
            StageExecutionStatus.NOT_APPLICABLE,
            StageRequirement.NOT_APPLICABLE,
            stage_id=f"stage-{index}",
        )
        for index in range(2)
    ]

    assert determine_pipeline_overall_status(stages) is PipelineOverallStatus.SUCCEEDED


def test_mixed_optional_and_not_applicable_stages_are_succeeded() -> None:
    stages = [
        make_stage(StageExecutionStatus.FAILED, StageRequirement.OPTIONAL, stage_id="optional"),
        make_stage(
            StageExecutionStatus.NOT_APPLICABLE,
            StageRequirement.NOT_APPLICABLE,
            stage_id="not-applicable",
        ),
    ]

    assert determine_pipeline_overall_status(stages) is PipelineOverallStatus.SUCCEEDED


@pytest.mark.parametrize("value", [None, 1, {"not": "a sequence"}, iter(())])
def test_rejects_non_sequence_inputs(value: object) -> None:
    with pytest.raises(TypeError, match="sequence"):
        determine_pipeline_overall_status(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", ["stages", b"stages"])
def test_rejects_string_and_bytes_inputs(value: str | bytes) -> None:
    with pytest.raises(TypeError, match="sequence"):
        determine_pipeline_overall_status(value)  # type: ignore[arg-type]


def test_rejects_non_stage_sequence_elements() -> None:
    invalid_stages: Sequence[object] = [make_stage(StageExecutionStatus.SUCCEEDED), object()]

    with pytest.raises(TypeError, match="StageExecutionResult"):
        determine_pipeline_overall_status(invalid_stages)  # type: ignore[arg-type]


def test_rejects_repeated_stage_ids_without_consolidating_attempts() -> None:
    stages = [
        make_stage(StageExecutionStatus.FAILED, stage_id="ingestion"),
        make_stage(StageExecutionStatus.SUCCEEDED, stage_id="ingestion"),
    ]

    with pytest.raises(ValueError, match="consolidate attempts"):
        determine_pipeline_overall_status(stages)


@pytest.mark.parametrize(
    ("stage", "exception"),
    [
        (make_unvalidated_stage(status="FAILED"), TypeError),
        (make_unvalidated_stage(requirement="REQUIRED"), TypeError),
        (
            make_unvalidated_stage(
                status=StageExecutionStatus.SUCCEEDED,
                requirement=StageRequirement.NOT_APPLICABLE,
            ),
            ValueError,
        ),
    ],
)
def test_rejects_invalid_stage_enum_or_requirement_status_combination(
    stage: StageExecutionResult, exception: type[Exception]
) -> None:
    with pytest.raises(exception):
        determine_pipeline_overall_status([stage])


def test_accepts_tuple_and_list_inputs() -> None:
    stage = make_stage(StageExecutionStatus.SUCCEEDED)

    assert determine_pipeline_overall_status((stage,)) is PipelineOverallStatus.SUCCEEDED
    assert determine_pipeline_overall_status([stage]) is PipelineOverallStatus.SUCCEEDED


def test_repeated_calls_are_deterministic_and_leave_input_unchanged() -> None:
    stages = [
        make_stage(StageExecutionStatus.PARTIAL, stage_id="partial"),
        make_stage(StageExecutionStatus.SUCCEEDED, stage_id="success"),
    ]
    original_stages = stages.copy()
    original_values = [(stage.stage_id, stage.status, stage.requirement) for stage in stages]

    first = determine_pipeline_overall_status(stages)
    second = determine_pipeline_overall_status(stages)

    assert first is second is PipelineOverallStatus.PARTIAL
    assert stages == original_stages
    assert [
        (stage.stage_id, stage.status, stage.requirement) for stage in stages
    ] == original_values


def test_stage_order_does_not_change_result() -> None:
    stages = (
        make_stage(StageExecutionStatus.SUCCEEDED, stage_id="success"),
        make_stage(StageExecutionStatus.BLOCKED, stage_id="blocked"),
        make_stage(StageExecutionStatus.PARTIAL, stage_id="partial"),
    )

    results = {determine_pipeline_overall_status(order) for order in permutations(stages)}

    assert results == {PipelineOverallStatus.BLOCKED}
