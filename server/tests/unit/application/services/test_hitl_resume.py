"""
Unit tests for HitlResumeService's failure handling.

The approval decision is committed before this service runs, so
resume_after_decision() must never raise, and a failure must be rolled
back, recorded on the AgentAction, and reported as FAILED.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import MissingGreenlet

from application.services import hitl_resume
from application.services.hitl_resume import HitlResumeService
from core.enums import AgentActionStatusEnum, ApprovalDecisionEnum, HitlResumeStatusEnum

APPROVAL_ID = "appr_" + "a" * 32
ACTION_ID = "actn_" + "b" * 32


class _Action:
    """
    Stands in for an AgentAction loaded on the request's session.

    After the session rolls back, reading any attribute raises
    MissingGreenlet, which is what an expired ORM instance does when
    it lazy-loads outside the async context.
    """

    def __init__(self, state: dict) -> None:
        object.__setattr__(self, "_state", state)
        object.__setattr__(
            self,
            "_values",
            {
                "id": ACTION_ID,
                "plan_snapshot": {"steps": []},
                "conversation_event_id": "evt-1",
                "thread_id": "thread-1",
                "user_id": "user-1",
                "tool_name": "email",
                "parameters": {"query": "x"},
                "status": AgentActionStatusEnum.PENDING_APPROVAL,
                "result": None,
                "executed_at": None,
            },
        )

    def __getattr__(self, name: str):
        if self._state["rolled_back"]:
            raise MissingGreenlet("greenlet_spawn has not been called")
        return self._values[name]

    def __setattr__(self, name: str, value) -> None:
        self._values[name] = value


@pytest.fixture
def state() -> dict:
    return {"rolled_back": False}


@pytest.fixture
def session(state: dict) -> MagicMock:
    session = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    async def rollback() -> None:
        state["rolled_back"] = True

    session.rollback = AsyncMock(side_effect=rollback)
    return session


@pytest.fixture
def loaded_action(state: dict) -> _Action:
    return _Action(state)


@pytest.fixture
def refetched_action() -> SimpleNamespace:
    return SimpleNamespace(id=ACTION_ID, status=AgentActionStatusEnum.EXECUTING, result=None)


@pytest.fixture
def repository(loaded_action: _Action, refetched_action: SimpleNamespace) -> MagicMock:
    repository = MagicMock()
    repository.get = AsyncMock(side_effect=[loaded_action, refetched_action])
    return repository


@pytest.fixture
def orchestrator() -> MagicMock:
    orchestrator = MagicMock()
    orchestrator.resume = AsyncMock(return_value=SimpleNamespace(content="done"))
    return orchestrator


@pytest.fixture
def service(
    session: MagicMock, repository: MagicMock, orchestrator: MagicMock
) -> HitlResumeService:
    events = MagicMock()
    events.get_by_id = AsyncMock(return_value=SimpleNamespace(id="evt-1", conversation_id="conv-1"))
    events.create = AsyncMock()
    return HitlResumeService(
        session=session,
        agent_action_repository=repository,
        conversation_event_service=events,
        orchestrator=orchestrator,
        action_workflow_service=MagicMock(),
        memory_extraction_scheduler=MagicMock(),
    )


@pytest.fixture(autouse=True)
def _plan():
    with patch.object(hitl_resume, "deserialize_plan", return_value=MagicMock()):
        yield


async def _resume(service: HitlResumeService, decision=ApprovalDecisionEnum.APPROVE):
    return await service.resume_after_decision(
        approval_id=APPROVAL_ID,
        agent_action_id=ACTION_ID,
        decision_type=decision,
    )


@pytest.mark.asyncio
async def test_successful_resume_commits_and_reports_completed(
    service: HitlResumeService, session: MagicMock, loaded_action: _Action
) -> None:
    assert await _resume(service) is HitlResumeStatusEnum.COMPLETED

    session.commit.assert_awaited_once()
    session.rollback.assert_not_awaited()
    assert loaded_action.status is AgentActionStatusEnum.COMPLETED


@pytest.mark.asyncio
async def test_resume_failure_does_not_touch_expired_state_or_raise(
    service: HitlResumeService,
    orchestrator: MagicMock,
    session: MagicMock,
    refetched_action: SimpleNamespace,
) -> None:
    """
    The rollback expires the loaded action; the error path must not read
    it (MissingGreenlet) and must not raise, since the decision is
    already committed.
    """

    orchestrator.resume.side_effect = RuntimeError("resume failed")

    result = await _resume(service)

    assert result is HitlResumeStatusEnum.FAILED
    session.rollback.assert_awaited_once()
    # The failure is recorded on a re-fetched action, in its own commit.
    assert refetched_action.status is AgentActionStatusEnum.FAILED
    assert refetched_action.result == {"error": "RuntimeError", "approval_id": APPROVAL_ID}
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_failure_to_record_the_failure_is_swallowed(
    service: HitlResumeService, orchestrator: MagicMock, repository: MagicMock
) -> None:
    orchestrator.resume.side_effect = RuntimeError("resume failed")
    repository.get.side_effect = [repository.get.side_effect.__next__(), RuntimeError("db down")]

    assert await _resume(service) is HitlResumeStatusEnum.FAILED


@pytest.mark.asyncio
async def test_failure_loading_the_action_is_reported_not_raised(
    service: HitlResumeService, repository: MagicMock
) -> None:
    repository.get.side_effect = RuntimeError("db down")

    assert await _resume(service) is HitlResumeStatusEnum.FAILED


@pytest.mark.asyncio
async def test_missing_action_is_reported_as_failed(
    service: HitlResumeService, repository: MagicMock, session: MagicMock
) -> None:
    repository.get.side_effect = None
    repository.get.return_value = None

    assert await _resume(service) is HitlResumeStatusEnum.FAILED
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("decision", [ApprovalDecisionEnum.EDIT, None])
async def test_non_resumable_decisions_leave_the_session_alone(
    service: HitlResumeService,
    session: MagicMock,
    repository: MagicMock,
    decision: ApprovalDecisionEnum | None,
) -> None:
    assert await _resume(service, decision) is HitlResumeStatusEnum.NOT_RESUMED

    repository.get.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()
