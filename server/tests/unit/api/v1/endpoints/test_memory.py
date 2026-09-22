"""
Unit tests for the user memory API endpoints.

Handlers are called directly with mocked services, matching this
suite's convention (see test_conversations.py). Real HTTP behaviour --
auth, 204 bodies, cross-user 404s, expiry purging -- is covered in
tests/e2e/test_user_memory_api.py.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Response, status

from api.schemas.memory import UpdateMemorySettingsRequest
from api.utilities.api_response import ApiResponse
from api.v1.endpoints.memory import (
    delete_memory,
    get_memory,
    get_memory_settings,
    list_memories,
    update_memory_settings,
)
from core.exceptions.httpx import NotFoundError
from main import app

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)

# Real ids are "umem_" + 32 hex chars; the response schema enforces that.
MEMORY_ID = "umem_" + "a" * 32


def _current_user(*, enabled: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        id="user_a",
        memory_enabled=enabled,
        memory_consent_updated_at=None,
    )


def _memory_row(memory_id: str = MEMORY_ID) -> SimpleNamespace:
    return SimpleNamespace(
        id=memory_id,
        kind="preference",
        content="prefers concise answers",
        status="active",
        confidence=1.0,
        source_conversation_id=None,
        last_used_at=NOW,
        expires_at=NOW,
        created_at=NOW,
    )


def _body(response: ApiResponse) -> dict:
    import json

    return json.loads(response.body)


async def test_settings_default_to_off() -> None:
    response = await get_memory_settings(current_user=_current_user(enabled=False))

    assert _body(response)["data"] == {"enabled": False}


async def test_turning_memory_on_calls_the_service_with_the_callers_id() -> None:
    service = MagicMock()
    service.set_consent = AsyncMock(return_value=_current_user(enabled=True))

    response = await update_memory_settings(
        request=UpdateMemorySettingsRequest(enabled=True),
        current_user=_current_user(),
        service=service,
    )

    service.set_consent.assert_awaited_once_with(user_id="user_a", enabled=True)
    assert _body(response)["data"]["enabled"] is True
    assert "turned on" in _body(response)["message"]


async def test_turning_memory_off_tells_the_user_everything_was_deleted() -> None:
    service = MagicMock()
    service.set_consent = AsyncMock(return_value=_current_user(enabled=False))

    response = await update_memory_settings(
        request=UpdateMemorySettingsRequest(enabled=False),
        current_user=_current_user(enabled=True),
        service=service,
    )

    service.set_consent.assert_awaited_once_with(user_id="user_a", enabled=False)
    assert "deleted" in _body(response)["message"]


async def test_list_scopes_to_the_authenticated_user_and_paginates() -> None:
    service = MagicMock()
    service.list_memories = AsyncMock(return_value=([_memory_row()], 5))

    response = await list_memories(
        offset=0,
        limit=2,
        current_user=_current_user(),
        service=service,
    )

    service.list_memories.assert_awaited_once_with(user_id="user_a", limit=2, offset=0)

    body = _body(response)["data"]

    assert [item["id"] for item in body["items"]] == [MEMORY_ID]
    assert body["pagination"] == {"offset": 0, "limit": 2, "total": 5, "has_more": True}
    # Nothing internal leaks into the item shape.
    assert set(body["items"][0]) <= {
        "id",
        "kind",
        "content",
        "status",
        "confidence",
        "source_conversation_id",
        "last_used_at",
        "expires_at",
        "created_at",
    }


async def test_get_returns_the_memory_and_uses_the_callers_id() -> None:
    service = MagicMock()
    service.get_memory = AsyncMock(return_value=_memory_row())

    response = await get_memory(
        memory_id=MEMORY_ID,
        current_user=_current_user(),
        service=service,
    )

    service.get_memory.assert_awaited_once_with(user_id="user_a", memory_id=MEMORY_ID)
    assert _body(response)["data"]["content"] == "prefers concise answers"


async def test_get_propagates_not_found() -> None:
    service = MagicMock()
    service.get_memory = AsyncMock(side_effect=NotFoundError(message="Memory not found."))

    with pytest.raises(NotFoundError):
        await get_memory(memory_id="umem_x", current_user=_current_user(), service=service)


async def test_delete_returns_an_empty_204() -> None:
    service = MagicMock()
    service.delete_memory = AsyncMock()

    response = await delete_memory(
        memory_id=MEMORY_ID,
        current_user=_current_user(),
        service=service,
    )

    service.delete_memory.assert_awaited_once_with(user_id="user_a", memory_id=MEMORY_ID)

    assert isinstance(response, Response)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.body == b""


def _openapi_text(path: str, method: str) -> str:
    operation = app.openapi()["paths"][path][method]

    return f'{operation.get("summary", "")} {operation.get("description", "")}'


def test_conversation_toggle_is_documented_as_forward_only() -> None:
    text = _openapi_text("/api/v1/conversations/{conversation_id}/memory", "put").lower()

    assert "forward-only" in text
    assert "does not delete" in text


def test_conversation_toggle_request_schema_says_it_does_not_scrub_history() -> None:
    schema = app.openapi()["components"]["schemas"]["UpdateConversationMemoryRequest"]
    description = schema["properties"]["memory_disabled"]["description"].lower()

    assert "forward-only" in description
    assert "does not delete" in description


def test_consent_off_is_documented_as_permanent_deletion() -> None:
    text = _openapi_text("/api/v1/memory/settings", "put").lower()

    assert "permanently deletes" in text
    assert "cannot be undone" in text
