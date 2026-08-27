"""
Chat service dependencies.
"""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.session import get_db_session
from agentic.orchestration.orchestrator import AIOrchestrator
from api.dependencies.action_workflow import get_action_workflow_service
from application.services.action_workflow import ActionWorkflowService
from application.services.chat import ChatService
from application.services.conversation import ConversationService
from application.services.conversation_event import ConversationEventService

# ============================================================================
# Repositories
# ============================================================================


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


def get_conversation_event_repository(
    session: AsyncSession = Depends(
        get_db_session,
    ),
) -> ConversationEventRepository:
    """
    Create a ConversationEventRepository.
    """

    return ConversationEventRepository(
        session=session,
    )


# ============================================================================
# Services
# ============================================================================


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
    repository: ConversationEventRepository = Depends(
        get_conversation_event_repository,
    ),
) -> ConversationEventService:
    """
    Create a ConversationEventService.
    """

    return ConversationEventService(
        session=session,
        repository=repository,
    )


def get_ai_orchestrator(
    request: Request,
) -> AIOrchestrator:
    """
    Return the application-scoped AI orchestrator.

    The orchestrator is created during application startup with
    the configured LangGraph PostgreSQL checkpointer.
    """

    return request.app.state.ai_orchestrator


# ============================================================================
# Chat Service
# ============================================================================


def get_chat_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    conversation_service: ConversationService = Depends(
        get_conversation_service,
    ),
    conversation_event_service: ConversationEventService = Depends(
        get_conversation_event_service,
    ),
    orchestrator: AIOrchestrator = Depends(
        get_ai_orchestrator,
    ),
    agent_action_workflow_service: ActionWorkflowService = Depends(
        get_action_workflow_service,
    ),
) -> ChatService:
    """
    Create a ChatService.
    """

    return ChatService(
        session=session,
        conversation_service=conversation_service,
        conversation_event_service=conversation_event_service,
        orchestrator=orchestrator,
        action_workflow_service=agent_action_workflow_service,
    )
