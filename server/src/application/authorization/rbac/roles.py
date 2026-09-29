"""
User role permission resolution.

A user's permissions are their role's, and both live in the database:
users.role names the role, and its role_permissions rows link it to the
permissions (action types) it grants. Changing
what a role grants (or a user's role) is a data change, not a deploy --
the same approach as agent_policies for agent tool access.

RBAC is the coarse gate on what a user may ask for. It is not the safety
boundary for side effects: every send is still a gated tool call that
runs only after the same user approves that exact message
(agentic/tools/constants.py GATED_TOOLS, ApprovalRecordVerifier).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.role import RoleRepository
from core.enums import ActionTypeEnum

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class RolePermissionProvider(Protocol):
    """
    Resolves the action types a user's role grants.
    """

    async def permissions_for(
        self,
        *,
        user_id: str,
    ) -> frozenset[ActionTypeEnum]: ...


class DatabaseRolePermissionProvider:
    """
    RolePermissionProvider backed by users.role and the roles table.

    Fails closed: an unknown user, a role with no row, a disabled role, or
    a permission name that isn't an ActionTypeEnum value grants nothing.

    Takes a session FACTORY: it is built once at startup
    (wiring/factories/authorization.py) and shared across concurrent
    requests, so it opens a fresh session per lookup -- the same pattern
    as DatabaseAgentPolicyProvider.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    async def permissions_for(
        self,
        *,
        user_id: str,
    ) -> frozenset[ActionTypeEnum]:
        async with self._session_factory() as session:
            role = await RoleRepository(session=session).get_for_user(user_id=user_id)

        if role is None or not role.enabled:
            logger.warning(
                "User has no enabled role; granting no permissions.",
                extra={"user_id": user_id, "role": role.name if role else None},
            )
            return frozenset()

        permissions: set[ActionTypeEnum] = set()

        for name in role.permission_names:
            try:
                permissions.add(ActionTypeEnum(name))
            except ValueError:
                logger.warning(
                    "Ignoring unknown permission on a role.",
                    extra={"role": role.name, "permission": name},
                )

        return frozenset(permissions)
