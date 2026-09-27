"""
HTTP status codes for approval-decision errors, asserted through the real
app, router and global exception handler (not by calling the route
function directly), so the status and error code a client actually
receives are what's tested.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from adapters.persistence.sqlalchemy.models.approval import Approval
from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from api.dependencies.approval import get_approval_lifecycle_service
from api.dependencies.auth import get_current_user
from api.dependencies.hitl_resume import get_hitl_resume_service
from application.services.approval_lifecycle import ApprovalLifecycleService
from core.enums import ApprovalStatusEnum
from main import app

OWNER_ID = "user_" + "a" * 32
OTHER_ID = "user_" + "b" * 32
APPROVAL_ID = "appr_" + "c" * 32
URL = f"/api/v1/approvals/{APPROVAL_ID}"


def _entity(*, status: ApprovalStatusEnum, expired: bool = False) -> MagicMock:
    entity = MagicMock(spec=Approval)
    entity.id = APPROVAL_ID
    entity.agent_action_id = "actn_" + "d" * 32
    entity.requested_by = OWNER_ID
    entity.status = status
    entity.is_expired = expired
    return entity


@pytest.fixture
def repository() -> MagicMock:
    repository = MagicMock(spec=ApprovalRepository)
    repository.get = AsyncMock()
    repository.save = AsyncMock(side_effect=lambda *, entity: entity)
    return repository


@pytest.fixture
async def client(repository: MagicMock) -> AsyncIterator[tuple[AsyncClient, dict]]:
    """
    Real app; only the caller identity and the service's dependencies are
    replaced. ``state["user_id"]`` selects who is calling.
    """

    state = {"user_id": OWNER_ID}
    compliance_log = MagicMock()
    compliance_log.record_hitl_approval_decision = AsyncMock()
    resume = MagicMock()
    resume.resume_after_decision = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=state["user_id"], is_active=True
    )
    session = MagicMock()
    session.commit = AsyncMock()
    app.dependency_overrides[get_approval_lifecycle_service] = lambda: ApprovalLifecycleService(
        session=session,
        repository=repository,
        compliance_log_service=compliance_log,
    )
    app.dependency_overrides[get_hitl_resume_service] = lambda: resume
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c, state
    finally:
        app.dependency_overrides.clear()


def _error(response) -> tuple[int, str]:
    body = response.json()
    assert body["success"] is False
    return response.status_code, body["error"]["code"]


@pytest.mark.asyncio
async def test_unknown_approval_returns_404(client, repository: MagicMock) -> None:
    c, _ = client
    repository.get.return_value = None

    response = await c.post(URL, json={"decision": "approve"})

    assert _error(response) == (404, "APPROVAL_NOT_FOUND")


@pytest.mark.asyncio
async def test_expired_approval_returns_410(client, repository: MagicMock) -> None:
    c, _ = client
    repository.get.return_value = _entity(status=ApprovalStatusEnum.WAITING, expired=True)

    response = await c.post(URL, json={"decision": "approve"})

    assert _error(response) == (410, "APPROVAL_EXPIRED")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [ApprovalStatusEnum.APPROVED, ApprovalStatusEnum.REJECTED, ApprovalStatusEnum.EDITED],
)
@pytest.mark.parametrize("decision", ["approve", "reject", "edit"])
async def test_already_decided_approval_returns_409(
    client, repository: MagicMock, status: ApprovalStatusEnum, decision: str
) -> None:
    c, _ = client
    repository.get.return_value = _entity(status=status)

    response = await c.post(URL, json={"decision": decision})

    assert _error(response) == (409, "APPROVAL_ALREADY_DECIDED")


@pytest.mark.asyncio
async def test_non_owner_still_gets_403_before_state_checks(client, repository: MagicMock) -> None:
    """
    Ownership is checked first: a non-owner gets 403 even for an expired
    or already-decided approval, so the status code reveals nothing about
    another user's approval.
    """

    c, state = client
    state["user_id"] = OTHER_ID

    for entity in (
        _entity(status=ApprovalStatusEnum.WAITING, expired=True),
        _entity(status=ApprovalStatusEnum.APPROVED),
    ):
        repository.get.return_value = entity
        response = await c.post(URL, json={"decision": "approve"})
        assert _error(response) == (403, "FORBIDDEN")


@pytest.mark.asyncio
async def test_none_of_the_decision_errors_is_a_500(client, repository: MagicMock) -> None:
    c, _ = client
    cases = [
        None,
        _entity(status=ApprovalStatusEnum.WAITING, expired=True),
        _entity(status=ApprovalStatusEnum.APPROVED),
    ]
    for entity in cases:
        repository.get.return_value = entity
        response = await c.post(URL, json={"decision": "approve"})
        assert response.status_code != 500
        assert response.json()["error"]["code"] != "AI_ERROR"
