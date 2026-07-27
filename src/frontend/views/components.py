"""
Frontend partial views.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from src.frontend.dependencies import ConversationServiceDep
from src.frontend.renderer import render


async def conversation_sidebar(
    *,
    request: Request,
    service: ConversationServiceDep,
    active_conversation_id: str | None = None,
) -> HTMLResponse:
    """
    Render the conversation sidebar.
    """

    #
    # TODO:
    # Replace with authenticated user.
    #
    user_id = "user_123"

    conversations = await service.list(
        user_id=user_id,
    )

    return render(
        request=request,
        template="components/sidebar.html",
        conversations=conversations,
        active_conversation_id=active_conversation_id,
    )
