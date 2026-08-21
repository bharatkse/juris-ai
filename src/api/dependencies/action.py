"""
Conversation dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.repositories.action import ActionRepository
from src.services.action import ActionService


def get_action_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> ActionRepository:
    """
    Create a ActionRepository.
    """

    return ActionRepository(
        session=session,
    )


def get_action_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    repository: ActionRepository = Depends(
        get_action_repository,
    ),
) -> ActionService:
    """
    Create a ActionService.
    """

    return ActionService(
        session=session,
        repository=repository,
    )
