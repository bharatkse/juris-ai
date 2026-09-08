from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.termination import TerminationReason

logger = logging.getLogger(__name__)


class BudgetCheckStatus(StrEnum):
    """Outcome of a pre-operation execution budget check."""

    ALLOWED = "allowed"
    EXCEEDED = "exceeded"


@dataclass(frozen=True, slots=True)
class BudgetCheckResult:
    """Immutable result returned by a single budget check."""

    status: BudgetCheckStatus
    reason: TerminationReason | None = None

    @property
    def allowed(self) -> bool:
        """Return True when the next operation may start."""
        return self.status is BudgetCheckStatus.ALLOWED

    @classmethod
    def allow(cls) -> BudgetCheckResult:
        """Create a successful budget-check result."""
        return cls(status=BudgetCheckStatus.ALLOWED)

    @classmethod
    def deny(cls, reason: TerminationReason) -> BudgetCheckResult:
        """Create a denied budget-check result with its terminal reason."""
        return cls(status=BudgetCheckStatus.EXCEEDED, reason=reason)


class BudgetGuard:
    """
    Perform stateless, read-only checks against one execution budget.

    BudgetGuard answers whether the next operation is allowed to start.
    It never mutates execution state, never stores request-scoped state,
    and never performs termination itself.

    The caller owns counter increments, state mutation, and application of
    AgentTerminator when a check returns an exceeded result.

    Counters use pre-operation semantics: when current_count >= maximum,
    the next operation is denied. This makes the check safe to call before
    an expensive LLM, tool, delegation, validation, or state-growth step.
    """

    def __init__(self, budget: AgentExecutionBudget) -> None:
        """Initialize a guard with immutable execution limits."""
        if not isinstance(budget, AgentExecutionBudget):
            raise TypeError("budget must be an AgentExecutionBudget.")

        self._budget = budget

    def check_iteration(self, *, iteration_count: int) -> BudgetCheckResult:
        """Check whether another reasoning iteration may start."""
        return self._count_check(
            name="iteration",
            current_count=iteration_count,
            maximum=self._budget.max_iterations,
            reason=TerminationReason.PARTIAL_MAX_ITERATIONS,
        )

    def check_tool_call(self, *, tool_call_count: int) -> BudgetCheckResult:
        """Check whether another tool execution may start."""
        return self._count_check(
            name="tool_call",
            current_count=tool_call_count,
            maximum=self._budget.max_tool_calls,
            reason=TerminationReason.PARTIAL_MAX_TOOL_CALLS,
        )

    def check_agent_hop(self, *, agent_hop_count: int) -> BudgetCheckResult:
        """Check whether another agent delegation may start."""
        return self._count_check(
            name="agent_hop",
            current_count=agent_hop_count,
            maximum=self._budget.max_agent_hops,
            reason=TerminationReason.PARTIAL_MAX_AGENT_HOPS,
        )

    def check_total_step(self, *, total_step_count: int) -> BudgetCheckResult:
        """Check whether another execution step may start."""
        return self._count_check(
            name="total_step",
            current_count=total_step_count,
            maximum=self._budget.max_total_steps,
            reason=TerminationReason.PARTIAL_MAX_TOTAL_STEPS,
        )

    def check_decisions(self, *, decision_count: int) -> BudgetCheckResult:
        """Check whether another decision may be retained."""
        return self._count_check(
            name="decision",
            current_count=decision_count,
            maximum=self._budget.max_decisions,
            reason=TerminationReason.PARTIAL_MAX_DECISIONS,
        )

    def check_evidence(self, *, evidence_count: int) -> BudgetCheckResult:
        """Check whether another evidence item may be retained."""
        return self._count_check(
            name="evidence",
            current_count=evidence_count,
            maximum=self._budget.max_evidence_items,
            reason=TerminationReason.PARTIAL_MAX_EVIDENCE_ITEMS,
        )

    def check_context(self, *, context_count: int) -> BudgetCheckResult:
        """Check whether another context item may be retained."""
        return self._count_check(
            name="context",
            current_count=context_count,
            maximum=self._budget.max_context_items,
            reason=TerminationReason.PARTIAL_MAX_CONTEXT_ITEMS,
        )

    def check_tool_result(self, *, tool_result_count: int) -> BudgetCheckResult:
        """Check whether another tool-result record may be retained."""
        return self._count_check(
            name="tool_result",
            current_count=tool_result_count,
            maximum=self._budget.max_tool_result_records,
            reason=TerminationReason.PARTIAL_MAX_TOOL_RESULTS,
        )

    def check_time(
        self,
        *,
        started_at: datetime,
        now: datetime | None = None,
    ) -> BudgetCheckResult:
        """
        Check whether execution remains within its configured time budget.

        A timezone-aware timestamp is required. Naive timestamps are rejected
        instead of silently assuming a timezone.
        """
        try:
            self._validate_datetime("started_at", started_at)
            current = now or datetime.now(UTC)
            self._validate_datetime("now", current)

            elapsed = (current - started_at).total_seconds()
        except (TypeError, ValueError) as exc:
            logger.exception("Invalid execution timing supplied to BudgetGuard.")
            raise ValueError("Invalid execution timing for budget check.") from exc

        if elapsed < 0:
            logger.warning(
                "Execution clock moved backwards: started_at=%s, now=%s.",
                started_at,
                current,
            )
            return BudgetCheckResult.deny(TerminationReason.PARTIAL_TIMEOUT)

        if elapsed >= self._budget.max_execution_time_seconds:
            result = BudgetCheckResult.deny(TerminationReason.PARTIAL_TIMEOUT)
            logger.warning(
                "Execution time budget exceeded: elapsed_seconds=%.3f limit_seconds=%s.",
                elapsed,
                self._budget.max_execution_time_seconds,
            )
            return result

        return BudgetCheckResult.allow()

    def check_repeated_action(
        self,
        *,
        repeat_count: int,
    ) -> BudgetCheckResult:
        """Check whether another repeated action may be attempted."""
        return self._count_check(
            name="repeated_action",
            current_count=repeat_count,
            maximum=self._budget.max_repeated_action,
            reason=TerminationReason.PARTIAL_REPEATED_ACTION,
        )

    def check_validation_attempts(
        self,
        *,
        validation_attempt_count: int,
    ) -> BudgetCheckResult:
        """Check whether another validation attempt may start."""
        return self._count_check(
            name="validation_attempt",
            current_count=validation_attempt_count,
            maximum=self._budget.max_validation_attempts,
            reason=TerminationReason.PARTIAL_VALIDATION_LIMIT,
        )

    @staticmethod
    def _count_check(
        *,
        name: str,
        current_count: int,
        maximum: int,
        reason: TerminationReason,
    ) -> BudgetCheckResult:
        """Apply common validation and pre-operation limit semantics."""
        if isinstance(current_count, bool) or not isinstance(current_count, int):
            raise TypeError(f"{name} count must be an integer.")

        if current_count < 0:
            raise ValueError(f"{name} count cannot be negative.")

        if current_count >= maximum:
            result = BudgetCheckResult.deny(reason)
            logger.warning(
                "Execution budget exceeded: resource=%s current=%d maximum=%d reason=%s.",
                name,
                current_count,
                maximum,
                reason,
            )
            return result

        return BudgetCheckResult.allow()

    @staticmethod
    def _validate_datetime(name: str, value: datetime) -> None:
        """Validate that a timestamp is a timezone-aware datetime."""
        if not isinstance(value, datetime):
            raise TypeError(f"{name} must be a datetime.")

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{name} must be timezone-aware.")
