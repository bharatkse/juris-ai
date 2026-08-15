"""
Conversation dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.repositories.conversation import ConversationRepository
from src.services.conversation import ConversationService


def get_conversation_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> ConversationRepository:
    """
    Create a ConversationRepository.
    """

    return ConversationRepository(
        session=session,
    )


def get_conversation_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    repository: ConversationRepository = Depends(
        get_conversation_repository,
    ),
) -> ConversationService:
    """
    Create a ConversationService.
    """

    return ConversationService(
        session=session,
        repository=repository,
    )
