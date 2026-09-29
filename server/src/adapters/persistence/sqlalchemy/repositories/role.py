"""
User role repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.role import PermissionModel, RoleModel
from adapters.persistence.sqlalchemy.models.user import User


class RoleRepository:
    """
    Repository for user roles and their permissions.

    Read on every RBAC check (DatabaseRolePermissionProvider), so
    get_for_user() is the hot path: the user's role row, with its
    permissions loaded alongside (RoleModel.permissions is selectin).
    Writes (upsert, create_if_missing) take permission names and create
    any PermissionModel row that doesn't exist yet.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        self._session = session

    async def get_by_name(
        self,
        *,
        name: str,
    ) -> RoleModel | None:
        """
        Return the role named ``name``, or None if it doesn't exist.
        """

        result = await self._session.execute(
            select(RoleModel).where(
                RoleModel.name == name,
            )
        )

        return result.scalar_one_or_none()

    async def get_for_user(
        self,
        *,
        user_id: str,
    ) -> RoleModel | None:
        """
        Return the role row for the user's users.role, or None when the
        user doesn't exist or their role has no row.
        """

        result = await self._session.execute(
            select(RoleModel).join(User, User.role == RoleModel.name).where(User.id == user_id)
        )

        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        name: str,
        permissions: list[str],
        enabled: bool = True,
    ) -> RoleModel:
        """
        Create or replace the role named ``name``. For admin changes and
        tests; startup seeding uses create_if_missing() so it never
        overwrites a change made in the database.
        """

        existing = await self.get_by_name(name=name)

        if existing is not None:
            existing.permissions = await self._permissions(permissions)
            existing.enabled = enabled
            await self._session.flush()
            return existing

        return await self._add(name=name, permissions=permissions, enabled=enabled)

    async def create_if_missing(
        self,
        *,
        name: str,
        permissions: list[str],
    ) -> bool:
        """
        Create the role named ``name`` unless it already exists. Returns
        whether it was created.
        """

        if await self.get_by_name(name=name) is not None:
            return False

        await self._add(name=name, permissions=permissions, enabled=True)
        return True

    async def _add(
        self,
        *,
        name: str,
        permissions: list[str],
        enabled: bool,
    ) -> RoleModel:
        role = RoleModel(
            name=name,
            permissions=await self._permissions(permissions),
            enabled=enabled,
        )
        self._session.add(role)
        await self._session.flush()
        return role

    async def _permissions(self, names: list[str]) -> list[PermissionModel]:
        """
        The PermissionModel rows for ``names``, creating missing ones.
        """

        wanted = sorted(set(names))

        if not wanted:
            return []

        result = await self._session.execute(
            select(PermissionModel).where(PermissionModel.name.in_(wanted)),
        )
        found = {permission.name: permission for permission in result.scalars()}

        for name in wanted:
            if name not in found:
                found[name] = PermissionModel(name=name)
                self._session.add(found[name])

        await self._session.flush()
        return [found[name] for name in wanted]
