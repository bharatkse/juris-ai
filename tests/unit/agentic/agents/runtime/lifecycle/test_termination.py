import pytest

from agentic.agents.runtime.lifecycle.termination import (
    AgentExecutionStatus,
    AgentTerminator,
    TerminationReason,
)


def test_complete_marks_execution_completed():
    state = type("State", (), {})()
    state.status = AgentExecutionStatus.RUNNING
    state.termination_reason = None

    result = AgentTerminator().complete(state=state)

    assert result is state
    assert state.status is AgentExecutionStatus.COMPLETED
    assert state.termination_reason is TerminationReason.COMPLETED


@pytest.mark.parametrize(
    "reason",
    [
        TerminationReason.PARTIAL_MAX_ITERATIONS,
        TerminationReason.PARTIAL_MAX_TOOL_CALLS,
        TerminationReason.PARTIAL_MAX_AGENT_HOPS,
        TerminationReason.PARTIAL_MAX_TOTAL_STEPS,
        TerminationReason.PARTIAL_MAX_DECISIONS,
        TerminationReason.PARTIAL_MAX_EVIDENCE_ITEMS,
        TerminationReason.PARTIAL_MAX_CONTEXT_ITEMS,
        TerminationReason.PARTIAL_MAX_TOOL_RESULTS,
        TerminationReason.PARTIAL_TIMEOUT,
        TerminationReason.PARTIAL_REPEATED_ACTION,
        TerminationReason.PARTIAL_VALIDATION_LIMIT,
    ],
)
def test_partial_marks_execution_partial(reason):
    state = type("State", (), {})()
    state.status = AgentExecutionStatus.RUNNING
    state.termination_reason = None

    result = AgentTerminator().partial(state=state, reason=reason)

    assert result is state
    assert state.status is AgentExecutionStatus.PARTIAL
    assert state.termination_reason is reason


@pytest.mark.parametrize(
    "reason",
    [
        TerminationReason.FAILED_TOOL,
        TerminationReason.FAILED_LLM,
        TerminationReason.FAILED_VALIDATION,
        TerminationReason.FAILED_POLICY,
    ],
)
def test_fail_marks_execution_failed(reason):
    state = type("State", (), {})()
    state.status = AgentExecutionStatus.RUNNING
    state.termination_reason = None

    result = AgentTerminator().fail(state=state, reason=reason)

    assert result is state
    assert state.status is AgentExecutionStatus.FAILED
    assert state.termination_reason is reason


def test_user_input_required_marks_execution_partial():
    state = type("State", (), {})()
    state.status = AgentExecutionStatus.RUNNING
    state.termination_reason = None

    result = AgentTerminator().user_input_required(state=state)

    assert result is state
    assert state.status is AgentExecutionStatus.PARTIAL
    assert state.termination_reason is TerminationReason.USER_INPUT_REQUIRED


def test_terminator_is_stateless():
    terminator = AgentTerminator()

    state_one = type("State", (), {})()
    state_one.status = AgentExecutionStatus.RUNNING
    state_one.termination_reason = None

    state_two = type("State", (), {})()
    state_two.status = AgentExecutionStatus.RUNNING
    state_two.termination_reason = None

    terminator.complete(state=state_one)
    terminator.fail(
        state=state_two,
        reason=TerminationReason.FAILED_LLM,
    )

    assert state_one.status is AgentExecutionStatus.COMPLETED
    assert state_one.termination_reason is TerminationReason.COMPLETED
    assert state_two.status is AgentExecutionStatus.FAILED
    assert state_two.termination_reason is TerminationReason.FAILED_LLM
