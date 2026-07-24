"""
Chat API routes.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from src.api.dependencies.chat import get_chat_service
from src.api.streaming import encode_sse_event
from src.core.logger import get_logger
from src.core.response import ApiResponse
from src.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamResponse,
    ConversationEventResponse,
)
from src.services.chat import ChatService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    summary="Chat with JurisAI",
    status_code=status.HTTP_200_OK,
)
async def chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ApiResponse:
    """
    Send a message to JurisAI.

    The request is stored as a user event,
    processed by the AI agent, and the generated
    response is stored as an assistant event.
    """

    result = await service.chat(
        conversation_id=request.conversation_id,
        message=request.message,
    )

    return ApiResponse(
        success=True,
        data=ChatResponse(
            conversation_id=result.conversation.id,
            user_event=ConversationEventResponse.model_validate(
                result.user_event,
                from_attributes=True,
            ),
            assistant_event=ConversationEventResponse.model_validate(
                result.assistant_event,
                from_attributes=True,
            ),
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/stream",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
)
async def stream_chat(
    request: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """
    Stream a chat response.
    """

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in service.stream_chat(
                conversation_id=request.conversation_id,
                message=request.message,
            ):
                yield encode_sse_event(
                    ChatStreamResponse(
                        content=chunk.content,
                        is_final=chunk.is_final,
                        metadata=chunk.metadata,
                    )
                )

        except asyncio.CancelledError:
            logger.error("Client disconnected from chat stream.")
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
