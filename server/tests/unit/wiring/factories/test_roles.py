"""
Default role seeding: creates missing roles, never changes existing ones.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from core.constants import DEFAULT_USER_ROLE
from wiring.factories import roles as roles_module
from wiring.factories.roles import DEFAULT_ROLES, seed_default_roles


def test_default_roles() -> None:
    assert DEFAULT_USER_ROLE == "member"
    assert set(DEFAULT_ROLES["member"]) == {"read", "analyze", "generate", "send"}
    assert set(DEFAULT_ROLES["reader"]) == {"read", "analyze", "generate"}


async def test_seed_creates_only_missing_roles_and_commits() -> None:
    session = MagicMock()
    session.commit = AsyncMock()

    @asynccontextmanager
    async def session_factory():
        yield session

    repository = MagicMock()
    repository.create_if_missing = AsyncMock(return_value=False)

    with (
        patch.object(roles_module, "session_factory", session_factory),
        patch.object(roles_module, "RoleRepository", return_value=repository),
    ):
        await seed_default_roles()

    assert {call.kwargs["name"] for call in repository.create_if_missing.await_args_list} == set(
        DEFAULT_ROLES
    )
    repository.upsert.assert_not_called()
    session.commit.assert_awaited_once()
