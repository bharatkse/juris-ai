"""
User role and permission persistence models.

The source of truth for what each user role may do (application/
authorization/rbac/roles.py, DatabaseRolePermissionProvider):

    users.role --(name)--> roles --(role_permissions)--> permissions

A permission is one ActionTypeEnum value (read, analyze, generate, send,
...). What a role grants is the set of role_permissions rows, so an admin
can change it without a code deploy -- the same approach as
agent_policies for agent tool access.

users.role deliberately has no foreign key to roles: a user whose role
has no row (or a disabled one) simply has no permissions, which is the
fail-closed outcome, and the column can be added to existing users before
the default roles are seeded at startup (wiring/factories/roles.py).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id",
        String(64),
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        String(64),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class PermissionModel(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    One grantable action type. ``name`` is an ActionTypeEnum value; a name
    that isn't one grants nothing (the provider ignores it).
    """

    __tablename__ = "permissions"
    _id_prefix = "perm"

    name: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )


class RoleModel(
    Base,
    PrimaryKeyMixin,
    TimestampMixin,
):
    """
    One user role. Its permissions govern both RBAC checks: which
    capabilities a user may request (before planning) and which concrete
    actions they may take.
    """

    __tablename__ = "roles"
    _id_prefix = "role"

    name: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        unique=True,
        index=True,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # selectin: a role is always read together with its permissions.
    permissions: Mapped[list[PermissionModel]] = relationship(
        secondary=role_permissions,
        lazy="selectin",
        order_by=PermissionModel.name,
    )

    @property
    def permission_names(self) -> list[str]:
        return [permission.name for permission in self.permissions]
