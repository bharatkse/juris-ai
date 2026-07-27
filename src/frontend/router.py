"""
Frontend routes.
"""

from __future__ import annotations

from fastapi import APIRouter

from src.frontend.views.chat import messages, send_message, stream_message
from src.frontend.views.conversation import (
    conversation_sidebar,
    create_conversation,
    open_conversation,
)
from src.frontend.views.home import index

router = APIRouter(
    tags=["Frontend"],
)


router.add_api_route(
    "/",
    endpoint=index,
    methods=["GET"],
)

router.add_api_route(
    "/conversations",
    create_conversation,
    methods=["POST"],
)

router.add_api_route(
    "/conversations/{conversation_id}",
    open_conversation,
    methods=["GET"],
)


router.add_api_route(
    "/ui/conversations/sidebar",
    endpoint=conversation_sidebar,
    methods=["GET"],
)


router.add_api_route(
    "/ui/conversations/{conversation_id}/messages",
    endpoint=messages,
    methods=["GET"],
)

router.add_api_route(
    "/ui/conversations/{conversation_id}/messages",
    endpoint=send_message,
    methods=["POST"],
)

router.add_api_route(
    "/ui/conversations/{conversation_id}/stream",
    endpoint=stream_message,
    methods=["POST"],
)
