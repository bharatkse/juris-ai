from datetime import UTC, datetime, timedelta

import pytest

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.lifecycle import AgentLifecycle
from agentic.agents.runtime.lifecycle.state import AgentState
from agentic.agents.runtime.lifecycle.termination import (
    AgentExecutionStatus,
    TerminationReason,
)


def build_state(
    *,
    budget: AgentExecutionBudget | None = None,
    started_at: datetime | None = None,
    **kwargs,
) -> AgentState:
    return AgentState(
        budget=budget or AgentExecutionBudget(),
        started_at=started_at or datetime.now(UTC),
        **kwargs,
    )


def test_lifecycle_requires_agent_state():
    with pytest.raises(TypeError, match="state must be an AgentState"):
        AgentLifecycle(state=None)


def test_lifecycle_state_property():
    state = build_state()

    lifecycle = AgentLifecycle(state=state)

    assert lifecycle.state is state


def test_lifecycle_deadline():
    started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    budget = AgentExecutionBudget(max_execution_time_seconds=30)
    state = build_state(budget=budget, started_at=started_at)

    lifecycle = AgentLifecycle(state=state)

    assert lifecycle.deadline == started_at + timedelta(seconds=30)


def test_check_time_delegates_to_guard():
    started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    budget = AgentExecutionBudget(max_execution_time_seconds=10)
    state = build_state(budget=budget, started_at=started_at)
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.check_time(
        now=started_at + timedelta(seconds=5),
    )

    assert result.allowed is True


def test_begin_iteration_increments_after_allowed_check():
    budget = AgentExecutionBudget(max_iterations=3)
    state = build_state(budget=budget)
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_iteration()

    assert result.allowed is True
    assert state.iteration_count == 1
    assert state.status is AgentExecutionStatus.RUNNING


def test_begin_iteration_denies_at_limit_without_increment():
    budget = AgentExecutionBudget(max_iterations=2)
    state = build_state(
        budget=budget,
        iteration_count=2,
    )
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_iteration()

    assert result.allowed is False
    assert result.reason is TerminationReason.PARTIAL_MAX_ITERATIONS
    assert state.iteration_count == 2
    assert state.status is AgentExecutionStatus.PARTIAL
    assert state.termination_reason is TerminationReason.PARTIAL_MAX_ITERATIONS


def test_begin_tool_call_increments_after_allowed_check():
    budget = AgentExecutionBudget(max_tool_calls=2)
    state = build_state(budget=budget)
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_tool_call()

    assert result.allowed is True
    assert state.tool_call_count == 1


def test_begin_tool_call_denies_at_limit_without_increment():
    budget = AgentExecutionBudget(max_tool_calls=2)
    state = build_state(
        budget=budget,
        tool_call_count=2,
    )
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_tool_call()

    assert result.reason is TerminationReason.PARTIAL_MAX_TOOL_CALLS
    assert state.tool_call_count == 2
    assert state.status is AgentExecutionStatus.PARTIAL


def test_begin_agent_hop_increments_after_allowed_check():
    budget = AgentExecutionBudget(max_agent_hops=2)
    state = build_state(budget=budget)
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_agent_hop()

    assert result.allowed is True
    assert state.agent_hop_count == 1


def test_begin_agent_hop_denies_at_limit_without_increment():
    budget = AgentExecutionBudget(max_agent_hops=2)
    state = build_state(
        budget=budget,
        agent_hop_count=2,
    )
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_agent_hop()

    assert result.reason is TerminationReason.PARTIAL_MAX_AGENT_HOPS
    assert state.agent_hop_count == 2


def test_begin_step_increments_after_allowed_check():
    budget = AgentExecutionBudget(max_total_steps=2)
    state = build_state(budget=budget)
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_step()

    assert result.allowed is True
    assert state.total_step_count == 1


def test_begin_step_denies_at_limit_without_increment():
    budget = AgentExecutionBudget(max_total_steps=2)
    state = build_state(
        budget=budget,
        total_step_count=2,
    )
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_step()

    assert result.reason is TerminationReason.PARTIAL_MAX_TOTAL_STEPS
    assert state.total_step_count == 2


def test_begin_decision_increments_after_allowed_check():
    budget = AgentExecutionBudget(max_decisions=2)
    state = build_state(budget=budget)
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_decision()

    assert result.allowed is True
    assert state.decision_count == 1


def test_begin_decision_denies_at_limit_without_increment():
    budget = AgentExecutionBudget(max_decisions=2)
    state = build_state(
        budget=budget,
        decision_count=2,
    )
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_decision()

    assert result.reason is TerminationReason.PARTIAL_MAX_DECISIONS
    assert state.decision_count == 2


def test_begin_validation_increments_after_allowed_check():
    budget = AgentExecutionBudget(max_validation_attempts=2)
    state = build_state(budget=budget)
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_validation()

    assert result.allowed is True
    assert state.validation_attempt_count == 1


def test_begin_validation_denies_at_limit_without_increment():
    budget = AgentExecutionBudget(max_validation_attempts=2)
    state = build_state(
        budget=budget,
        validation_attempt_count=2,
    )
    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_validation()

    assert result.reason is TerminationReason.PARTIAL_VALIDATION_LIMIT
    assert state.validation_attempt_count == 2


@pytest.mark.parametrize(
    ("method", "field", "limit_field", "reason"),
    [
        (
            "record_evidence",
            "evidence_count",
            "max_evidence_items",
            TerminationReason.PARTIAL_MAX_EVIDENCE_ITEMS,
        ),
        (
            "record_context",
            "context_count",
            "max_context_items",
            TerminationReason.PARTIAL_MAX_CONTEXT_ITEMS,
        ),
        (
            "record_tool_result",
            "tool_result_count",
            "max_tool_result_records",
            TerminationReason.PARTIAL_MAX_TOOL_RESULTS,
        ),
    ],
)
def test_record_collection_allows_within_limit(
    method,
    field,
    limit_field,
    reason,
):
    budget = AgentExecutionBudget(**{limit_field: 3})
    lifecycle = AgentLifecycle(
        state=build_state(budget=budget),
    )

    result = getattr(lifecycle, method)(count=2)

    assert result.allowed is True
    assert getattr(lifecycle.state, field) == 2
    assert lifecycle.state.status is AgentExecutionStatus.RUNNING


@pytest.mark.parametrize(
    ("method", "field", "limit_field", "reason"),
    [
        (
            "record_evidence",
            "evidence_count",
            "max_evidence_items",
            TerminationReason.PARTIAL_MAX_EVIDENCE_ITEMS,
        ),
        (
            "record_context",
            "context_count",
            "max_context_items",
            TerminationReason.PARTIAL_MAX_CONTEXT_ITEMS,
        ),
        (
            "record_tool_result",
            "tool_result_count",
            "max_tool_result_records",
            TerminationReason.PARTIAL_MAX_TOOL_RESULTS,
        ),
    ],
)
def test_record_collection_denies_when_new_count_exceeds_limit(
    method,
    field,
    limit_field,
    reason,
):
    budget = AgentExecutionBudget(**{limit_field: 3})
    lifecycle = AgentLifecycle(
        state=build_state(
            budget=budget,
            **{field: 2},
        ),
    )

    result = getattr(lifecycle, method)(count=2)

    assert result.allowed is False
    assert result.reason is reason
    assert getattr(lifecycle.state, field) == 2
    assert lifecycle.state.status is AgentExecutionStatus.PARTIAL
    assert lifecycle.state.termination_reason is reason


@pytest.mark.parametrize(
    "method",
    ["record_evidence", "record_context", "record_tool_result"],
)
def test_record_collection_rejects_non_positive_count(method):
    lifecycle = AgentLifecycle(state=build_state())

    with pytest.raises(ValueError, match="count must be greater than zero"):
        getattr(lifecycle, method)(count=0)

    with pytest.raises(ValueError, match="count must be greater than zero"):
        getattr(lifecycle, method)(count=-1)


def test_record_action_first_action():
    lifecycle = AgentLifecycle(state=build_state())

    result = lifecycle.record_action("search")

    assert result.allowed is True
    assert lifecycle.state.last_action_key == "search"
    # LoopBreaker counts repeats, so the first action is not a repeat.
    assert lifecycle.state.repeated_action_count == 0


def test_record_action_repeated_action_increments_count():
    budget = AgentExecutionBudget(max_repeated_action=3)
    lifecycle = AgentLifecycle(state=build_state(budget=budget))

    lifecycle.record_action("search")
    result = lifecycle.record_action("search")

    assert result.allowed is True
    assert lifecycle.state.last_action_key == "search"
    # The second identical action is the first repeat.
    assert lifecycle.state.repeated_action_count == 1


def test_record_action_denies_at_repeat_limit():
    budget = AgentExecutionBudget(max_repeated_action=2)
    lifecycle = AgentLifecycle(state=build_state(budget=budget))

    assert lifecycle.record_action("search").allowed is True
    assert lifecycle.record_action("search").allowed is True
    result = lifecycle.record_action("search")

    assert result.allowed is False
    assert result.reason is TerminationReason.PARTIAL_REPEATED_ACTION
    assert lifecycle.state.repeated_action_count == 2
    assert lifecycle.state.status is AgentExecutionStatus.PARTIAL


def test_record_action_new_action_resets_count():
    budget = AgentExecutionBudget(max_repeated_action=3)
    lifecycle = AgentLifecycle(state=build_state(budget=budget))

    lifecycle.record_action("search")
    lifecycle.record_action("search")
    result = lifecycle.record_action("different")

    assert result.allowed is True
    assert lifecycle.state.last_action_key == "different"
    # A new action starts a new repeat streak at zero.
    assert lifecycle.state.repeated_action_count == 0


def test_record_action_rejects_empty_key():
    lifecycle = AgentLifecycle(state=build_state())

    with pytest.raises(ValueError, match="action_key must not be empty"):
        lifecycle.record_action("")


def test_set_partial_response_stores_response():
    lifecycle = AgentLifecycle(state=build_state())

    lifecycle.set_partial_response("The answer is available.")

    assert lifecycle.state.partial_response == "The answer is available."


def test_set_partial_response_ignores_none():
    lifecycle = AgentLifecycle(
        state=build_state(partial_response="Existing response"),
    )

    lifecycle.set_partial_response(None)

    assert lifecycle.state.partial_response == "Existing response"


def test_set_partial_response_truncates_to_budget():
    budget = AgentExecutionBudget(max_partial_response_chars=5)
    lifecycle = AgentLifecycle(state=build_state(budget=budget))

    lifecycle.set_partial_response("123456789")

    assert lifecycle.state.partial_response == "12345"


@pytest.mark.parametrize("value", [123, object(), [], {}])
def test_set_partial_response_rejects_non_string(value):
    lifecycle = AgentLifecycle(state=build_state())

    with pytest.raises(TypeError, match="partial response must be a string"):
        lifecycle.set_partial_response(value)


def test_complete_marks_execution_completed():
    lifecycle = AgentLifecycle(state=build_state())

    result = lifecycle.complete()

    assert result is None
    assert lifecycle.state.status is AgentExecutionStatus.COMPLETED
    assert lifecycle.state.termination_reason is TerminationReason.COMPLETED


@pytest.mark.parametrize(
    "reason",
    [
        TerminationReason.FAILED_TOOL,
        TerminationReason.FAILED_LLM,
        TerminationReason.FAILED_VALIDATION,
        TerminationReason.FAILED_POLICY,
    ],
)
def test_fail_accepts_failed_reason(reason):
    lifecycle = AgentLifecycle(state=build_state())

    result = lifecycle.fail(reason)

    assert result is None
    assert lifecycle.state.status is AgentExecutionStatus.FAILED
    assert lifecycle.state.termination_reason is reason


@pytest.mark.parametrize(
    "reason",
    [
        TerminationReason.COMPLETED,
        TerminationReason.PARTIAL_TIMEOUT,
        TerminationReason.USER_INPUT_REQUIRED,
    ],
)
def test_fail_rejects_non_failed_reason(reason):
    lifecycle = AgentLifecycle(state=build_state())

    with pytest.raises(
        ValueError,
        match=r"reason must be a FAILED_\* termination reason",
    ):
        lifecycle.fail(reason)

    assert lifecycle.state.status is AgentExecutionStatus.RUNNING
    assert lifecycle.state.termination_reason is None


def test_user_input_required_marks_partial():
    lifecycle = AgentLifecycle(state=build_state())

    result = lifecycle.user_input_required()

    assert result is None
    assert lifecycle.state.status is AgentExecutionStatus.PARTIAL
    assert lifecycle.state.termination_reason is TerminationReason.USER_INPUT_REQUIRED


def test_partial_marks_partial():
    lifecycle = AgentLifecycle(state=build_state())

    result = lifecycle.partial(TerminationReason.PARTIAL_TIMEOUT)

    assert result is None
    assert lifecycle.state.status is AgentExecutionStatus.PARTIAL
    assert lifecycle.state.termination_reason is TerminationReason.PARTIAL_TIMEOUT


def test_begin_iteration_timeout_is_checked_before_iteration_budget():
    started_at = datetime.now(UTC) - timedelta(seconds=20)
    budget = AgentExecutionBudget(
        max_iterations=1,
        max_execution_time_seconds=10,
    )
    state = build_state(
        budget=budget,
        started_at=started_at,
        iteration_count=1,
    )

    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_iteration()

    assert result.allowed is False
    assert result.reason is TerminationReason.PARTIAL_TIMEOUT
    assert state.iteration_count == 1
    assert state.termination_reason is TerminationReason.PARTIAL_TIMEOUT


def test_begin_tool_call_timeout_is_checked_before_tool_budget():
    started_at = datetime.now(UTC) - timedelta(seconds=20)
    budget = AgentExecutionBudget(
        max_tool_calls=1,
        max_execution_time_seconds=10,
    )
    state = build_state(
        budget=budget,
        started_at=started_at,
        tool_call_count=1,
    )

    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_tool_call()

    assert result.reason is TerminationReason.PARTIAL_TIMEOUT
    assert state.tool_call_count == 1


def test_begin_agent_hop_timeout_is_checked_before_hop_budget():
    started_at = datetime.now(UTC) - timedelta(seconds=20)
    budget = AgentExecutionBudget(
        max_agent_hops=1,
        max_execution_time_seconds=10,
    )
    state = build_state(
        budget=budget,
        started_at=started_at,
        agent_hop_count=1,
    )

    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_agent_hop()

    assert result.reason is TerminationReason.PARTIAL_TIMEOUT
    assert state.agent_hop_count == 1


def test_begin_step_timeout_is_checked_before_step_budget():
    started_at = datetime.now(UTC) - timedelta(seconds=20)
    budget = AgentExecutionBudget(
        max_total_steps=1,
        max_execution_time_seconds=10,
    )
    state = build_state(
        budget=budget,
        started_at=started_at,
        total_step_count=1,
    )

    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_step()

    assert result.reason is TerminationReason.PARTIAL_TIMEOUT
    assert state.total_step_count == 1


def test_begin_decision_timeout_is_checked_before_decision_budget():
    started_at = datetime.now(UTC) - timedelta(seconds=20)
    budget = AgentExecutionBudget(
        max_decisions=1,
        max_execution_time_seconds=10,
    )
    state = build_state(
        budget=budget,
        started_at=started_at,
        decision_count=1,
    )

    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_decision()

    assert result.reason is TerminationReason.PARTIAL_TIMEOUT
    assert state.decision_count == 1


def test_begin_validation_timeout_is_checked_before_validation_budget():
    started_at = datetime.now(UTC) - timedelta(seconds=20)
    budget = AgentExecutionBudget(
        max_validation_attempts=1,
        max_execution_time_seconds=10,
    )
    state = build_state(
        budget=budget,
        started_at=started_at,
        validation_attempt_count=1,
    )

    lifecycle = AgentLifecycle(state=state)

    result = lifecycle.begin_validation()

    assert result.reason is TerminationReason.PARTIAL_TIMEOUT
    assert state.validation_attempt_count == 1
