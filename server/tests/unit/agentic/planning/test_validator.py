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

    step-2 and step-3 are independent siblings (both depend only on
    step-1, neither depends on the other), so they are given different
    agents -- two independent steps assigned the same agent is a
    separate, deliberately rejected shape (see the
    test_validate_rejects_* / test_validate_accepts_* agent-concurrency
    tests below). This test's own purpose is dependency-graph
    acceptance, not agent assignment.
    """

    plan = build_plan(
        steps=(
            build_step("step-1"),
            build_step(
                "step-2",
                agent=AgentTypeEnum.LEGAL,
                depends_on=("step-1",),
            ),
            build_step(
                "step-3",
                agent=AgentTypeEnum.CONTRACT,
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

    step-1 and step-2 have no depends_on relationship (only different
    stage numbers), so they are given different agents -- this test's
    purpose is confirming stage alone does not create an implicit
    dependency, not agent assignment (same-agent-on-independent-steps
    is covered separately below).
    """

    plan = build_plan(
        mode=ExecutionModeEnum.HYBRID,
        steps=(
            build_step(
                "step-1",
                agent=AgentTypeEnum.LEGAL,
                stage=1,
            ),
            build_step(
                "step-2",
                agent=AgentTypeEnum.CONTRACT,
                stage=2,
            ),
        ),
    )

    assert plan_validator.validate(plan) is plan


# ----------------------------------------------------------------------
# Agent concurrency -- the same agent must never be assigned to two
# steps that could execute at the same time (no depends_on relationship
# between them, in either direction). See validator.py's
# _validate_agent_concurrency docstring for the full rationale: this is
# the root cause of a real production DuplicateAgentResponseError --
# the planner produced a 2-step plan with both steps assigned to
# 'legal' and neither depending on the other, the executor ran both
# concurrently (correctly, per depends_on), both agent calls succeeded
# individually, and only the post-execution ResponseValidator caught
# the conflict -- after two real LLM calls had already run. These
# tests catch that plan shape here, before any agent is invoked.
# ----------------------------------------------------------------------


def test_validate_rejects_same_agent_on_independent_steps(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject the real production repro shape: two steps assigned the
    same agent, neither depending on the other.
    """

    plan = build_plan(
        steps=(
            build_step(
                "step-1",
                agent=AgentTypeEnum.LEGAL,
            ),
            build_step(
                "step-2",
                agent=AgentTypeEnum.LEGAL,
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="no dependency relationship between them",
    ):
        plan_validator.validate(plan)


def test_validate_accepts_same_agent_in_dependency_chain(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Accept the same agent appearing twice when the steps are connected
    by depends_on -- a later step building on what an earlier step
    using the same agent already produced (e.g. planning.md's
    "contract-analysis" -> "risk-analysis" example). This is a
    legitimate, deliberate pattern, not the shape the check above
    rejects -- the constraint is "can't run in parallel", not "can't
    appear twice in a plan at all".
    """

    plan = build_plan(
        steps=(
            build_step(
                "contract-analysis",
                agent=AgentTypeEnum.CONTRACT,
            ),
            build_step(
                "risk-analysis",
                agent=AgentTypeEnum.CONTRACT,
                depends_on=("contract-analysis",),
            ),
        ),
    )

    assert plan_validator.validate(plan) is plan


def test_validate_rejects_same_agent_on_unordered_siblings_sharing_an_ancestor(
    plan_validator: ExecutionPlanValidator,
) -> None:
    """
    Reject the same agent on two steps that share a common ancestor
    but are not ordered relative to EACH OTHER -- both still depend
    only on step-1, and could still execute concurrently with each
    other once step-1 completes, so sharing an ancestor is not enough
    to make them safe.
    """

    plan = build_plan(
        steps=(
            build_step(
                "step-1",
                agent=AgentTypeEnum.CONTRACT,
            ),
            build_step(
                "step-2",
                agent=AgentTypeEnum.LEGAL,
                depends_on=("step-1",),
            ),
            build_step(
                "step-3",
                agent=AgentTypeEnum.LEGAL,
                depends_on=("step-1",),
            ),
        ),
    )

    with pytest.raises(
        PlanValidationError,
        match="no dependency relationship between them",
    ):
        plan_validator.validate(plan)
