"""
Chat service dependencies.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.base import BaseAgent
from src.agents.legal import LegalAgent
from src.clients.llm.groq import GroqClient
from src.core.config import settings
from src.db.session import get_db_session
from src.prompts.legal import LEGAL_SYSTEM_PROMPT
from src.repositories.conversation import ConversationRepository
from src.repositories.conversation_event import ConversationEventRepository
from src.services.chat import ChatService

# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------
_groq_client = GroqClient(
    api_key=settings.GROQ_API_KEY,
    model=settings.GROQ_MODEL,
)


def get_groq_client() -> GroqClient:
    """
    Return the shared Groq client.
    """

    return _groq_client


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

_legal_agent = LegalAgent(
    client=_groq_client,
    system_prompt=LEGAL_SYSTEM_PROMPT,
)


def get_legal_agent() -> BaseAgent:
    """
    Return the shared legal agent.
    """

    return _legal_agent


# ---------------------------------------------------------------------------
# Repositories
# ---------------------------------------------------------------------------


def get_conversation_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ConversationRepository:
    """
    Create a ConversationRepository.
    """

    return ConversationRepository(session)


def get_conversation_event_repository(
    session: AsyncSession = Depends(get_db_session),
) -> ConversationEventRepository:
    """
    Create a ConversationEventRepository.
    """

    return ConversationEventRepository(session)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def get_chat_service(
    session: AsyncSession = Depends(get_db_session),
    conversation_repository: ConversationRepository = Depends(
        get_conversation_repository,
    ),
    event_repository: ConversationEventRepository = Depends(
        get_conversation_event_repository,
    ),
    agent: BaseAgent = Depends(get_legal_agent),
) -> ChatService:
    """
    Create a ChatService.
    """

    return ChatService(
        session=session,
        conversation_repository=conversation_repository,
        event_repository=event_repository,
        agent=agent,
    )
