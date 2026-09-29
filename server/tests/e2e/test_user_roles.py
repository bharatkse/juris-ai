"""
E2E: user roles and their permissions come from the database.

users.role names a role; the role's rows in role_permissions say what it
grants. Seeded at startup (member, reader) but owned by the data: a
change made in the database takes effect on the next request, with no
code change or restart, and a restart doesn't undo it.

Roles are read and written through RoleRepository against real Postgres,
the same way the agent-policy e2e tests use AgentPolicyRepository. Tests
that need a changed role use a temporary one, or restore what they touch.

RBAC is only the coarse gate: a member may ask for a send, but the send
itself still needs the user's approval (test_hitl_approval_flow.py).

Requires the real Postgres/Redis services with migrations applied. Run via
`make test-e2e`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import delete, select, update

from adapters.persistence.sqlalchemy.models.role import RoleModel
from adapters.persistence.sqlalchemy.models.user import User
from adapters.persistence.sqlalchemy.repositories.role import RoleRepository
from adapters.persistence.sqlalchemy.session import session_factory
from application.authorization.service import AuthorizationService
from core.enums import ActionTypeEnum
from core.exceptions.authorization import AuthorizationError
from tests.builders.core.dto import build_agent_action_response_dto
from wiring.factories.authorization import create_authorization
from wiring.factories.roles import seed_default_roles

# Classified SEND by the capability classifier -- an ordinary legal
# question the former "user-1" stub refused for every real user.
SEND_MESSAGE = "Is it legal to forward this email to the client?"
RESEARCH = ["analyze", "generate", "read"]


@pytest_asyncio.fixture
async def authorization(e2e_client: AsyncClient) -> AuthorizationService:
    # e2e_client first: it resets the DB engine for this test's event loop.
    return create_authorization()


async def _set_role(user_id: str, role: str) -> None:
    async with session_factory() as session:
        await session.execute(update(User).where(User.id == user_id).values(role=role))
        await session.commit()


async def _role_permissions(name: str) -> list[str] | None:
    async with session_factory() as session:
        role = await RoleRepository(session=session).get_by_name(name=name)
    return role.permission_names if role else None


@pytest_asyncio.fixture
async def temporary_role() -> AsyncIterator[str]:
    """A role name unique to this test, deleted afterwards."""

    name = f"e2e-{uuid.uuid4().hex[:12]}"
    yield name
    async with session_factory() as session:
        await session.execute(delete(RoleModel).where(RoleModel.name == name))
        await session.commit()


async def test_default_roles_are_seeded(e2e_client: AsyncClient) -> None:
    assert await _role_permissions("member") == [*RESEARCH, "send"]
    assert await _role_permissions("reader") == RESEARCH


async def test_a_new_user_is_a_member(e2e_client: AsyncClient, registered_user: dict) -> None:
    async with session_factory() as session:
        role = await session.scalar(select(User.role).where(User.id == registered_user["user_id"]))

    assert role == "member"


async def test_a_member_may_ask_to_send(
    authorization: AuthorizationService, registered_user: dict
) -> None:
    analysis = await authorization.authorize_request(
        user_id=registered_user["user_id"],
        message=SEND_MESSAGE,
    )

    assert ActionTypeEnum.SEND in analysis.action_types


async def test_a_reader_is_refused_a_send_request_over_http(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    """
    Refused at request authorization, before planning, so no LLM call is
    made (the e2e hermetic_llm fixture would fail one).
    """

    await _set_role(registered_user["user_id"], "reader")

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": SEND_MESSAGE},
        headers=registered_user["headers"],
    )

    assert response.status_code == 400, response.text
    assert "not authorized" in response.json()["error"]["message"]


async def test_a_readers_gated_send_action_is_denied(
    authorization: AuthorizationService, registered_user: dict
) -> None:
    await _set_role(registered_user["user_id"], "reader")
    action = build_agent_action_response_dto(
        agent_id="legal",
        action_type=ActionTypeEnum.SEND,
        tool_name="email_send",
    )

    result = await authorization.authorize_action(
        user_id=registered_user["user_id"],
        action=action,
    )

    assert result.is_allowed is False


async def test_a_role_change_in_the_database_applies_on_the_next_request(
    authorization: AuthorizationService,
    registered_user: dict,
    temporary_role: str,
) -> None:
    """
    An admin grants or revokes a permission with a data change; the same
    running authorization service sees it immediately.
    """

    user_id = registered_user["user_id"]

    async with session_factory() as session:
        await RoleRepository(session=session).upsert(name=temporary_role, permissions=RESEARCH)
        await session.commit()
    await _set_role(user_id, temporary_role)

    with pytest.raises(AuthorizationError):
        await authorization.authorize_request(user_id=user_id, message=SEND_MESSAGE)

    async with session_factory() as session:
        await RoleRepository(session=session).upsert(
            name=temporary_role, permissions=[*RESEARCH, "send"]
        )
        await session.commit()

    analysis = await authorization.authorize_request(user_id=user_id, message=SEND_MESSAGE)
    assert ActionTypeEnum.SEND in analysis.action_types


@pytest.mark.parametrize("state", ["disabled", "missing"])
async def test_a_disabled_or_missing_role_grants_nothing(
    authorization: AuthorizationService,
    registered_user: dict,
    temporary_role: str,
    state: str,
) -> None:
    if state == "disabled":
        async with session_factory() as session:
            await RoleRepository(session=session).upsert(
                name=temporary_role, permissions=[*RESEARCH, "send"], enabled=False
            )
            await session.commit()
    await _set_role(registered_user["user_id"], temporary_role)

    with pytest.raises(AuthorizationError):
        await authorization.authorize_request(
            user_id=registered_user["user_id"],
            message=SEND_MESSAGE,
        )


async def test_startup_seeding_never_overwrites_a_changed_role(e2e_client: AsyncClient) -> None:
    original = await _role_permissions("reader")
    assert original is not None

    try:
        async with session_factory() as session:
            await RoleRepository(session=session).upsert(name="reader", permissions=["read"])
            await session.commit()

        await seed_default_roles()

        assert await _role_permissions("reader") == ["read"]
    finally:
        async with session_factory() as session:
            await RoleRepository(session=session).upsert(name="reader", permissions=original)
            await session.commit()
