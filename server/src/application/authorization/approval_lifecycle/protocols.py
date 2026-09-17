"""
Approval lifecycle protocols.
"""

from __future__ import annotations

from typing import Protocol

from core.dto.agent_action import AgentActionResponseDTO
from core.dto.approval import ApprovalDecisionRequestDTO, ApprovalResponseDTO


class ApprovalLifecycleServiceProtocol(Protocol):
    """
    Defines the contract for the approval lifecycle service.

    The lifecycle service owns:
    - approval creation,
    - approval retrieval,
    - approval validation,
    - approval decision processing.

    It does not own:
    - authorization,
    - approval policy evaluation,
    - action execution.
    """

    async def create(
        self,
        *,
        action: AgentActionResponseDTO,
        requested_by: str,
    ) -> ApprovalResponseDTO:
        """
        Create a new approval request.
        """
        ...

    async def get(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Retrieve an approval request.
        """
        ...

    async def validate(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Validate an approved request for execution.
        """
        ...

    async def process(
        self,
        *,
        approval_id: str,
        request: ApprovalDecisionRequestDTO,
        user_id: str,
    ) -> ApprovalResponseDTO:
        """
        Process a human approval decision.
        """
        ...
