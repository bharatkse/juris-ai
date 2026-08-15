"""
Unit tests for execution state assembly.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.core.enums import ExecutionStatusEnum
from src.execution.graph.state import ExecutionArtifactUpdate, ExecutionStepUpdate
from src.execution.schemas.state import ExecutionStateSchema
from src.execution.state.assembler import ExecutionStateAssembler
from tests.builders.execution import build_graph_state
from tests.builders.planning import build_plan, build_step


def test_assemble_state_with_no_updates() -> None:
    """
    It should create a pending execution state when no updates exist.
    """

    assembler = ExecutionStateAssembler()

    graph_state = build_graph_state(
        plan=build_plan(
            steps=(),
        ),
    )

    result = assembler.assemble_state(
        graph_state=graph_state,
    )

    assert isinstance(
        result,
        ExecutionStateSchema,
    )

    assert str(result.request_id) == graph_state["request_id"]
    assert result.status is ExecutionStatusEnum.PENDING
    assert result.steps == {}


def test_assemble_state_with_completed_step() -> None:
    """
    It should assemble a completed step.
    """

    started_at = datetime.now(UTC)
    completed_at = datetime.now(UTC)

    graph_state = build_graph_state(
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=0,
                started_at=started_at,
                completed_at=completed_at,
                error=None,
            ),
        ],
    )

    assembler = ExecutionStateAssembler()

    result = assembler.assemble_state(
        graph_state=graph_state,
    )

    assert result.status is ExecutionStatusEnum.COMPLETED

    step = result.steps["step-a"]

    assert step.step_id == "step-a"
    assert step.status is ExecutionStatusEnum.COMPLETED
    assert step.retry_count == 0
    assert step.started_at == started_at
    assert step.completed_at == completed_at
    assert step.error is None


def test_assemble_state_with_failed_step() -> None:
    """
    It should mark the execution as failed when a step fails.
    """

    started_at = datetime.now(UTC)
    completed_at = datetime.now(UTC)

    graph_state = build_graph_state(
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.FAILED,
                retry_count=2,
                started_at=started_at,
                completed_at=completed_at,
                error="Simulated failure",
            ),
        ],
    )

    assembler = ExecutionStateAssembler()

    result = assembler.assemble_state(
        graph_state=graph_state,
    )

    assert result.status is ExecutionStatusEnum.FAILED

    step = result.steps["step-a"]

    assert step.status is ExecutionStatusEnum.FAILED
    assert step.retry_count == 2
    assert step.error == "Simulated failure"


def test_assemble_state_with_completed_and_skipped_steps() -> None:
    """
    It should mark execution as completed when all steps are
    either completed or skipped.
    """

    graph_state = build_graph_state(
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=0,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error=None,
            ),
            ExecutionStepUpdate(
                step_id="step-b",
                status=ExecutionStatusEnum.SKIPPED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error="Dependency failed.",
            ),
        ],
        plan=build_plan(
            steps=(
                build_step("step-a"),
                build_step(
                    "step-b",
                    depends_on=("step-a",),
                ),
            ),
        ),
    )

    assembler = ExecutionStateAssembler()

    result = assembler.assemble_state(
        graph_state=graph_state,
    )

    assert result.status is ExecutionStatusEnum.COMPLETED
    assert result.steps["step-a"].status is ExecutionStatusEnum.COMPLETED
    assert result.steps["step-b"].status is ExecutionStatusEnum.SKIPPED


def test_assemble_state_with_failed_and_skipped_steps() -> None:
    """
    It should mark execution as failed when any step fails,
    even when dependent steps are skipped.
    """

    graph_state = build_graph_state(
        plan=build_plan(
            steps=(
                build_step("step-a"),
                build_step(
                    "step-b",
                    depends_on=("step-a",),
                ),
            ),
        ),
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.FAILED,
                retry_count=2,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error="Simulated failure",
            ),
            ExecutionStepUpdate(
                step_id="step-b",
                status=ExecutionStatusEnum.SKIPPED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error="Dependency failed.",
            ),
        ],
    )

    assembler = ExecutionStateAssembler()

    result = assembler.assemble_state(
        graph_state=graph_state,
    )

    assert result.status is ExecutionStatusEnum.FAILED


def test_assemble_memory() -> None:
    """
    It should assemble execution artifacts from graph updates.
    """

    graph_state = build_graph_state(
        memory_updates=[
            ExecutionArtifactUpdate(
                key="step-a.response",
                value="Executed A",
            ),
            ExecutionArtifactUpdate(
                key="step-b.response",
                value="Executed B",
            ),
        ],
    )

    assembler = ExecutionStateAssembler()

    result = assembler.assemble_memory(
        graph_state=graph_state,
    )

    assert result.artifacts == {
        "step-a.response": "Executed A",
        "step-b.response": "Executed B",
    }
