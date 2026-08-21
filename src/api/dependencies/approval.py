"""
Approval API dependencies.
"""

from __future__ import annotations

from fastapi import Depends

from src.db.session import get_db_session
from src.repositories.approval import ApprovalRepository
from src.services.approval import ApprovalService


def get_approval_lifecycle_service(
    session=Depends(get_db_session),
) -> ApprovalService:
    """
    Provide the approval lifecycle service.
    """

    repository = ApprovalRepository(
        session=session,
    )

    return ApprovalService(
        repository=repository,
    )
