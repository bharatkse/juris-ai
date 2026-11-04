"""
E2E: what a client sees of an error (Phase 4, P4-EL).

Over real HTTP and Postgres. A server error's own text never reaches the
client: it gets the error code, a generic message and the request ID (in
the error, the response metadata and X-Request-ID) to quote. A client error
keeps its message. On /chat/stream an error after the stream started ends
it with one `error` event built the same way.
"""

from __future__ import annotations

import json
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from api.exception_handlers import GENERIC_ERROR_MESSAGE
from application.services.chat import ChatService
from core.constants import ERROR_INTERNAL_SERVER_ERROR
from core.exceptions.client import ClientProviderError

pytestmark = pytest.mark.asyncio

INTERNAL_TEXT = "upstream 500: invalid api key gsk_live_e2e for org-4471"


async def test_a_server_error_on_chat_is_generic_and_carries_the_request_id(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hermetic_llm,
) -> None:
    async def fail(self, **_kwargs):
        raise ClientProviderError(INTERNAL_TEXT)

    with patch.object(ChatService, "_build_chat_request", fail):
        response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": "What is an FIR?"},
            headers=registered_user["headers"],
        )

    assert response.status_code == 502, response.text
    body = response.json()
    request_id = response.headers["x-request-id"]
    assert body["error"] == {
        "code": "CLIENT_PROVIDER_ERROR",
        "message": GENERIC_ERROR_MESSAGE,
        "request_id": request_id,
    }
    assert body["metadata"]["request_id"] == request_id
    assert "gsk_live" not in response.text


async def test_an_unexpected_failure_mid_stream_ends_it_with_a_generic_error_event(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hermetic_llm,
) -> None:
    async def fail(self, **_kwargs):
        raise RuntimeError(INTERNAL_TEXT)

    with patch.object(ChatService, "_build_chat_request", fail):
        async with e2e_client.stream(
            "POST",
            "/api/v1/chat/stream",
            data={"conversation_id": conversation_id, "message": "What is an FIR?"},
            headers=registered_user["headers"],
        ) as response:
            assert response.status_code == 200
            request_id = response.headers["x-request-id"]
            body = (await response.aread()).decode()

    events = [block for block in body.split("\n\n") if block.strip()]
    assert len(events) == 1, body
    name, data = events[0].split("\n", 1)
    assert name == "event: error"
    error = json.loads(data.removeprefix("data: "))
    assert error["code"] == ERROR_INTERNAL_SERVER_ERROR
    assert error["message"] == GENERIC_ERROR_MESSAGE
    assert error["request_id"] == request_id
    assert "gsk_live" not in body


async def test_a_client_error_keeps_its_message_and_carries_the_request_id(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    response = await e2e_client.get(
        f"/api/v1/conversations/conv_{uuid4().hex}",
        headers=registered_user["headers"],
    )

    assert response.status_code == 404, response.text
    error = response.json()["error"]
    assert error["message"] != GENERIC_ERROR_MESSAGE
    assert error["request_id"] == response.headers["x-request-id"]
