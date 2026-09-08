from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agentic.agents.runtime.lifecycle.state import AgentState


class AgentExecutionStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class TerminationReason(StrEnum):
    COMPLETED = "completed"

    PARTIAL_MAX_ITERATIONS = "partial_max_iterations"
    PARTIAL_MAX_TOOL_CALLS = "partial_max_tool_calls"
    PARTIAL_MAX_AGENT_HOPS = "partial_max_agent_hops"
    PARTIAL_MAX_TOTAL_STEPS = "partial_max_total_steps"
    PARTIAL_MAX_DECISIONS = "partial_max_decisions"

    PARTIAL_MAX_EVIDENCE_ITEMS = "partial_max_evidence_items"
    PARTIAL_MAX_CONTEXT_ITEMS = "partial_max_context_items"
    PARTIAL_MAX_TOOL_RESULTS = "partial_max_tool_results"

    PARTIAL_TIMEOUT = "partial_timeout"
    PARTIAL_REPEATED_ACTION = "partial_repeated_action"
    PARTIAL_VALIDATION_LIMIT = "partial_validation_limit"

    FAILED_TOOL = "failed_tool"
    FAILED_LLM = "failed_llm"
    FAILED_VALIDATION = "failed_validation"
    FAILED_POLICY = "failed_policy"

    USER_INPUT_REQUIRED = "user_input_required"


class AgentTerminator:
    """
    Applies terminal status to one execution state.

    AgentTerminator is stateless and never retains AgentState.
    """

    def complete(
        self,
        *,
        state: AgentState,
    ) -> AgentState:
        state.status = AgentExecutionStatus.COMPLETED
        state.termination_reason = TerminationReason.COMPLETED
        return state

    def partial(
        self,
        *,
        state: AgentState,
        reason: TerminationReason,
    ) -> AgentState:
        state.status = AgentExecutionStatus.PARTIAL
        state.termination_reason = reason
        return state

    def fail(
        self,
        *,
        state: AgentState,
        reason: TerminationReason,
    ) -> AgentState:
        state.status = AgentExecutionStatus.FAILED
        state.termination_reason = reason
        return state

    def user_input_required(
        self,
        *,
        state: AgentState,
    ) -> AgentState:
        state.status = AgentExecutionStatus.PARTIAL
        state.termination_reason = TerminationReason.USER_INPUT_REQUIRED
        return state
