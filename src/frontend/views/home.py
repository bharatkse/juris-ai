"""
Frontend home view.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse

from src.frontend.context import build_frontend_context
from src.frontend.dependencies import ConversationServiceDep
from src.frontend.renderer import render


async def index(
    request: Request,
    conversation_service: ConversationServiceDep,
) -> HTMLResponse:
    """
    Render the application home page.
    """

    #
    # TODO:
    # Replace with authenticated user.
    #
    user_id = "user_123"

    context = await build_frontend_context(
        conversation_service=conversation_service,
        user_id=user_id,
    )

    return render(
        request=request,
        template="index.html",
        **context,
    )
