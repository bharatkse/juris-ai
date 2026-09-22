"""
Chat service dependencies.
"""

from __future__ import annotations

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.clients.llm.base import LLMClient
from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.session import get_db_session
from agentic.orchestration.orchestrator import AIOrchestrator
from api.dependencies.action_workflow import get_action_workflow_service
from api.dependencies.compliance_log import get_compliance_log_service
from api.dependencies.llm import get_llm_client
from api.dependencies.rate_limit import get_usage_service
from api.dependencies.user_memory import (
    get_memory_extraction_scheduler,
    get_user_memory_service,
)
from application.services.action_workflow import ActionWorkflowService
from application.services.chat import ChatService
from application.services.compliance_log import ComplianceLogService
from application.services.conversation import ConversationService
from application.services.conversation_event import ConversationEventService
from application.services.conversation_summarization import (
    ConversationSummarizationService,
)
from application.services.usage import UsageService
from application.services.user_memory import UserMemoryService
from application.services.user_memory_extraction import MemoryExtractionScheduler

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


def get_conversation_summarization_service(
    session: AsyncSession = Depends(
        get_db_session,
    ),
    conversation_event_service: ConversationEventService = Depends(
        get_conversation_event_service,
    ),
    llm_client: LLMClient = Depends(
        get_llm_client,
    ),
) -> ConversationSummarizationService:
    """
    Create a ConversationSummarizationService.
    """

    return ConversationSummarizationService(
        session=session,
        conversation_event_service=conversation_event_service,
        llm_client=llm_client,
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
    usage_service: UsageService = Depends(
        get_usage_service,
    ),
    conversation_summarization_service: ConversationSummarizationService = Depends(
        get_conversation_summarization_service,
    ),
    compliance_log_service: ComplianceLogService = Depends(
        get_compliance_log_service,
    ),
    user_memory_service: UserMemoryService = Depends(
        get_user_memory_service,
    ),
    memory_extraction_scheduler: MemoryExtractionScheduler = Depends(
        get_memory_extraction_scheduler,
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
        usage_service=usage_service,
        conversation_summarization_service=conversation_summarization_service,
        compliance_log_service=compliance_log_service,
        user_memory_service=user_memory_service,
        memory_extraction_scheduler=memory_extraction_scheduler,
    )
