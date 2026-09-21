"""
Shared fixtures for API-level end-to-end tests.

These tests exercise the real FastAPI app (real Postgres, real Redis,
real Postgres-backed LangGraph checkpointer) over httpx.AsyncClient --
no mock ORM, no fake HTTP layer. The only things ever mocked are the
genuinely external, non-deterministic, or costly boundaries a test
would otherwise have no control over: live LLM "thinking" calls and
an outbound MCP (Gmail/Slack) network call -- never the application's
own routing, persistence, authorization, or HITL logic. See each
test module's own docstring for what it mocks and why.

Run via `make test-e2e` (needs the real docker compose Postgres/Redis
services up -- `./setup.sh --install --dependency postgres
--dependency redis`), not part of the fast unit-test loop.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from adapters.persistence.sqlalchemy.session import dispose_engine
from main import app as fastapi_app


@pytest_asyncio.fixture
async def e2e_client() -> AsyncIterator[AsyncClient]:
    """
    A real httpx client wired directly to the real FastAPI app via
    ASGITransport (no network socket, but every other layer -- routing,
    middleware, dependency injection, exception handlers -- runs
    exactly as it would under uvicorn).

    httpx's ASGITransport does not drive the app's lifespan on its
    own, so it's driven explicitly here via
    app.router.lifespan_context() -- this is what actually runs
    main.py's lifespan(): seeds default agent policies, opens the
    real AsyncPostgresSaver checkpointer, and builds the real
    AIOrchestrator stored on app.state, all against the real
    Postgres/Redis this test run points at.
    """

    # session_factory's shared engine may be holding connections
    # opened under a different event loop from a previous test module
    # (each test function gets its own loop under pytest-asyncio's
    # default function-scoped loop) -- discard them before first use,
    # mirroring tests/smoke/conftest.py's rag_smoke_environment fixture.
    await dispose_engine()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        transport = ASGITransport(app=fastapi_app)

        async with AsyncClient(
            transport=transport,
            base_url="http://e2e.testserver",
        ) as client:
            yield client

    await dispose_engine()


@pytest_asyncio.fixture
async def registered_user(e2e_client: AsyncClient) -> dict:
    """
    Register and log in a fresh user through the real HTTP API --
    the same path any real client takes, not a DB shortcut.

    Returns {"user_id", "email", "headers"} -- "headers" is ready to
    merge into any authenticated request.
    """

    email = f"e2e-{uuid.uuid4().hex[:16]}@example.com"
    password = "Str0ng-E2E-Passw0rd!"

    register_response = await e2e_client.post(
        "/api/v1/users",
        json={
            "email": email,
            "password": password,
            "confirm_password": password,
            "first_name": "E2E",
            "last_name": "Tester",
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
    # /auth/login returns LoginResponse's fields directly (response_model=None,
    # and the endpoint returns the pydantic model bare rather than wrapped
    # in ApiResponse) -- not the {"data": {...}} envelope most other
    # endpoints use. Handle both shapes defensively rather than assume
    # one silently breaks the other if it's ever made consistent.
    access_token = (
        login_body["data"]["access_token"]
        if "data" in login_body and login_body["data"]
        else login_body["access_token"]
    )

    return {
        "user_id": user_id,
        "email": email,
        "headers": {"Authorization": f"Bearer {access_token}"},
    }


@pytest_asyncio.fixture
async def conversation_id(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> str:
    """
    Create a real conversation for registered_user, via the real HTTP
    API.
    """

    response = await e2e_client.post(
        "/api/v1/conversations",
        json={},
        headers=registered_user["headers"],
    )
    assert response.status_code == 201, response.text

    return response.json()["data"]["id"]
