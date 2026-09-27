"""
E2E: user memory API, over real HTTP and real Postgres.

Covers what the unit tests cannot: real auth, real 204 bodies, real
cross-user isolation through the HTTP layer, consent withdrawal deleting
data, the forward-only conversation switch, and expiry purging.

Memories are seeded straight into the database through the repository
(extraction is a separate, LLM-backed path); everything a user can do to
them is then exercised through the real API.

Requires the real Postgres/Redis services with migrations applied.
Run via `make test-e2e`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from adapters.persistence.sqlalchemy.models.compliance_log import ComplianceLog
from adapters.persistence.sqlalchemy.models.user_memory import UserMemory
from adapters.persistence.sqlalchemy.repositories.compliance_log import (
    ComplianceLogRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation import (
    ConversationRepository,
)
from adapters.persistence.sqlalchemy.repositories.user import UserRepository
from adapters.persistence.sqlalchemy.repositories.user_memory import (
    UserMemoryRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from application.services.compliance_log import ComplianceLogService
from application.services.user_memory import UserMemoryService, expiry_from, hash_content
from core.enums import ComplianceEventTypeEnum, UserMemoryKindEnum
from rag.models import EmbeddingMetadata

MODEL = "api-test-model"
DIMENSION = 384
VECTOR = [1.0] + [0.0] * (DIMENSION - 1)


class _FixedEmbeddingProvider:
    def __init__(self) -> None:
        self.metadata = EmbeddingMetadata(model_name=MODEL, dimension=DIMENSION)

    async def embed(self, *, texts: list[str]) -> list[list[float]]:
        return [VECTOR for _ in texts]


async def _seed(
    user_id: str,
    *,
    content: str,
    expires_at: datetime | None = None,
    source_conversation_id: str | None = None,
) -> str:
    now = datetime.now(UTC)

    async with session_factory() as session:
        memory = await UserMemoryRepository(session=session).add(
            user_id=user_id,
            kind=UserMemoryKindEnum.PREFERENCE,
            content=content,
            content_hash=hash_content(content),
            embedding=VECTOR,
            embedding_model=MODEL,
            confidence=1.0,
            last_used_at=now,
            expires_at=expires_at or expiry_from(now),
            source_conversation_id=source_conversation_id,
        )
        await session.commit()

        return memory.id


async def _stored_ids(user_id: str) -> set[str]:
    async with session_factory() as session:
        rows = await session.execute(select(UserMemory.id).where(UserMemory.user_id == user_id))

        return set(rows.scalars().all())


async def _register_second_user(client: AsyncClient) -> dict:
    email = f"e2e-other-{uuid.uuid4().hex[:12]}@example.com"
    password = "Str0ng-E2E-Passw0rd!"

    response = await client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "first_name": "Other",
            "last_name": "User",
        },
    )
    assert response.status_code == 201, response.text

    login = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200, login.text
    body = login.json()
    token = body["data"]["access_token"] if body.get("data") else body["access_token"]

    return {
        "user_id": response.json()["data"]["id"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


# ----------------------------------------------------------------------
# Auth
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/memory/settings"),
        ("PUT", "/api/v1/memory/settings"),
        ("GET", "/api/v1/memory/items"),
        ("GET", f"/api/v1/memory/items/umem_{'a' * 32}"),
        ("DELETE", f"/api/v1/memory/items/umem_{'a' * 32}"),
    ],
)
async def test_memory_endpoints_require_authentication(
    e2e_client: AsyncClient,
    method: str,
    path: str,
) -> None:
    response = await e2e_client.request(method, path, json={"enabled": True})

    assert response.status_code == 401


# ----------------------------------------------------------------------
# Consent
# ----------------------------------------------------------------------


async def test_memory_is_off_by_default_and_can_be_turned_on(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    headers = registered_user["headers"]

    initial = await e2e_client.get("/api/v1/memory/settings", headers=headers)
    assert initial.status_code == 200
    assert initial.json()["data"]["enabled"] is False

    turned_on = await e2e_client.put(
        "/api/v1/memory/settings",
        json={"enabled": True},
        headers=headers,
    )
    assert turned_on.status_code == 200
    assert turned_on.json()["data"]["enabled"] is True
    assert turned_on.json()["data"]["consent_updated_at"] is not None

    again = await e2e_client.get("/api/v1/memory/settings", headers=headers)
    assert again.json()["data"]["enabled"] is True


async def test_turning_memory_off_deletes_every_saved_memory(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    headers = registered_user["headers"]
    user_id = registered_user["user_id"]

    await e2e_client.put("/api/v1/memory/settings", json={"enabled": True}, headers=headers)

    await _seed(user_id, content="one")
    await _seed(user_id, content="two")
    assert len(await _stored_ids(user_id)) == 2

    off = await e2e_client.put(
        "/api/v1/memory/settings",
        json={"enabled": False},
        headers=headers,
    )

    assert off.status_code == 200
    assert off.json()["data"]["enabled"] is False
    assert await _stored_ids(user_id) == set()


async def test_withdrawing_consent_does_not_touch_another_users_memories(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    other = await _register_second_user(e2e_client)

    await e2e_client.put(
        "/api/v1/memory/settings",
        json={"enabled": True},
        headers=registered_user["headers"],
    )
    await e2e_client.put(
        "/api/v1/memory/settings",
        json={"enabled": True},
        headers=other["headers"],
    )

    mine = await _seed(registered_user["user_id"], content="mine")
    theirs = await _seed(other["user_id"], content="theirs")

    await e2e_client.put(
        "/api/v1/memory/settings",
        json={"enabled": False},
        headers=registered_user["headers"],
    )

    assert mine not in await _stored_ids(registered_user["user_id"])
    assert theirs in await _stored_ids(other["user_id"])


# ----------------------------------------------------------------------
# List / view / delete, and isolation over HTTP
# ----------------------------------------------------------------------


async def test_list_view_and_delete_own_memory(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    headers = registered_user["headers"]
    memory_id = await _seed(registered_user["user_id"], content="prefers concise answers")

    listed = await e2e_client.get("/api/v1/memory/items", headers=headers)
    assert listed.status_code == 200
    data = listed.json()["data"]
    assert [item["id"] for item in data["items"]] == [memory_id]
    assert data["items"][0]["content"] == "prefers concise answers"
    assert data["pagination"]["total"] == 1
    # Internals never reach the client.
    assert "embedding" not in data["items"][0]
    assert "content_hash" not in data["items"][0]
    assert "user_id" not in data["items"][0]

    viewed = await e2e_client.get(f"/api/v1/memory/items/{memory_id}", headers=headers)
    assert viewed.status_code == 200
    assert viewed.json()["data"]["id"] == memory_id

    deleted = await e2e_client.delete(f"/api/v1/memory/items/{memory_id}", headers=headers)
    assert deleted.status_code == 204
    assert deleted.content == b""

    assert await _stored_ids(registered_user["user_id"]) == set()
    assert (
        await e2e_client.get(f"/api/v1/memory/items/{memory_id}", headers=headers)
    ).status_code == 404
    assert (
        await e2e_client.delete(f"/api/v1/memory/items/{memory_id}", headers=headers)
    ).status_code == 404


async def test_a_user_cannot_list_view_or_delete_another_users_memory(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    other = await _register_second_user(e2e_client)
    theirs = await _seed(other["user_id"], content="someone else's private fact")

    mine = registered_user["headers"]

    listed = await e2e_client.get("/api/v1/memory/items", headers=mine)
    assert listed.json()["data"]["items"] == []
    assert listed.json()["data"]["pagination"]["total"] == 0

    assert (await e2e_client.get(f"/api/v1/memory/items/{theirs}", headers=mine)).status_code == 404
    assert (
        await e2e_client.delete(f"/api/v1/memory/items/{theirs}", headers=mine)
    ).status_code == 404

    # ...and it is still there for its owner.
    assert theirs in await _stored_ids(other["user_id"])
    owner_view = await e2e_client.get(f"/api/v1/memory/items/{theirs}", headers=other["headers"])
    assert owner_view.status_code == 200


async def test_a_malformed_memory_id_is_rejected_before_it_reaches_the_database(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    response = await e2e_client.get(
        "/api/v1/memory/items/not-a-memory-id",
        headers=registered_user["headers"],
    )

    assert response.status_code == 422


async def test_pagination_limit_is_bounded(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    response = await e2e_client.get(
        "/api/v1/memory/items?limit=100000",
        headers=registered_user["headers"],
    )

    assert response.status_code == 422


# ----------------------------------------------------------------------
# Per-conversation "don't remember this" -- forward-only
# ----------------------------------------------------------------------


async def test_conversation_switch_is_forward_only(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    headers = registered_user["headers"]
    already_saved = await _seed(
        registered_user["user_id"],
        content="saved before the switch was turned on",
        source_conversation_id=conversation_id,
    )

    response = await e2e_client.put(
        f"/api/v1/conversations/{conversation_id}/memory",
        json={"memory_disabled": True},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["memory_disabled"] is True
    assert "already saved is unchanged" in response.json()["message"]

    fetched = await e2e_client.get(f"/api/v1/conversations/{conversation_id}", headers=headers)
    assert fetched.json()["data"]["memory_disabled"] is True

    # Forward-only: the fact extracted from this conversation earlier is
    # untouched, and still listed.
    assert already_saved in await _stored_ids(registered_user["user_id"])

    listed = await e2e_client.get("/api/v1/memory/items", headers=headers)
    assert [item["id"] for item in listed.json()["data"]["items"]] == [already_saved]

    back = await e2e_client.put(
        f"/api/v1/conversations/{conversation_id}/memory",
        json={"memory_disabled": False},
        headers=headers,
    )
    assert back.json()["data"]["memory_disabled"] is False


async def test_a_user_cannot_flip_the_switch_on_another_users_conversation(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    other = await _register_second_user(e2e_client)

    response = await e2e_client.put(
        f"/api/v1/conversations/{conversation_id}/memory",
        json={"memory_disabled": True},
        headers=other["headers"],
    )

    assert response.status_code == 404

    owner = await e2e_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=registered_user["headers"],
    )
    assert owner.json()["data"]["memory_disabled"] is False


# ----------------------------------------------------------------------
# Expiry: excluded from retrieval, and actually removed by a purge
# ----------------------------------------------------------------------


async def test_expired_memory_is_excluded_from_retrieval_and_removed_by_a_purging_call(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    headers = registered_user["headers"]
    user_id = registered_user["user_id"]

    await e2e_client.put("/api/v1/memory/settings", json={"enabled": True}, headers=headers)

    live = await _seed(user_id, content="live fact")
    expired = await _seed(
        user_id,
        content="expired fact",
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    assert await _stored_ids(user_id) == {live, expired}

    # 1. Retrieval never returns the expired row -- even though it is an
    #    exact vector match and is still physically in the table.
    async with session_factory() as session:
        service = UserMemoryService(
            session=session,
            repository=UserMemoryRepository(session=session),
            user_repository=UserRepository(session=session),
            conversation_repository=ConversationRepository(session=session),
            embedding_provider=_FixedEmbeddingProvider(),
            compliance_log=ComplianceLogService(
                session=session,
                repository=ComplianceLogRepository(session=session),
            ),
        )
        items = await service.retrieve_for_prompt(
            user_id=user_id, conversation_id=conversation_id, query="anything"
        )
        await session.commit()

    assert [item.id for item in items] == [live]
    assert expired in await _stored_ids(user_id), "retrieval must not delete; only purge does"

    # 2. A purge-triggering call (the list endpoint) really removes it.
    listed = await e2e_client.get("/api/v1/memory/items", headers=headers)

    assert [item["id"] for item in listed.json()["data"]["items"]] == [live]
    assert await _stored_ids(user_id) == {live}


async def test_purge_only_removes_the_callers_expired_rows(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    other = await _register_second_user(e2e_client)
    long_ago = datetime.now(UTC) - timedelta(days=400)

    theirs_expired = await _seed(other["user_id"], content="their stale fact", expires_at=long_ago)
    await _seed(registered_user["user_id"], content="my stale fact", expires_at=long_ago)

    await e2e_client.get("/api/v1/memory/items", headers=registered_user["headers"])

    assert await _stored_ids(registered_user["user_id"]) == set()
    # Their expired row is not mine to purge; it goes when *they* trigger one.
    assert theirs_expired in await _stored_ids(other["user_id"])


async def test_expired_rows_do_not_count_toward_the_per_user_cap(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    user_id = registered_user["user_id"]

    async with session_factory() as session:
        repository = UserMemoryRepository(session=session)
        now = datetime.now(UTC)

        await _seed(user_id, content="stale", expires_at=now - timedelta(days=1))
        await _seed(user_id, content="fresh")

        visible = await repository.count_visible(user_id=user_id, now=now)

        stored = (
            await session.execute(
                select(func.count()).select_from(UserMemory).where(UserMemory.user_id == user_id)
            )
        ).scalar_one()

    # The cap counts what the user can see, so an expired row is not
    # held against them even before it has been purged.
    assert (visible, stored) == (1, 2)


# ----------------------------------------------------------------------
# Compliance log: identifiers, counts and hashes only
# ----------------------------------------------------------------------

_SECRET_TEXT = "the-client-is-acme-holdings-in-a-sealed-arbitration"


async def _memory_audit_rows(user_id: str) -> list[ComplianceLog]:
    async with session_factory() as session:
        rows = await session.execute(
            select(ComplianceLog)
            .where(
                ComplianceLog.user_id == user_id,
                ComplianceLog.event_type == ComplianceEventTypeEnum.MEMORY_OPERATION,
            )
            .order_by(ComplianceLog.created_at)
        )

        return list(rows.scalars().all())


async def test_memory_operations_are_audited_without_ever_logging_memory_text(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    headers = registered_user["headers"]
    user_id = registered_user["user_id"]

    await e2e_client.put("/api/v1/memory/settings", json={"enabled": True}, headers=headers)

    deleted_id = await _seed(user_id, content=_SECRET_TEXT)
    await _seed(user_id, content=_SECRET_TEXT + " (second)")

    assert (
        await e2e_client.delete(f"/api/v1/memory/items/{deleted_id}", headers=headers)
    ).status_code == 204

    await e2e_client.put("/api/v1/memory/settings", json={"enabled": False}, headers=headers)

    rows = await _memory_audit_rows(user_id)
    by_operation = {row.payload["operation"]: row for row in rows}

    assert list(by_operation) == ["consent_granted", "deleted", "consent_withdrawn"]

    deleted = by_operation["deleted"]
    assert deleted.resource_type == "user_memory"
    assert deleted.resource_id == deleted_id
    assert deleted.payload["memory_id"] == deleted_id
    assert deleted.payload["content_hash"] == hash_content(_SECRET_TEXT)

    # One memory was left when consent was withdrawn.
    assert by_operation["consent_withdrawn"].payload["count"] == 1

    # The compliance log is insert-only and kept indefinitely, so the
    # text must not be anywhere in any row -- payload or otherwise.
    for row in rows:
        assert "acme" not in str(row.payload).lower()
        assert _SECRET_TEXT not in str(row.payload)
        assert set(row.payload) <= {"operation", "memory_id", "content_hash", "kind", "count"}


async def test_a_purge_is_audited_with_a_count_and_no_content(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    user_id = registered_user["user_id"]

    await _seed(user_id, content="stale", expires_at=datetime.now(UTC) - timedelta(days=1))
    await _seed(user_id, content="stale too", expires_at=datetime.now(UTC) - timedelta(days=2))

    await e2e_client.get("/api/v1/memory/items", headers=registered_user["headers"])

    (row,) = await _memory_audit_rows(user_id)

    assert row.payload == {"operation": "purged_expired", "count": 2}
