"""
Frontend dependencies.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies.chat import get_chat_service
from src.api.dependencies.conversation import get_conversation_service
from src.db.session import get_db_session
from src.services.chat import ChatService
from src.services.conversation import ConversationService

SessionDep = Annotated[
    AsyncSession,
    Depends(get_db_session),
]

ConversationServiceDep = Annotated[
    ConversationService,
    Depends(get_conversation_service),
]

ChatServiceDep = Annotated[
    ChatService,
    Depends(get_chat_service),
]
