"""
Protocols for human approval.
"""

from __future__ import annotations

from typing import Protocol

from src.core.dto.action import ActionResponseDTO
from src.core.dto.approval import ApprovalResponseDTO


class ApprovalLifecycle(Protocol):
    """
    Defines the human approval lifecycle contract.
    """

    async def create(
        self,
        *,
        action: ActionResponseDTO,
        requested_by: str,
    ) -> ApprovalResponseDTO:
        """
        Create a human approval request for a persisted action.
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
        Validate that an approval is currently executable.
        """

        ...

    async def approve(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Approve a waiting approval request.
        """

        ...

    async def reject(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Reject a waiting approval request.
        """

        ...

    async def edit(
        self,
        approval_id: str,
    ) -> ApprovalResponseDTO:
        """
        Mark the current approval as edited.

        The existing approval becomes invalid for execution.
        A new approval cycle is required for the edited action.
        """

        ...
