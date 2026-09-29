"""
Authentication and ownership on the user profile routes, asserted through
the real app, router, auth dependency and global exception handler (not by
calling the route function directly), so the status and error code a
client actually receives are what's tested.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from api.dependencies.auth import get_current_user
from api.dependencies.user import get_user_service
from main import app
from tests.unit.factories.user import UserFactory

USER_A = "user_" + "a" * 32
USER_B = "user_" + "b" * 32
PATCH_BODY = {"first_name": "Changed"}


@pytest.fixture
def service() -> MagicMock:
    service = MagicMock()
    service.get_or_raise = AsyncMock(side_effect=lambda *, user_id: UserFactory.build(id=user_id))
    service.update = AsyncMock(
        side_effect=lambda *, user_id, request: UserFactory.build(id=user_id)
    )
    return service


@pytest.fixture
async def client(service: MagicMock) -> AsyncIterator[AsyncClient]:
    """
    Real app; the caller is USER_A and the user service is a mock.
    """

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=USER_A, is_active=True)
    app.dependency_overrides[get_user_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def anonymous_client(service: MagicMock) -> AsyncIterator[AsyncClient]:
    """
    Real app and real ``get_current_user``: no bearer token is sent.
    """

    app.dependency_overrides[get_user_service] = lambda: service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthenticated_requests_are_rejected(
    anonymous_client: AsyncClient, service: MagicMock
) -> None:
    get_response = await anonymous_client.get(f"/api/v1/users/{USER_A}")
    patch_response = await anonymous_client.patch(f"/api/v1/users/{USER_A}", json=PATCH_BODY)

    assert get_response.status_code == 401
    assert patch_response.status_code == 401
    service.get_or_raise.assert_not_awaited()
    service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_reading_another_user_is_forbidden(client: AsyncClient, service: MagicMock) -> None:
    response = await client.get(f"/api/v1/users/{USER_B}")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    service.get_or_raise.assert_not_awaited()


@pytest.mark.asyncio
async def test_updating_another_user_is_forbidden(client: AsyncClient, service: MagicMock) -> None:
    response = await client.patch(f"/api/v1/users/{USER_B}", json=PATCH_BODY)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_reading_own_profile_is_allowed(client: AsyncClient, service: MagicMock) -> None:
    response = await client.get(f"/api/v1/users/{USER_A}")

    assert response.status_code == 200
    assert response.json()["data"]["id"] == USER_A
    service.get_or_raise.assert_awaited_once_with(user_id=USER_A)


@pytest.mark.asyncio
async def test_updating_own_profile_is_allowed(client: AsyncClient, service: MagicMock) -> None:
    response = await client.patch(f"/api/v1/users/{USER_A}", json=PATCH_BODY)

    assert response.status_code == 200
    assert response.json()["data"]["id"] == USER_A
    service.update.assert_awaited_once()
    assert service.update.await_args.kwargs["user_id"] == USER_A
