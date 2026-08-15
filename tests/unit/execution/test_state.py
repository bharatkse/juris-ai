"""
Unit tests for execution runtime state.
"""

from __future__ import annotations

from src.core.enums import ExecutionStatusEnum
from src.execution.schemas.state import ExecutionStateSchema, StepExecutionStateSchema
from tests.helpers.identifiers import unknown_request_id


def test_step_execution_state_defaults() -> None:
    """
    It should initialize a step in the pending state.
    """

    state = StepExecutionStateSchema(
        step_id="step-a",
    )

    assert state.step_id == "step-a"
    assert state.status is ExecutionStatusEnum.PENDING
    assert state.retry_count == 0
    assert state.started_at is None
    assert state.completed_at is None
    assert state.error is None


def test_execution_state_defaults() -> None:
    """
    It should initialize execution state as pending.
    """

    state = ExecutionStateSchema(
        request_id=unknown_request_id(),
    )

    assert state.status is ExecutionStatusEnum.PENDING
    assert state.hop_count == 0
    assert state.retry_count == 0
    assert state.steps == {}
    assert state.created_at is not None


def test_register_step() -> None:
    """
    It should register a step in pending state.
    """

    state = ExecutionStateSchema(
        request_id=unknown_request_id(),
    )

    state.register_step(
        step_id="step-a",
    )

    assert "step-a" in state.steps

    step = state.steps["step-a"]

    assert step.step_id == "step-a"
    assert step.status is ExecutionStatusEnum.PENDING
    assert step.retry_count == 0
    assert step.started_at is None
    assert step.completed_at is None
    assert step.error is None


def test_start_step() -> None:
    """
    It should mark a registered step as running.
    """

    state = ExecutionStateSchema(
        request_id=unknown_request_id(),
    )

    state.register_step(
        step_id="step-a",
    )

    state.start_step(
        step_id="step-a",
    )

    step = state.steps["step-a"]

    assert step.status is ExecutionStatusEnum.RUNNING
    assert step.started_at is not None
    assert step.completed_at is None
    assert step.error is None


def test_complete_step() -> None:
    """
    It should mark a running step as completed.
    """

    state = ExecutionStateSchema(
        request_id=unknown_request_id(),
    )

    state.register_step(
        step_id="step-a",
    )

    state.start_step(
        step_id="step-a",
    )

    state.complete_step(
        step_id="step-a",
    )

    step = state.steps["step-a"]

    assert step.status is ExecutionStatusEnum.COMPLETED
    assert step.started_at is not None
    assert step.completed_at is not None
    assert step.error is None


def test_fail_step() -> None:
    """
    It should mark a running step as failed.
    """

    state = ExecutionStateSchema(
        request_id=unknown_request_id(),
    )

    state.register_step(
        step_id="step-a",
    )

    state.start_step(
        step_id="step-a",
    )

    state.fail_step(
        step_id="step-a",
        error="Simulated failure",
    )

    step = state.steps["step-a"]

    assert step.status is ExecutionStatusEnum.FAILED
    assert step.started_at is not None
    assert step.completed_at is not None
    assert step.error == "Simulated failure"
