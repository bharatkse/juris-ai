from datetime import UTC, datetime, timedelta

import pytest

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.guard import (
    BudgetCheckResult,
    BudgetCheckStatus,
    BudgetGuard,
)
from agentic.agents.runtime.lifecycle.termination import TerminationReason


def test_budget_guard_requires_agent_execution_budget():
    with pytest.raises(TypeError, match="budget must be an AgentExecutionBudget"):
        BudgetGuard(None)


@pytest.mark.parametrize(
    ("method", "argument", "budget_field", "reason"),
    [
        (
            "check_iteration",
            "iteration_count",
            "max_iterations",
            TerminationReason.PARTIAL_MAX_ITERATIONS,
        ),
        (
            "check_tool_call",
            "tool_call_count",
            "max_tool_calls",
            TerminationReason.PARTIAL_MAX_TOOL_CALLS,
        ),
        (
            "check_agent_hop",
            "agent_hop_count",
            "max_agent_hops",
            TerminationReason.PARTIAL_MAX_AGENT_HOPS,
        ),
        (
            "check_total_step",
            "total_step_count",
            "max_total_steps",
            TerminationReason.PARTIAL_MAX_TOTAL_STEPS,
        ),
        (
            "check_decisions",
            "decision_count",
            "max_decisions",
            TerminationReason.PARTIAL_MAX_DECISIONS,
        ),
        (
            "check_evidence",
            "evidence_count",
            "max_evidence_items",
            TerminationReason.PARTIAL_MAX_EVIDENCE_ITEMS,
        ),
        (
            "check_context",
            "context_count",
            "max_context_items",
            TerminationReason.PARTIAL_MAX_CONTEXT_ITEMS,
        ),
        (
            "check_tool_result",
            "tool_result_count",
            "max_tool_result_records",
            TerminationReason.PARTIAL_MAX_TOOL_RESULTS,
        ),
        (
            "check_repeated_action",
            "repeat_count",
            "max_repeated_action",
            TerminationReason.PARTIAL_REPEATED_ACTION,
        ),
        (
            "check_rejected_decisions",
            "rejected_decision_count",
            "max_rejected_decisions",
            TerminationReason.PARTIAL_REJECTED_DECISION_LIMIT,
        ),
    ],
)
def test_count_checks_allow_below_limit(
    method,
    argument,
    budget_field,
    reason,
):
    budget = AgentExecutionBudget(**{budget_field: 3})
    guard = BudgetGuard(budget)

    result = getattr(guard, method)(**{argument: 2})

    assert result.status is BudgetCheckStatus.ALLOWED
    assert result.allowed is True
    assert result.reason is None


@pytest.mark.parametrize(
    ("method", "argument", "budget_field", "reason"),
    [
        (
            "check_iteration",
            "iteration_count",
            "max_iterations",
            TerminationReason.PARTIAL_MAX_ITERATIONS,
        ),
        (
            "check_tool_call",
            "tool_call_count",
            "max_tool_calls",
            TerminationReason.PARTIAL_MAX_TOOL_CALLS,
        ),
        (
            "check_agent_hop",
            "agent_hop_count",
            "max_agent_hops",
            TerminationReason.PARTIAL_MAX_AGENT_HOPS,
        ),
        (
            "check_total_step",
            "total_step_count",
            "max_total_steps",
            TerminationReason.PARTIAL_MAX_TOTAL_STEPS,
        ),
        (
            "check_decisions",
            "decision_count",
            "max_decisions",
            TerminationReason.PARTIAL_MAX_DECISIONS,
        ),
        (
            "check_evidence",
            "evidence_count",
            "max_evidence_items",
            TerminationReason.PARTIAL_MAX_EVIDENCE_ITEMS,
        ),
        (
            "check_context",
            "context_count",
            "max_context_items",
            TerminationReason.PARTIAL_MAX_CONTEXT_ITEMS,
        ),
        (
            "check_tool_result",
            "tool_result_count",
            "max_tool_result_records",
            TerminationReason.PARTIAL_MAX_TOOL_RESULTS,
        ),
        (
            "check_repeated_action",
            "repeat_count",
            "max_repeated_action",
            TerminationReason.PARTIAL_REPEATED_ACTION,
        ),
        (
            "check_rejected_decisions",
            "rejected_decision_count",
            "max_rejected_decisions",
            TerminationReason.PARTIAL_REJECTED_DECISION_LIMIT,
        ),
    ],
)
def test_count_checks_deny_at_limit(
    method,
    argument,
    budget_field,
    reason,
):
    budget = AgentExecutionBudget(**{budget_field: 3})
    guard = BudgetGuard(budget)

    result = getattr(guard, method)(**{argument: 3})

    assert result.status is BudgetCheckStatus.EXCEEDED
    assert result.allowed is False
    assert result.reason is reason


def test_count_checks_deny_above_limit():
    guard = BudgetGuard(
        AgentExecutionBudget(max_iterations=3),
    )

    result = guard.check_iteration(iteration_count=4)

    assert result.allowed is False
    assert result.reason is TerminationReason.PARTIAL_MAX_ITERATIONS


@pytest.mark.parametrize(
    "value",
    [-1, -10],
)
def test_count_checks_reject_negative_count(value):
    guard = BudgetGuard(AgentExecutionBudget())

    with pytest.raises(ValueError, match="count cannot be negative"):
        guard.check_iteration(iteration_count=value)


@pytest.mark.parametrize(
    "value",
    [True, False, 1.0, "1", None],
)
def test_count_checks_reject_non_integer_count(value):
    guard = BudgetGuard(AgentExecutionBudget())

    with pytest.raises(TypeError, match="count must be an integer"):
        guard.check_iteration(iteration_count=value)


def test_check_time_allows_before_deadline():
    started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    now = started_at + timedelta(seconds=9)

    guard = BudgetGuard(
        AgentExecutionBudget(max_execution_time_seconds=10),
    )

    result = guard.check_time(
        started_at=started_at,
        now=now,
    )

    assert result.allowed is True
    assert result.reason is None


def test_check_time_denies_at_deadline():
    started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    now = started_at + timedelta(seconds=10)

    guard = BudgetGuard(
        AgentExecutionBudget(max_execution_time_seconds=10),
    )

    result = guard.check_time(
        started_at=started_at,
        now=now,
    )

    assert result.allowed is False
    assert result.reason is TerminationReason.PARTIAL_TIMEOUT


def test_check_time_denies_after_deadline():
    started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    now = started_at + timedelta(seconds=11)

    guard = BudgetGuard(
        AgentExecutionBudget(max_execution_time_seconds=10),
    )

    result = guard.check_time(
        started_at=started_at,
        now=now,
    )

    assert result.allowed is False
    assert result.reason is TerminationReason.PARTIAL_TIMEOUT


def test_check_time_denies_when_clock_moves_backwards():
    started_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    now = started_at - timedelta(seconds=1)

    guard = BudgetGuard(AgentExecutionBudget())

    result = guard.check_time(
        started_at=started_at,
        now=now,
    )

    assert result.allowed is False
    assert result.reason is TerminationReason.PARTIAL_TIMEOUT


def test_check_time_rejects_naive_started_at():
    guard = BudgetGuard(AgentExecutionBudget())

    with pytest.raises(ValueError, match="Invalid execution timing"):
        guard.check_time(
            started_at=datetime(2026, 1, 1, 12, 0),
            now=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        )


def test_check_time_rejects_naive_now():
    guard = BudgetGuard(AgentExecutionBudget())

    with pytest.raises(ValueError, match="Invalid execution timing"):
        guard.check_time(
            started_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
            now=datetime(2026, 1, 1, 12, 0),
        )


def test_check_time_rejects_non_datetime_started_at():
    guard = BudgetGuard(AgentExecutionBudget())

    with pytest.raises(ValueError, match="Invalid execution timing"):
        guard.check_time(
            started_at="2026-01-01",
            now=datetime(2026, 1, 1, tzinfo=UTC),
        )


def test_budget_check_result_allow():
    result = BudgetCheckResult.allow()

    assert result.status is BudgetCheckStatus.ALLOWED
    assert result.allowed is True
    assert result.reason is None


def test_budget_check_result_deny():
    result = BudgetCheckResult.deny(
        TerminationReason.PARTIAL_MAX_ITERATIONS,
    )

    assert result.status is BudgetCheckStatus.EXCEEDED
    assert result.allowed is False
    assert result.reason is TerminationReason.PARTIAL_MAX_ITERATIONS
