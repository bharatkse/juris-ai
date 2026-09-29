"""
DatabaseRolePermissionProvider: a user's permissions are their role's,
read from the database, and anything unexpected grants nothing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from application.authorization.rbac import roles as roles_module
from application.authorization.rbac.roles import DatabaseRolePermissionProvider
from core.enums import ActionTypeEnum

USER = "user_" + "a" * 32


def _role(*names: str, enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(name="member", enabled=enabled, permission_names=list(names))


@pytest.fixture
def repository() -> MagicMock:
    repository = MagicMock()
    repository.get_for_user = AsyncMock()
    return repository


@pytest.fixture
def provider(repository: MagicMock):
    @asynccontextmanager
    async def session_factory():
        yield MagicMock()

    with patch.object(roles_module, "RoleRepository", return_value=repository):
        yield DatabaseRolePermissionProvider(session_factory=session_factory)


async def test_grants_the_roles_permissions(provider, repository: MagicMock) -> None:
    repository.get_for_user.return_value = _role("read", "analyze", "send")

    granted = await provider.permissions_for(user_id=USER)

    assert granted == {ActionTypeEnum.READ, ActionTypeEnum.ANALYZE, ActionTypeEnum.SEND}
    repository.get_for_user.assert_awaited_once_with(user_id=USER)


async def test_unknown_user_or_role_grants_nothing(provider, repository: MagicMock) -> None:
    repository.get_for_user.return_value = None

    assert await provider.permissions_for(user_id=USER) == frozenset()


async def test_disabled_role_grants_nothing(provider, repository: MagicMock) -> None:
    repository.get_for_user.return_value = _role("read", "send", enabled=False)

    assert await provider.permissions_for(user_id=USER) == frozenset()


async def test_unknown_permission_names_are_ignored(provider, repository: MagicMock) -> None:
    repository.get_for_user.return_value = _role("read", "launch_missiles")

    assert await provider.permissions_for(user_id=USER) == {ActionTypeEnum.READ}
