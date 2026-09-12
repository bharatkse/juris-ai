from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.termination import (
    AgentExecutionStatus,
    TerminationReason,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentState:
    """
    Request-scoped mutable state for one agent execution.

    One instance belongs to exactly one execution and must never be stored
    as module/global state or shared between concurrent requests.

    AgentState contains execution data only. Runtime behavior belongs to
    AgentLifecycle.

    Progress tracking is also request-scoped. The state records the latest
    progress identity and consecutive no-progress observations so the
    existing lifecycle and LoopBreaker can make deterministic continuation
    decisions without introducing another loop-control framework.
    """

    budget: AgentExecutionBudget
    started_at: datetime

    status: AgentExecutionStatus = AgentExecutionStatus.RUNNING
    termination_reason: TerminationReason | None = None

    iteration_count: int = 0
    tool_call_count: int = 0
    agent_hop_count: int = 0
    total_step_count: int = 0
    decision_count: int = 0
    validation_attempt_count: int = 0

    evidence_count: int = 0
    context_count: int = 0
    tool_result_count: int = 0

    repeated_action_count: int = 0
    last_action_key: str | None = field(default=None, repr=False)

    no_progress_count: int = 0
    last_progress_key: str | None = field(default=None, repr=False)

    partial_response: str = ""
