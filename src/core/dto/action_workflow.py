"""
Agent action workflow dto.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.dto.agent_action import AgentActionResponseDTO
from src.core.dto.approval import ApprovalResponseDTO


@dataclass(frozen=True, slots=True)
class ActionWorkflowResultDTO:
    """
    Result of preparing an AgentAction for execution.

    If human approval is required, the result contains the
    persisted approval request.

    This workflow never waits for human approval.
    """

    action: AgentActionResponseDTO
    approval: ApprovalResponseDTO | None = None

    @property
    def approval_required(self) -> bool:
        """
        Return whether human approval is required.
        """

        return self.approval is not None
