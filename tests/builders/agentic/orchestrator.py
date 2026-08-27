"""
Builders for orchestration models.
"""

from __future__ import annotations

from agentic.orchestration.schemas.request import (
    Attachment,
    OrchestratorRequest,
    RequestMetadata,
)
from agentic.orchestration.schemas.response import (
    AgentResponse,
    Citation,
    OrchestratorResponse,
    ResponseMetadata,
    Source,
    Usage,
)
from core.enums import AttachmentTypeEnum, MessageRoleEnum, RequestSourceEnum
from core.models.conversation import ConversationMessageSchema
from core.types import ConversationId, UserId
from tests.helpers.identifiers import unknown_conversation_id, unknown_user_id


def build_citation(
    **kwargs,
) -> Citation:
    """
    Build a Citation.
    """

    data = {
        "title": "Indian Penal Code",
        "source": "IPC",
        "reference": "Section 420",
        "page": 10,
        "snippet": "Cheating and dishonestly inducing delivery of property.",
    }

    data.update(kwargs)

    return Citation(**data)


def build_source(
    **kwargs,
) -> Source:
    """
    Build a Source.
    """

    data = {
        "title": "IPC",
        "uri": "https://example.com/ipc",
        "type": "legal_document",
    }

    data.update(kwargs)

    return Source(**data)


def build_usage(
    **kwargs,
) -> Usage:
    """
    Build usage information.
    """

    data = {
        "provider": "groq",
        "model": "llama-3.3-70b-versatile",
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "latency_ms": 120.5,
    }

    data.update(kwargs)

    return Usage(**data)


def build_response_metadata(
    **kwargs,
) -> ResponseMetadata:
    """
    Build response metadata.
    """

    data = {
        "agents": ["legal"],
        "workflow": "legal_qa",
    }

    data.update(kwargs)

    return ResponseMetadata(**data)


def build_agent_response(
    **kwargs,
) -> AgentResponse:
    """
    Build an AgentResponse.
    """

    data = {
        "agent_name": "legal",
        "content": "Hello",
        "citations": [],
        "sources": [],
        "usage": build_usage(),
        "metadata": build_response_metadata(),
    }

    data.update(kwargs)

    return AgentResponse(**data)


def build_orchestrator_response(
    *,
    conversation_id: ConversationId | None = None,
    content: str = "Legal answer",
    metadata: ResponseMetadata | None = None,
) -> OrchestratorResponse:
    """
    Build an OrchestratorResponse.
    """

    return OrchestratorResponse(
        conversation_id=(conversation_id or unknown_conversation_id()),
        content=content,
        metadata=(metadata or build_response_metadata()),
    )


def build_conversation_message(
    **kwargs,
) -> ConversationMessageSchema:
    """
    Build a ConversationMessageSchema.
    """

    data = {
        "role": MessageRoleEnum.USER,
        "content": "Hello",
    }

    data.update(kwargs)

    return ConversationMessageSchema(**data)


def build_attachment(
    **kwargs,
) -> Attachment:
    """
    Build an Attachment.
    """

    data = {
        "id": "file_123",
        "name": "contract.pdf",
        "type": AttachmentTypeEnum.PDF,
        "uri": "s3://bucket/contract.pdf",
    }

    data.update(kwargs)

    return Attachment(**data)


def build_request_metadata(
    **kwargs,
) -> RequestMetadata:
    """
    Build request metadata.
    """

    data = {
        "source": RequestSourceEnum.CHAT,
    }

    data.update(kwargs)

    return RequestMetadata(**data)


def build_orchestrator_request(
    *,
    conversation_id: ConversationId | None = None,
    user_id: UserId | None = None,
    message: str = "Hello",
    history: list[ConversationMessageSchema] | None = None,
    attachments: list[Attachment] | None = None,
    metadata: RequestMetadata | None = None,
) -> OrchestratorRequest:
    """
    Build an OrchestratorRequest.
    """

    return OrchestratorRequest(
        conversation_id=(conversation_id or unknown_conversation_id()),
        user_id=(user_id or unknown_user_id()),
        message=message,
        history=history or [],
        attachments=attachments or [],
        metadata=metadata or build_request_metadata(),
    )
