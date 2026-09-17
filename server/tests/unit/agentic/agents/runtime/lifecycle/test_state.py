from datetime import UTC, datetime

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.state import AgentState
from agentic.agents.runtime.lifecycle.termination import (
    AgentExecutionStatus,
    TerminationReason,
)


def build_state(**kwargs) -> AgentState:
    return AgentState(
        budget=kwargs.pop("budget", AgentExecutionBudget()),
        started_at=kwargs.pop(
            "started_at",
            datetime.now(UTC),
        ),
        **kwargs,
    )


def test_agent_state_requires_budget():
    try:
        AgentState(
            budget=None,
            started_at=datetime.now(UTC),
        )
    except TypeError:
        pass


def test_agent_state_requires_started_at():
    try:
        AgentState(
            budget=AgentExecutionBudget(),
            started_at=None,
        )
    except TypeError:
        pass


def test_agent_state_defaults():
    state = build_state()

    assert state.status is AgentExecutionStatus.RUNNING
    assert state.termination_reason is None

    assert state.iteration_count == 0
    assert state.tool_call_count == 0
    assert state.agent_hop_count == 0
    assert state.total_step_count == 0
    assert state.decision_count == 0
    assert state.validation_attempt_count == 0

    assert state.evidence_count == 0
    assert state.context_count == 0
    assert state.tool_result_count == 0

    assert state.repeated_action_count == 0
    assert state.last_action_key is None
    assert state.partial_response == ""


def test_agent_state_preserves_budget():
    budget = AgentExecutionBudget(
        max_iterations=3,
        max_tool_calls=4,
        max_agent_hops=5,
    )

    state = build_state(budget=budget)

    assert state.budget is budget


def test_agent_state_preserves_started_at():
    started_at = datetime(
        2026,
        1,
        1,
        12,
        0,
        tzinfo=UTC,
    )

    state = build_state(started_at=started_at)

    assert state.started_at is started_at


def test_agent_state_accepts_custom_status():
    state = build_state(
        status=AgentExecutionStatus.PARTIAL,
        termination_reason=TerminationReason.PARTIAL_TIMEOUT,
    )

    assert state.status is AgentExecutionStatus.PARTIAL
    assert state.termination_reason is TerminationReason.PARTIAL_TIMEOUT


def test_agent_state_accepts_failed_status():
    state = build_state(
        status=AgentExecutionStatus.FAILED,
        termination_reason=TerminationReason.FAILED_LLM,
    )

    assert state.status is AgentExecutionStatus.FAILED
    assert state.termination_reason is TerminationReason.FAILED_LLM


def test_agent_state_accepts_custom_execution_counters():
    state = build_state(
        iteration_count=2,
        tool_call_count=3,
        agent_hop_count=1,
        total_step_count=6,
        decision_count=4,
        validation_attempt_count=2,
    )

    assert state.iteration_count == 2
    assert state.tool_call_count == 3
    assert state.agent_hop_count == 1
    assert state.total_step_count == 6
    assert state.decision_count == 4
    assert state.validation_attempt_count == 2


def test_agent_state_accepts_custom_collection_counters():
    state = build_state(
        evidence_count=10,
        context_count=20,
        tool_result_count=5,
    )

    assert state.evidence_count == 10
    assert state.context_count == 20
    assert state.tool_result_count == 5


def test_agent_state_accepts_repeated_action_tracking():
    state = build_state(
        repeated_action_count=2,
        last_action_key="search:contract",
    )

    assert state.repeated_action_count == 2
    assert state.last_action_key == "search:contract"


def test_agent_state_accepts_partial_response():
    response = "The agreement requires thirty days' notice."

    state = build_state(
        partial_response=response,
    )

    assert state.partial_response == response


def test_agent_state_is_mutable():
    state = build_state()

    state.iteration_count = 3
    state.status = AgentExecutionStatus.PARTIAL
    state.termination_reason = TerminationReason.PARTIAL_TIMEOUT
    state.partial_response = "Partial answer."

    assert state.iteration_count == 3
    assert state.status is AgentExecutionStatus.PARTIAL
    assert state.termination_reason is TerminationReason.PARTIAL_TIMEOUT
    assert state.partial_response == "Partial answer."


def test_agent_state_instances_do_not_share_mutable_runtime_state():
    first = build_state()
    second = build_state()

    first.iteration_count = 5
    first.partial_response = "First response"
    first.last_action_key = "first"
    first.repeated_action_count = 2

    assert second.iteration_count == 0
    assert second.partial_response == ""
    assert second.last_action_key is None
    assert second.repeated_action_count == 0


def test_agent_state_slots_prevent_arbitrary_attributes():
    state = build_state()

    try:
        state.unexpected_attribute = "value"
    except AttributeError:
        pass
    else:
        raise AssertionError(
            "AgentState should reject attributes outside its slots.",
        )


def test_agent_state_repr_does_not_expose_last_action_key():
    state = build_state(
        last_action_key="sensitive-action-key",
    )

    representation = repr(state)

    assert "last_action_key" not in representation
    assert "sensitive-action-key" not in representation


def test_agent_state_can_transition_from_running_to_completed():
    state = build_state()

    state.status = AgentExecutionStatus.COMPLETED
    state.termination_reason = TerminationReason.COMPLETED

    assert state.status is AgentExecutionStatus.COMPLETED
    assert state.termination_reason is TerminationReason.COMPLETED


def test_agent_state_can_transition_from_running_to_failed():
    state = build_state()

    state.status = AgentExecutionStatus.FAILED
    state.termination_reason = TerminationReason.FAILED_POLICY

    assert state.status is AgentExecutionStatus.FAILED
    assert state.termination_reason is TerminationReason.FAILED_POLICY
