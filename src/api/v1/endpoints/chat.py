"""
Chat API routes.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from src.api.dependencies.auth import get_current_user
from src.api.dependencies.chat import get_chat_service
from src.api.helpers.files import build_tool_files
from src.api.schemas.chat import (
    AIResponse,
    ChatRequest,
    ChatResponse,
    ChatStreamResponse,
    ConversationEventResponse,
)
from src.api.streaming import encode_sse_event
from src.core.logger import get_logger
from src.core.response import ApiResponse
from src.services.chat import ChatService

logger = get_logger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=None,
    summary="Chat with JurisAI",
    status_code=status.HTTP_200_OK,
)
async def chat(
    http_request: Request,
    chat_request: ChatRequest = Depends(ChatRequest.as_form),
    current_user=Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> ApiResponse:
    """
    Send a message to JurisAI.
    """

    logger.info(
        "Processing chat request.",
        extra={
            "operation": "chat",
            "conversation_id": str(chat_request.conversation_id),
            "user_id": str(current_user.id),
        },
    )

    files = await build_tool_files(
        chat_request.files,
    )

    result = await service.chat(
        user_id=current_user.id,
        conversation_id=chat_request.conversation_id,
        message=chat_request.message,
        request_id=http_request.state.context.request_id,
        files=files,
    )

    response = AIResponse(
        content=result.response.content,
        citations=result.response.citations,
        sources=result.response.sources,
        usage=result.response.usage,
        metadata=result.response.metadata,
    )

    return ApiResponse(
        success=True,
        status_code=status.HTTP_200_OK,
        data=ChatResponse(
            conversation_id=result.conversation.id,
            response=response,
            user_event=ConversationEventResponse.model_validate(
                result.user_event,
                from_attributes=True,
            ),
            assistant_event=ConversationEventResponse.model_validate(
                result.assistant_event,
                from_attributes=True,
            ),
        ),
    )


@router.post(
    "/stream",
    response_model=None,
    response_class=StreamingResponse,
    summary="Stream chat response",
    status_code=status.HTTP_200_OK,
)
async def stream_chat(
    http_request: Request,
    chat_request: ChatRequest = Depends(ChatRequest.as_form),
    current_user=Depends(get_current_user),
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """
    Stream a chat response.
    """

    logger.info(
        "Starting chat stream.",
        extra={
            "operation": "stream_chat",
            "conversation_id": str(chat_request.conversation_id),
            "user_id": str(current_user.id),
        },
    )

    files = await build_tool_files(
        chat_request.files,
    )

    async def event_generator() -> AsyncIterator[str]:
        try:
            async for chunk in service.stream_chat(
                user_id=current_user.id,
                conversation_id=chat_request.conversation_id,
                message=chat_request.message,
                request_id=http_request.state.context.request_id,
                files=files,
            ):
                yield encode_sse_event(
                    ChatStreamResponse(
                        content=chunk.content,
                        is_final=chunk.is_final,
                        metadata=chunk.metadata,
                    ),
                    event_name=("complete" if chunk.is_final else "message"),
                )

        except asyncio.CancelledError:
            logger.info(
                "Client disconnected from chat stream.",
                extra={
                    "operation": "stream_chat",
                    "conversation_id": str(
                        chat_request.conversation_id,
                    ),
                    "user_id": str(current_user.id),
                },
            )
            raise

        except Exception:
            logger.exception(
                "Chat stream failed.",
                extra={
                    "operation": "stream_chat",
                    "conversation_id": str(
                        chat_request.conversation_id,
                    ),
                    "user_id": str(current_user.id),
                },
            )
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
