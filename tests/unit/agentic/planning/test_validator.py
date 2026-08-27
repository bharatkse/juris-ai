"""
Tests for execution plan validation.
"""

from __future__ import annotations

import pytest

from agentic.planning.validator import ExecutionPlanValidator
from core.dto.planning import ExecutionStepDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum
from core.exceptions.planning import PlanValidationError
from tests.builders.agentic.planning import build_plan, build_step


def test_validate_accepts_single_step(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Accept a valid single-step plan.
    """

    plan = build_plan(
        steps=(build_step("step-1"),),
    )

    assert plan_validator.validate(plan) is plan


@pytest.mark.parametrize(
    "mode",
    (
        ExecutionModeEnum.SEQUENTIAL,
        ExecutionModeEnum.PARALLEL,
        ExecutionModeEnum.HYBRID,
    ),
)
def test_validate_accepts_supported_execution_modes(
    plan_validator: ExecutionPlanValidator,
    mode: ExecutionModeEnum,
) -> None:
    """
    Accept all supported execution modes.
    """

    plan = build_plan(
        mode=mode,
        steps=(build_step("step-1"),),
    )

    assert plan_validator.validate(plan) is plan


def test_validate_rejects_empty_plan(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject a plan without execution steps.
    """

    plan = build_plan(
        steps=(),
    )

    with pytest.raises(
        PlanValidationError,
        match="at least one execution step",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_duplicate_step_ids(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject duplicate execution step identifiers.
    """

    plan = build_plan(
        steps=(
            build_step("step-1"),
            build_step("step-1"),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="identifiers must be unique",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_empty_step_id(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject an empty execution step identifier.
    """

    plan = build_plan(
        steps=(build_step("   "),),
    )

    with pytest.raises(
        PlanValidationError,
        match="identifier cannot be empty",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_empty_instruction(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject an empty execution instruction.
    """

    plan = build_plan(
        steps=(
            ExecutionStepDTO(
                id="step-1",
                agent=AgentTypeEnum.LEGAL,
                instruction="   ",
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="instruction cannot be empty",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_invalid_stage(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject an execution step with an invalid stage.
    """

    plan = build_plan(
        steps=(
            build_step(
                "step-1",
                stage=0,
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="stage must be greater than zero",
    ):
        plan_validator.validate(plan)


def test_validate_accepts_valid_dependency_graph(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Accept a valid dependency graph.
    """

    plan = build_plan(
        steps=(
            build_step("step-1"),
            build_step(
                "step-2",
                depends_on=("step-1",),
            ),
            build_step(
                "step-3",
                depends_on=("step-1",),
            ),
            build_step(
                "step-4",
                depends_on=("step-2", "step-3"),
            ),
        ),
        mode=ExecutionModeEnum.HYBRID,
    )

    assert plan_validator.validate(plan) is plan


def test_validate_rejects_unknown_dependency(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject a dependency that references an unknown step.
    """

    plan = build_plan(
        steps=(
            build_step(
                "step-1",
                depends_on=("missing-step",),
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="unknown dependency",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_self_dependency(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject a step that depends on itself.
    """

    plan = build_plan(
        steps=(
            build_step(
                "step-1",
                depends_on=("step-1",),
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="cannot depend on itself",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_duplicate_dependencies(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject duplicate dependency identifiers.
    """

    plan = build_plan(
        steps=(
            build_step("step-1"),
            build_step(
                "step-2",
                depends_on=("step-1", "step-1"),
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="duplicate dependencies",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_empty_dependency_id(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject an empty dependency identifier.
    """

    plan = build_plan(
        steps=(
            build_step("step-1"),
            build_step(
                "step-2",
                depends_on=("   ",),
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="empty dependency identifier",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_two_step_cycle(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject a two-step dependency cycle.
    """

    plan = build_plan(
        steps=(
            build_step(
                "step-1",
                depends_on=("step-2",),
            ),
            build_step(
                "step-2",
                depends_on=("step-1",),
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="dependency cycle",
    ):
        plan_validator.validate(plan)


def test_validate_rejects_multi_step_cycle(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject a dependency cycle containing multiple steps.
    """

    plan = build_plan(
        steps=(
            build_step(
                "step-1",
                depends_on=("step-3",),
            ),
            build_step(
                "step-2",
                depends_on=("step-1",),
            ),
            build_step(
                "step-3",
                depends_on=("step-2",),
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="dependency cycle",
    ):
        plan_validator.validate(plan)


def test_validate_does_not_use_stage_as_dependency(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Stage is metadata and must not create dependencies.
    """

    plan = build_plan(
        mode=ExecutionModeEnum.HYBRID,
        steps=(
            build_step(
                "step-1",
                stage=1,
            ),
            build_step(
                "step-2",
                stage=2,
            ),
        ),
    )

    assert plan_validator.validate(plan) is plan
