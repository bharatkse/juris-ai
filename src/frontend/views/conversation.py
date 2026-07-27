"""
Frontend conversation views.
"""

from __future__ import annotations

from fastapi import Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.frontend.context import build_frontend_context
from src.frontend.dependencies import (
    ConversationEventServiceDep,
    ConversationServiceDep,
)
from src.frontend.renderer import render
from src.services.conversation import CreateConversationRequest

templates = Jinja2Templates(
    directory="src/frontend/templates",
)


async def create_conversation(
    request: Request,
    service: ConversationServiceDep,
    title: str | None = Form(default=None),
) -> HTMLResponse:
    """
    Create a new conversation.
    """

    user_id = "user_123"
    conversation = await service.create(
        request=CreateConversationRequest(
            user_id=user_id,
            title=title,
        ),
    )

    conversations = [
        conversation,
    ]

    return templates.TemplateResponse(
        request=request,
        name="components/sidebar.html",
        context={
            "request": request,
            "conversations": conversations,
            "active_conversation_id": conversation.id,
        },
    )


async def conversation_sidebar(
    request: Request,
) -> HTMLResponse:
    """
    Render the conversation sidebar.

    TODO:
        Load conversations from ConversationService.
    """

    conversations: list[dict[str, str]] = []

    return templates.TemplateResponse(
        request=request,
        name="components/sidebar.html",
        context={
            "request": request,
            "conversations": conversations,
            "active_conversation_id": None,
        },
    )


async def open_conversation(
    request: Request,
    conversation_id: str,
    conversation_service: ConversationServiceDep,
    event_service: ConversationEventServiceDep,
) -> HTMLResponse:
    """
    Open a conversation.
    """

    #
    # TODO:
    # Replace with authenticated user.
    #
    user_id = "user_123"

    conversation = await conversation_service.get(
        conversation_id=conversation_id,
        user_id=user_id,
    )

    if conversation is None:
        raise NotImplementedError("Conversation not found.")

    messages = await event_service.list(
        conversation_id=conversation.id,
    )

    context = await build_frontend_context(
        conversation_service=conversation_service,
        user_id=user_id,
        active_conversation_id=conversation.id,
        current_conversation=conversation,
        messages=messages,
    )

    return render(
        request=request,
        template="components/chat_panel.html",
        **context,
    )
