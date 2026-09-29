"""
Default user roles, seeded at startup.

The database is the source of truth for roles and their permissions
(adapters/persistence/sqlalchemy/models/role.py). This only makes sure the
two roles the application relies on exist on a fresh database: a role
that already exists is left exactly as it is, so a permission an admin
added or removed survives restarts and deploys. (Unlike
seed_default_agent_policies(), which rewrites its rows on every startup.)

- member (the users.role default, core.constants.DEFAULT_USER_ROLE):
  research plus send. Safe to grant broadly because every send is a gated
  tool call that runs only after the same user approves that exact
  message; RBAC is the coarse gate, not the safety boundary.
- reader: research only; requests classified SEND are refused.
"""

from __future__ import annotations

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.role import RoleRepository
from adapters.persistence.sqlalchemy.session import session_factory
from core.constants import DEFAULT_USER_ROLE
from core.enums import ActionTypeEnum

logger = get_logger(__name__)

_RESEARCH = [
    ActionTypeEnum.READ.value,
    ActionTypeEnum.ANALYZE.value,
    ActionTypeEnum.GENERATE.value,
]

DEFAULT_ROLES: dict[str, list[str]] = {
    DEFAULT_USER_ROLE: [*_RESEARCH, ActionTypeEnum.SEND.value],
    "reader": list(_RESEARCH),
}


async def seed_default_roles() -> None:
    """
    Create each default role that doesn't exist yet. Idempotent; never
    changes an existing role.
    """

    async with session_factory() as session:
        repository = RoleRepository(session=session)

        created = [
            name
            for name, permissions in DEFAULT_ROLES.items()
            if await repository.create_if_missing(name=name, permissions=permissions)
        ]

        await session.commit()

    logger.info(
        "Seeded default user roles.",
        extra={"created_roles": created, "default_roles": list(DEFAULT_ROLES)},
    )
