"""
Conversation dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.session import get_db_session
from application.services.conversation import ConversationService
from application.services.conversation_event import ConversationEventService


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


def get_conversation_event_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> ConversationEventService:
    """
    Create a conversation event service for history endpoints.
    """

    return ConversationEventService(
        session=session,
        repository=ConversationEventRepository(
            session=session,
        ),
    )
