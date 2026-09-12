from __future__ import annotations

import logging
from datetime import datetime, timedelta

from agentic.agents.runtime.lifecycle.guard import BudgetCheckResult, BudgetGuard
from agentic.agents.runtime.lifecycle.loop_breaker import LoopBreaker
from agentic.agents.runtime.lifecycle.state import AgentState
from agentic.agents.runtime.lifecycle.termination import (
    AgentTerminator,
    TerminationReason,
)

logger = logging.getLogger(__name__)


class AgentLifecycle:
    """
    Controls the runtime lifecycle of one agent execution.

    The lifecycle object is stateless with respect to execution data.
    All mutable execution state is held by the request-scoped AgentState.

    Responsibilities:
    - enforce execution budgets
    - consume runtime counters
    - track repeated actions
    - track semantic progress
    - maintain bounded partial responses
    - apply terminal state transitions

    This class does not:
    - perform LLM reasoning
    - execute tools
    - delegate to other agents
    - own LangGraph state
    - store state globally
    """

    def __init__(
        self,
        *,
        state: AgentState,
        guard: BudgetGuard | None = None,
        terminator: AgentTerminator | None = None,
    ) -> None:
        if not isinstance(state, AgentState):
            raise TypeError("state must be an AgentState.")

        self._state = state
        self._guard = guard or BudgetGuard(state.budget)
        self._terminator = terminator or AgentTerminator()
        self._loop_breaker = LoopBreaker(
            state=self._state,
            guard=self._guard,
        )

    @property
    def state(self) -> AgentState:
        """Return the request-scoped execution state."""
        return self._state

    @property
    def deadline(self) -> datetime:
        """Return the absolute execution deadline."""
        return self._state.started_at + timedelta(
            seconds=self._state.budget.max_execution_time_seconds,
        )

    def check_time(
        self,
        *,
        now: datetime | None = None,
    ) -> BudgetCheckResult:
        """Check whether the execution deadline has been exceeded."""
        return self._guard.check_time(
            started_at=self._state.started_at,
            now=now,
        )

    def begin_iteration(self) -> BudgetCheckResult:
        """
        Check and consume one reasoning-iteration budget unit.

        The counter is incremented only after all pre-operation checks pass.
        """
        result = self.check_time()
        if not result.allowed:
            return self._terminate_partial(result.reason)

        result = self._guard.check_iteration(
            iteration_count=self._state.iteration_count,
        )
        if not result.allowed:
            return self._terminate_partial(result.reason)

        self._state.iteration_count += 1
        return result

    def begin_tool_call(self) -> BudgetCheckResult:
        """Check and consume one tool-call execution budget unit."""
        result = self.check_time()
        if not result.allowed:
            return self._terminate_partial(result.reason)

        result = self._guard.check_tool_call(
            tool_call_count=self._state.tool_call_count,
        )
        if not result.allowed:
            return self._terminate_partial(result.reason)

        self._state.tool_call_count += 1
        return result

    def begin_agent_hop(self) -> BudgetCheckResult:
        """Check and consume one agent-delegation hop budget unit."""
        result = self.check_time()
        if not result.allowed:
            return self._terminate_partial(result.reason)

        result = self._guard.check_agent_hop(
            agent_hop_count=self._state.agent_hop_count,
        )
        if not result.allowed:
            return self._terminate_partial(result.reason)

        self._state.agent_hop_count += 1
        return result

    def begin_step(self) -> BudgetCheckResult:
        """Check and consume one total execution-step budget unit."""
        result = self.check_time()
        if not result.allowed:
            return self._terminate_partial(result.reason)

        result = self._guard.check_total_step(
            total_step_count=self._state.total_step_count,
        )
        if not result.allowed:
            return self._terminate_partial(result.reason)

        self._state.total_step_count += 1
        return result

    def begin_decision(self) -> BudgetCheckResult:
        """
        Check and consume one decision budget unit.

        The decision object itself is retained by the caller, typically in
        LangGraph execution state. This method only controls the lifecycle
        counter and budget.
        """
        result = self.check_time()
        if not result.allowed:
            return self._terminate_partial(result.reason)

        result = self._guard.check_decisions(
            decision_count=self._state.decision_count,
        )
        if not result.allowed:
            return self._terminate_partial(result.reason)

        self._state.decision_count += 1
        return result

    def record_evidence(self, *, count: int = 1) -> BudgetCheckResult:
        """Check and consume retained evidence capacity."""
        if count <= 0:
            raise ValueError("count must be greater than zero.")

        new_count = self._state.evidence_count + count

        if new_count > self._state.budget.max_evidence_items:
            return self._terminate_partial(
                TerminationReason.PARTIAL_MAX_EVIDENCE_ITEMS,
            )

        self._state.evidence_count = new_count
        return BudgetCheckResult.allow()

    def record_context(self, *, count: int = 1) -> BudgetCheckResult:
        """Check and consume retained context capacity."""
        if count <= 0:
            raise ValueError("count must be greater than zero.")

        new_count = self._state.context_count + count

        if new_count > self._state.budget.max_context_items:
            return self._terminate_partial(
                TerminationReason.PARTIAL_MAX_CONTEXT_ITEMS,
            )

        self._state.context_count = new_count
        return BudgetCheckResult.allow()

    def record_tool_result(self, *, count: int = 1) -> BudgetCheckResult:
        """Check and consume retained tool-result record capacity."""
        if count <= 0:
            raise ValueError("count must be greater than zero.")

        new_count = self._state.tool_result_count + count

        if new_count > self._state.budget.max_tool_result_records:
            return self._terminate_partial(
                TerminationReason.PARTIAL_MAX_TOOL_RESULTS,
            )

        self._state.tool_result_count = new_count
        return BudgetCheckResult.allow()

    def begin_validation(self) -> BudgetCheckResult:
        """Check and consume one validation-attempt budget unit."""
        result = self.check_time()
        if not result.allowed:
            return self._terminate_partial(result.reason)

        result = self._guard.check_validation_attempts(
            validation_attempt_count=self._state.validation_attempt_count,
        )
        if not result.allowed:
            return self._terminate_partial(result.reason)

        self._state.validation_attempt_count += 1
        return result

    def record_action(self, action_key: str) -> BudgetCheckResult:
        """
        Track a consecutive executable action through the LoopBreaker.

        AgentLifecycle remains responsible for applying the terminal
        transition when the LoopBreaker denies the operation.
        """
        result = self._loop_breaker.record_action(
            action_key,
        )

        if not result.allowed:
            return self._terminate_partial(result.reason)

        return result

    def record_progress(
        self,
        progress_key: str,
    ) -> BudgetCheckResult:
        """
        Track semantic continuation progress through the LoopBreaker.

        AgentLifecycle remains responsible for applying the terminal
        transition when the LoopBreaker denies further continuation.
        """
        result = self._loop_breaker.record_progress(
            progress_key,
        )

        if not result.allowed:
            return self._terminate_partial(result.reason)

        return result

    def set_partial_response(self, response: str | None) -> None:
        """
        Store a bounded best-known response.

        The response is truncated at the configured character limit so a
        large model output cannot grow request-scoped memory without bound.
        """
        if response is None:
            return

        if not isinstance(response, str):
            raise TypeError("partial response must be a string.")

        self._state.partial_response = response[: self._state.budget.max_partial_response_chars]

    def complete(self) -> None:
        """Mark this execution as successfully completed."""
        self._terminator.complete(
            state=self._state,
        )

    def fail(self, reason: TerminationReason) -> None:
        """
        Mark this execution as failed.

        Only explicit FAILED_* reasons are accepted.
        """
        if reason not in {
            TerminationReason.FAILED_TOOL,
            TerminationReason.FAILED_LLM,
            TerminationReason.FAILED_VALIDATION,
            TerminationReason.FAILED_POLICY,
        }:
            raise ValueError(
                "reason must be a FAILED_* termination reason.",
            )

        self._terminator.fail(
            state=self._state,
            reason=reason,
        )

    def user_input_required(self) -> None:
        """Mark this execution as waiting for required user input."""
        self._terminator.user_input_required(
            state=self._state,
        )

    def partial(self, reason: TerminationReason) -> None:
        """Mark this execution as partially completed."""
        self._terminate_partial(reason)

    def _terminate_partial(
        self,
        reason: TerminationReason | None,
    ) -> BudgetCheckResult:
        """Apply a partial terminal state after a budget check is denied."""
        if reason is None:
            raise ValueError(
                "A denied budget check must contain a termination reason.",
            )

        self._terminator.partial(
            state=self._state,
            reason=reason,
        )

        logger.warning(
            "Agent execution terminated partially: reason=%s.",
            reason,
        )

        return BudgetCheckResult.deny(reason)
