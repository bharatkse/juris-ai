"""
Frontend chat views.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(
    directory="src/frontend/templates",
)


async def messages(
    request: Request,
    conversation_id: str,
) -> HTMLResponse:
    """
    Render the messages for a conversation.

    TODO:
        Load messages from ChatService.
    """

    return templates.TemplateResponse(
        request=request,
        name="components/message_list.html",
        context={
            "request": request,
            "conversation_id": conversation_id,
            "messages": [],
        },
    )


async def send_message(
    request: Request,
    conversation_id: str,
) -> HTMLResponse:
    """
    Persist the user's message.

    TODO:
        Call ChatService.chat().
    """

    return templates.TemplateResponse(
        request=request,
        name="components/message_list.html",
        context={
            "request": request,
            "conversation_id": conversation_id,
            "messages": [],
        },
    )


async def stream_message(
    request: Request,
    conversation_id: str,
) -> StreamingResponse:
    """
    Stream the assistant response.

    TODO:
        Call ChatService.stream_chat().
    """

    async def event_stream() -> AsyncIterator[str]:
        yield "data: {}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )
