"""
E2E: user profile routes are authenticated and owner-scoped, over real
HTTP, real JWTs and real Postgres.

A user may read and update only their own profile: no token is a 401,
another user's id is a 403, and a refused update leaves the other
user's row untouched.

Requires the real Postgres/Redis services with migrations applied.
Run via `make test-e2e`.
"""

from __future__ import annotations

from httpx import AsyncClient


def _url(user: dict) -> str:
    return f"/api/v1/users/{user['user_id']}"


async def test_profile_routes_require_a_token(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    get_response = await e2e_client.get(_url(registered_user))
    patch_response = await e2e_client.patch(
        _url(registered_user),
        json={"first_name": "Anonymous"},
    )

    assert get_response.status_code == 401
    assert patch_response.status_code == 401


async def test_user_cannot_read_or_update_another_users_profile(
    e2e_client: AsyncClient,
    registered_user: dict,
    second_registered_user: dict,
) -> None:
    attacker, victim = registered_user, second_registered_user

    read_response = await e2e_client.get(_url(victim), headers=attacker["headers"])
    update_response = await e2e_client.patch(
        _url(victim),
        json={"first_name": "Hijacked", "phone_number": "9999999999"},
        headers=attacker["headers"],
    )

    assert read_response.status_code == 403, read_response.text
    assert read_response.json()["error"]["code"] == "FORBIDDEN"
    assert victim["email"] not in read_response.text
    assert update_response.status_code == 403, update_response.text

    victim_view = await e2e_client.get(_url(victim), headers=victim["headers"])

    assert victim_view.status_code == 200, victim_view.text
    profile = victim_view.json()["data"]
    assert profile["first_name"] == "E2E"
    # The response envelope omits null fields.
    assert profile.get("phone_number") is None


async def test_user_can_read_and_update_own_profile(
    e2e_client: AsyncClient,
    registered_user: dict,
) -> None:
    read_response = await e2e_client.get(
        _url(registered_user),
        headers=registered_user["headers"],
    )

    assert read_response.status_code == 200, read_response.text
    assert read_response.json()["data"]["email"] == registered_user["email"]

    update_response = await e2e_client.patch(
        _url(registered_user),
        json={"first_name": "Renamed"},
        headers=registered_user["headers"],
    )

    assert update_response.status_code == 200, update_response.text

    reread = await e2e_client.get(
        _url(registered_user),
        headers=registered_user["headers"],
    )

    assert reread.json()["data"]["first_name"] == "Renamed"
