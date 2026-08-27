"""
Execution result models.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agentic.execution.schemas.state import ExecutionStateSchema
from core.dto.agent_action import AgentActionResponseDTO
from core.dto.approval import ApprovalResponseDTO


class ExecutionResultSchema(BaseModel):
    """
    Result produced by an execution session.

    The result contains the execution state and artifacts produced
    by LangGraph, together with an optional persisted AgentAction
    and optional human approval request.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    state: ExecutionStateSchema

    artifacts: dict[str, Any] = Field(
        default_factory=dict,
    )

    action: AgentActionResponseDTO | None = None

    approval: ApprovalResponseDTO | None = None

    @property
    def approval_required(self) -> bool:
        """
        Return whether the execution produced an action requiring
        human approval.
        """

        return self.approval is not None
