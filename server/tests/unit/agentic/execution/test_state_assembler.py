"""
Unit tests for ExecutionStateAssembler.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from agentic.execution.graph.state import ExecutionArtifactUpdate, ExecutionStepUpdate
from agentic.execution.schemas.memory import ExecutionMemorySchema
from agentic.execution.schemas.state import ExecutionStateSchema
from agentic.execution.state.assembler import ExecutionStateAssembler
from core.enums import ExecutionStatusEnum
from tests.builders.agentic.execution import build_graph_state
from tests.builders.agentic.planning import build_plan, build_step


@pytest.fixture
def assembler() -> ExecutionStateAssembler:
    return ExecutionStateAssembler()


def test_assemble_state_with_no_steps_returns_pending(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(
        plan=build_plan(steps=()),
        execution_state_updates=[],
    )

    result = assembler.assemble_state(graph_state=graph_state)

    assert isinstance(result, ExecutionStateSchema)
    assert str(result.request_id) == graph_state["request_id"]
    assert result.status is ExecutionStatusEnum.PENDING
    assert result.steps == {}


def test_assemble_state_registers_plan_steps(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(
        plan=build_plan(
            steps=(
                build_step("step-a"),
                build_step("step-b"),
            ),
        ),
        execution_state_updates=[],
    )

    result = assembler.assemble_state(graph_state=graph_state)

    assert set(result.steps) == {"step-a", "step-b"}
    assert result.steps["step-a"].step_id == "step-a"
    assert result.steps["step-b"].step_id == "step-b"
    assert result.status is ExecutionStatusEnum.PENDING


def test_assemble_state_applies_step_update_fields(
    assembler: ExecutionStateAssembler,
) -> None:
    started_at = datetime.now(UTC)
    completed_at = datetime.now(UTC)

    graph_state = build_graph_state(
        plan=build_plan(steps=(build_step("step-a"),)),
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=2,
                started_at=started_at,
                completed_at=completed_at,
                error=None,
                termination_reason=None,
            ),
        ],
    )

    result = assembler.assemble_state(graph_state=graph_state)
    step = result.steps["step-a"]

    assert step.step_id == "step-a"
    assert step.status is ExecutionStatusEnum.COMPLETED
    assert step.retry_count == 2
    assert step.started_at == started_at
    assert step.completed_at == completed_at
    assert step.error is None
    assert step.termination_reason is None


@pytest.mark.parametrize(
    ("status", "expected_execution_status"),
    [
        (ExecutionStatusEnum.COMPLETED, ExecutionStatusEnum.COMPLETED),
        (ExecutionStatusEnum.SKIPPED, ExecutionStatusEnum.COMPLETED),
        (ExecutionStatusEnum.PARTIAL, ExecutionStatusEnum.PARTIAL),
        (ExecutionStatusEnum.FAILED, ExecutionStatusEnum.FAILED),
    ],
)
def test_assemble_state_derives_status_from_single_step(
    assembler: ExecutionStateAssembler,
    status: ExecutionStatusEnum,
    expected_execution_status: ExecutionStatusEnum,
) -> None:
    graph_state = build_graph_state(
        plan=build_plan(steps=(build_step("step-a"),)),
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=status,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error=None,
                termination_reason=None,
            ),
        ],
    )

    result = assembler.assemble_state(graph_state=graph_state)

    assert result.status is expected_execution_status


def test_assemble_state_failed_takes_precedence_over_partial(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(
        plan=build_plan(
            steps=(
                build_step("step-a"),
                build_step("step-b"),
            ),
        ),
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.PARTIAL,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error="Partial result",
                termination_reason=None,
            ),
            ExecutionStepUpdate(
                step_id="step-b",
                status=ExecutionStatusEnum.FAILED,
                retry_count=1,
                started_at=None,
                completed_at=None,
                error="Simulated failure",
                termination_reason=None,
            ),
        ],
    )

    result = assembler.assemble_state(graph_state=graph_state)

    assert result.status is ExecutionStatusEnum.FAILED


def test_assemble_state_failed_takes_precedence_over_completed(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(
        plan=build_plan(
            steps=(
                build_step("step-a"),
                build_step("step-b"),
            ),
        ),
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error=None,
                termination_reason=None,
            ),
            ExecutionStepUpdate(
                step_id="step-b",
                status=ExecutionStatusEnum.FAILED,
                retry_count=1,
                started_at=None,
                completed_at=None,
                error="Simulated failure",
                termination_reason=None,
            ),
        ],
    )

    result = assembler.assemble_state(graph_state=graph_state)

    assert result.status is ExecutionStatusEnum.FAILED


def test_assemble_state_partial_takes_precedence_over_completed(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(
        plan=build_plan(
            steps=(
                build_step("step-a"),
                build_step("step-b"),
            ),
        ),
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error=None,
                termination_reason=None,
            ),
            ExecutionStepUpdate(
                step_id="step-b",
                status=ExecutionStatusEnum.PARTIAL,
                retry_count=1,
                started_at=None,
                completed_at=None,
                error="Partial result",
                termination_reason=None,
            ),
        ],
    )

    result = assembler.assemble_state(graph_state=graph_state)

    assert result.status is ExecutionStatusEnum.PARTIAL


def test_assemble_state_completed_when_all_steps_are_completed_or_skipped(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(
        plan=build_plan(
            steps=(
                build_step("step-a"),
                build_step("step-b", depends_on=("step-a",)),
            ),
        ),
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.COMPLETED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error=None,
                termination_reason=None,
            ),
            ExecutionStepUpdate(
                step_id="step-b",
                status=ExecutionStatusEnum.SKIPPED,
                retry_count=0,
                started_at=None,
                completed_at=None,
                error="Dependency skipped.",
                termination_reason=None,
            ),
        ],
    )

    result = assembler.assemble_state(graph_state=graph_state)

    assert result.status is ExecutionStatusEnum.COMPLETED


def test_assemble_state_preserves_termination_reason(
    assembler: ExecutionStateAssembler,
) -> None:
    termination_reason = "max_retries"

    graph_state = build_graph_state(
        plan=build_plan(steps=(build_step("step-a"),)),
        execution_state_updates=[
            ExecutionStepUpdate(
                step_id="step-a",
                status=ExecutionStatusEnum.PARTIAL,
                retry_count=3,
                started_at=None,
                completed_at=None,
                error="Retry limit reached.",
                termination_reason=termination_reason,
            ),
        ],
    )

    result = assembler.assemble_state(graph_state=graph_state)

    assert result.steps["step-a"].termination_reason == termination_reason


def test_assemble_memory_with_no_updates_returns_empty_memory(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(memory_updates=[])

    result = assembler.assemble_memory(graph_state=graph_state)

    assert isinstance(result, ExecutionMemorySchema)
    assert result.artifacts == {}


def test_assemble_memory_stores_all_artifacts(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(
        memory_updates=[
            ExecutionArtifactUpdate(
                key="step-a.response",
                value="Executed A",
            ),
            ExecutionArtifactUpdate(
                key="step-b.response",
                value={"result": "Executed B"},
            ),
        ],
    )

    result = assembler.assemble_memory(graph_state=graph_state)

    assert result.artifacts == {
        "step-a.response": "Executed A",
        "step-b.response": {"result": "Executed B"},
    }


def test_assemble_memory_preserves_duplicate_key_last_value(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state(
        memory_updates=[
            ExecutionArtifactUpdate(
                key="result",
                value="first",
            ),
            ExecutionArtifactUpdate(
                key="result",
                value="second",
            ),
        ],
    )

    result = assembler.assemble_memory(graph_state=graph_state)

    assert result.artifacts["result"] == "second"


def test_assemble_action_returns_proposed_action(
    assembler: ExecutionStateAssembler,
) -> None:
    action = object()

    # build_graph_state does not expose ``action`` as a builder argument.
    # The assembler itself only requires the graph state to provide the
    # optional ``action`` entry.
    graph_state = build_graph_state()
    graph_state["action"] = action

    result = assembler.assemble_action(graph_state=graph_state)

    assert result is action


def test_assemble_action_returns_none_when_no_action_exists(
    assembler: ExecutionStateAssembler,
) -> None:
    graph_state = build_graph_state()

    result = assembler.assemble_action(graph_state=graph_state)

    assert result is None
