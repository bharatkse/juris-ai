"""
Conversation dependencies.
"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db_session
from src.repositories.conversation import ConversationRepository
from src.services.conversation import ConversationService


def get_conversation_service(
    session: AsyncSession = Depends(get_db_session),
) -> ConversationService:
    """
    Create a ConversationService instance.
    """

    repository = ConversationRepository(session)

    return ConversationService(
        session=session,
        repository=repository,
    )
