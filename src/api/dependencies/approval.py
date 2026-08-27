"""
Approval API dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from adapters.persistence.sqlalchemy.session import get_db_session
from application.services.approval_lifecycle import ApprovalLifecycleService


def get_approval_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> ApprovalRepository:
    """
    Create an approval repository.
    """

    return ApprovalRepository(
        session=session,
    )


def get_approval_lifecycle_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    repository: ApprovalRepository = Depends(
        get_approval_repository,
    ),
) -> ApprovalLifecycleService:
    """
    Create the approval lifecycle service.
    """

    return ApprovalLifecycleService(
        session=session,
        repository=repository,
    )
