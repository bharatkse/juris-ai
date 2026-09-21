"""
E2E: rate-limit and daily-token-quota enforcement, over real HTTP and
real Postgres.

Both checks (api/dependencies/rate_limit.py::enforce_usage_limits,
backed by application/services/usage.py::UsageService) run as a
FastAPI dependency BEFORE POST /chat dispatches to the orchestrator --
so a request that trips either limit never reaches the planner/agent
at all. That means this test needs no LLM mocking: the real
UsageRecordRepository (real Postgres, atomic upsert counters) is used
directly to seed each user's bucket to the boundary, then one real,
unmocked HTTP request either side of that boundary confirms the real
enforcement path end to end.

Requires the real Postgres/Redis docker compose services running
(`./setup.sh --install --dependency postgres
--dependency redis`). Run via `make test-e2e`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from adapters.persistence.sqlalchemy.repositories.usage_record import (
    UsageRecordRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from config.settings import get_settings
from core.constants import ERROR_RATE_LIMIT_EXCEEDED, ERROR_TOKEN_QUOTA_EXCEEDED

# tests/conftest.py's pytest_collection_modifyitems auto-tags every
# test under tests/e2e/ with the "e2e" marker — no pytestmark needed
# here, matching the existing unit/smoke convention.


async def _register_and_login(e2e_client: AsyncClient) -> dict:
    email = f"e2e-quota-{uuid.uuid4().hex[:16]}@example.com"
    password = "Str0ng-E2E-Passw0rd!"

    register_response = await e2e_client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "first_name": "E2E",
            "last_name": "Quota",
        },
    )
    assert register_response.status_code == 201, register_response.text
    user_id = register_response.json()["data"]["id"]

    login_response = await e2e_client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    login_body = login_response.json()
    access_token = (
        login_body["data"]["access_token"]
        if "data" in login_body and login_body["data"]
        else login_body["access_token"]
    )

    return {"user_id": user_id, "headers": {"Authorization": f"Bearer {access_token}"}}


async def _create_conversation(e2e_client: AsyncClient, headers: dict) -> str:
    response = await e2e_client.post(
        "/api/v1/conversations",
        json={},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


@pytest.mark.asyncio
async def test_rate_limit_and_token_quota_are_enforced_with_real_429s(
    e2e_client: AsyncClient,
) -> None:
    settings = get_settings().rate_limit
    assert settings.RATE_LIMIT_ENABLED, (
        "RATE_LIMIT_ENABLED is False in this environment -- this test "
        "verifies real enforcement and needs it on."
    )

    # ==============================================================
    # 1. Per-minute request-rate limit -> 429 RATE_LIMIT_EXCEEDED.
    # ==============================================================
    rate_limit_user = await _register_and_login(e2e_client)
    rate_limit_conversation_id = await _create_conversation(e2e_client, rate_limit_user["headers"])

    minute_window = datetime.now(UTC).replace(second=0, microsecond=0)

    async with session_factory() as session:
        repository = UsageRecordRepository(session=session)
        # Real production code path, called the same number of times
        # RATE_LIMIT_REQUESTS_PER_MINUTE legitimate requests would --
        # brings the bucket to exactly the limit, not over it.
        for _ in range(settings.RATE_LIMIT_REQUESTS_PER_MINUTE):
            await repository.increment_request_count(
                user_id=rate_limit_user["user_id"],
                window_start=minute_window,
            )
        await session.commit()

    over_limit_response = await e2e_client.post(
        "/api/v1/chat",
        data={
            "conversation_id": rate_limit_conversation_id,
            "message": "One request over the limit.",
        },
        headers=rate_limit_user["headers"],
    )

    assert over_limit_response.status_code == 429, over_limit_response.text
    assert (
        over_limit_response.json()["error"]["code"] == ERROR_RATE_LIMIT_EXCEEDED
    ), over_limit_response.text

    # ==============================================================
    # 2. Daily token quota -> 429 TOKEN_QUOTA_EXCEEDED.
    #
    # A separate user/conversation: this must fail on the QUOTA check
    # specifically, so its own per-minute bucket must still be well
    # under the limit.
    # ==============================================================
    quota_user = await _register_and_login(e2e_client)
    quota_conversation_id = await _create_conversation(e2e_client, quota_user["headers"])

    day_window = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    async with session_factory() as session:
        repository = UsageRecordRepository(session=session)
        await repository.increment_tokens(
            user_id=quota_user["user_id"],
            window_start=day_window,
            input_tokens=settings.RATE_LIMIT_DAILY_TOKEN_QUOTA,
            output_tokens=0,
        )
        await session.commit()

    over_quota_response = await e2e_client.post(
        "/api/v1/chat",
        data={
            "conversation_id": quota_conversation_id,
            "message": "One request over the daily token quota.",
        },
        headers=quota_user["headers"],
    )

    assert over_quota_response.status_code == 429, over_quota_response.text
    assert (
        over_quota_response.json()["error"]["code"] == ERROR_TOKEN_QUOTA_EXCEEDED
    ), over_quota_response.text
