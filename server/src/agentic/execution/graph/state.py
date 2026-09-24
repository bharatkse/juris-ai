"""
LangGraph execution state.
"""

from __future__ import annotations

from datetime import datetime
from operator import add
from typing import Annotated, Any, TypedDict
from uuid import UUID

from agentic.decisions.schemas import AgentDecision
from core.dto.agent import AgentContextDTO
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.conversation import ConversationDTO
from core.dto.planning import ExecutionPlanDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import ExecutionStatusEnum


class ExecutionStepUpdate(TypedDict):
    """
    Immutable execution-state update produced by a graph node.

    A failed execution records an error, while a partial execution records
    the lifecycle termination reason. These fields are kept separate so
    budget-based termination is not treated as an execution failure.
    """

    step_id: str

    status: ExecutionStatusEnum

    retry_count: int

    started_at: datetime | None

    completed_at: datetime | None

    error: str | None

    termination_reason: str | None


class ExecutionArtifactUpdate(TypedDict):
    """
    Immutable execution-memory update produced by a graph node.
    """

    key: str

    value: Any


class AgentDecisionUpdate(TypedDict):
    """
    Immutable agent-decision update produced by an execution node.

    The step_id scopes the decision to one execution-plan step, which keeps
    parallel agent steps isolated while allowing LangGraph to persist the
    history through its checkpoint state.
    """

    step_id: str

    decision: AgentDecision


class ExecutionGraphState(TypedDict):
    """
    LangGraph runtime state.

    Graph state contains immutable/update-oriented values rather than
    mutable ExecutionStateSchema or ExecutionMemorySchema instances.

    This allows multiple parallel nodes to safely emit updates to the
    same channels.

    `context` contains request-scoped runtime information such as identity,
    execution identifiers, and uploaded files.

    `reasoning_context` contains accumulated evidence that may be supplied
    to a subsequent agent reasoning turn.

    The action field contains only the concrete action proposed by an
    agent. Action persistence, authorization, approval-policy evaluation,
    and approval-request creation are handled after graph execution by
    ExecutionSession through ActionWorkflowService.
    """

    request_id: UUID

    # Request-scoped execution timing. These values are immutable for the
    # lifetime of the graph invocation and are used by runtime budget checks.
    started_at: datetime

    deadline: datetime

    conversation: ConversationDTO

    context: AgentContextDTO

    reasoning_context: Annotated[
        list[RetrievedContentDTO],
        add,
    ]

    plan: ExecutionPlanDTO

    execution_state_updates: Annotated[
        list[ExecutionStepUpdate],
        add,
    ]

    memory_updates: Annotated[
        list[ExecutionArtifactUpdate],
        add,
    ]

    agent_decision_updates: Annotated[
        list[AgentDecisionUpdate],
        add,
    ]

    action: AgentActionRequestDTO | None
    termination_reason: str | None
