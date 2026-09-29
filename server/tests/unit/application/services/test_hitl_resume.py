"""
Unit tests for HitlResumeService.

The approval decision is committed before this service runs, so
resume_after_decision() must never raise, and a failure must be rolled
back, recorded on the AgentAction, and reported as FAILED. An approved
(or edited) call runs once with the approved parameters, and its result
is committed before the graph resumes, so retry() never runs it twice.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import MissingGreenlet

from agentic.tools.result import ToolResult
from application.services import hitl_resume
from application.services.hitl_resume import HitlResumeService
from core.enums import AgentActionStatusEnum, ApprovalDecisionEnum, HitlResumeStatusEnum
from core.exceptions.approval import ApprovalResumeNotAllowedError

APPROVAL_ID = "appr_" + "a" * 32
ACTION_ID = "actn_" + "b" * 32
DRAFT = {"to": "client@example.org", "subject": "Notice", "body": "Please sign."}
SENT = ToolResult(
    tool_name="email_send",
    success=True,
    content="Message sent.",
    evidence=(),
    execution_metadata={},
    error=None,
)


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
                "tool_name": "email_send",
                "parameters": dict(DRAFT),
                "status": AgentActionStatusEnum.PENDING_APPROVAL,
                "result": None,
                "executed_at": None,
                "to_dto": lambda: "action-dto",
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
    orchestrator.run_approved_tool = AsyncMock(return_value=SENT)
    orchestrator.resume = AsyncMock(return_value=SimpleNamespace(content="done", approval=None))
    return orchestrator


@pytest.fixture
def authorization() -> MagicMock:
    authorization = MagicMock()
    authorization.authorize_action = AsyncMock(
        return_value=SimpleNamespace(is_allowed=True, reason="Action is authorized.")
    )
    return authorization


@pytest.fixture
def service(
    session: MagicMock,
    repository: MagicMock,
    orchestrator: MagicMock,
    authorization: MagicMock,
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
        authorization_service=authorization,
        memory_extraction_scheduler=MagicMock(),
    )


@pytest.fixture(autouse=True)
def _plan():
    with patch.object(hitl_resume, "deserialize_plan", return_value=MagicMock()):
        yield


async def _resume(
    service: HitlResumeService,
    decision=ApprovalDecisionEnum.APPROVE,
    edited_payload: dict | None = None,
):
    return await service.resume_after_decision(
        approval_id=APPROVAL_ID,
        agent_action_id=ACTION_ID,
        decision_type=decision,
        edited_payload=edited_payload,
    )


@pytest.mark.asyncio
async def test_successful_resume_commits_and_reports_completed(
    service: HitlResumeService, session: MagicMock, loaded_action: _Action
) -> None:
    assert await _resume(service) is HitlResumeStatusEnum.COMPLETED

    # One commit storing the tool result before the graph resumes, one
    # for the finished turn.
    assert session.commit.await_count == 2
    session.rollback.assert_not_awaited()
    assert loaded_action.status is AgentActionStatusEnum.COMPLETED
    assert loaded_action.result["tool_result"] == SENT.to_dict()
    assert loaded_action.result["content"] == "done"


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
    # The tool-result commit, then the failure record's own commit.
    assert session.commit.await_count == 2


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
async def test_undecided_approval_leaves_the_session_alone(
    service: HitlResumeService,
    session: MagicMock,
    repository: MagicMock,
) -> None:
    assert await _resume(service, None) is HitlResumeStatusEnum.NOT_RESUMED

    repository.get.assert_not_awaited()
    session.commit.assert_not_awaited()
    session.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_approve_runs_the_proposed_draft_with_the_approval_as_token(
    service: HitlResumeService, orchestrator: MagicMock
) -> None:
    assert await _resume(service) is HitlResumeStatusEnum.COMPLETED

    orchestrator.run_approved_tool.assert_awaited_once_with(
        tool_name="email_send",
        parameters=DRAFT,
        approval_token=APPROVAL_ID,
    )
    assert orchestrator.resume.await_args.kwargs["tool_result"] == SENT


@pytest.mark.asyncio
async def test_edit_runs_the_edited_draft(
    service: HitlResumeService, orchestrator: MagicMock
) -> None:
    """
    EDIT used to leave the conversation paused for good (NOT_RESUMED).
    """

    result = await _resume(
        service,
        ApprovalDecisionEnum.EDIT,
        edited_payload={"body": "Please sign by Friday."},
    )

    assert result is HitlResumeStatusEnum.COMPLETED
    assert orchestrator.run_approved_tool.await_args.kwargs["parameters"] == {
        **DRAFT,
        "body": "Please sign by Friday.",
    }


@pytest.mark.asyncio
async def test_reject_runs_nothing(service: HitlResumeService, orchestrator: MagicMock) -> None:
    assert await _resume(service, ApprovalDecisionEnum.REJECT) is HitlResumeStatusEnum.COMPLETED

    orchestrator.run_approved_tool.assert_not_awaited()
    assert orchestrator.resume.await_args.kwargs["approved"] is False
    assert orchestrator.resume.await_args.kwargs["tool_result"] is None


@pytest.mark.asyncio
async def test_a_stored_tool_result_is_reused_not_run_again(
    service: HitlResumeService, orchestrator: MagicMock, loaded_action: _Action
) -> None:
    loaded_action.result = {"tool_result": SENT.to_dict(), "approval_id": APPROVAL_ID}
    loaded_action.status = AgentActionStatusEnum.FAILED

    assert await _resume(service) is HitlResumeStatusEnum.COMPLETED

    orchestrator.run_approved_tool.assert_not_awaited()
    assert orchestrator.resume.await_args.kwargs["tool_result"] == SENT


@pytest.mark.asyncio
async def test_failure_after_the_call_keeps_its_stored_result(
    service: HitlResumeService,
    orchestrator: MagicMock,
    refetched_action: SimpleNamespace,
) -> None:
    orchestrator.resume.side_effect = RuntimeError("resume failed")
    refetched_action.result = {"tool_result": SENT.to_dict(), "approval_id": APPROVAL_ID}

    assert await _resume(service) is HitlResumeStatusEnum.FAILED

    assert refetched_action.status is AgentActionStatusEnum.FAILED
    assert refetched_action.result["tool_result"] == SENT.to_dict()
    assert refetched_action.result["error"] == "RuntimeError"


def _approval(
    decision: ApprovalDecisionEnum | None = ApprovalDecisionEnum.APPROVE,
    edited_payload: dict | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        approval_id=APPROVAL_ID,
        agent_action_id=ACTION_ID,
        decision_type=decision,
        edited_payload=edited_payload,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        AgentActionStatusEnum.FAILED,
        AgentActionStatusEnum.PENDING_APPROVAL,
        AgentActionStatusEnum.EXECUTING,
    ],
)
async def test_retry_resumes_a_stuck_action(
    service: HitlResumeService,
    repository: MagicMock,
    loaded_action: _Action,
    orchestrator: MagicMock,
    status: AgentActionStatusEnum,
) -> None:
    loaded_action.status = status
    repository.get.side_effect = [loaded_action, loaded_action]

    result = await service.retry(approval=_approval(ApprovalDecisionEnum.EDIT, {"subject": "New"}))

    assert result is HitlResumeStatusEnum.COMPLETED
    assert orchestrator.run_approved_tool.await_args.kwargs["parameters"]["subject"] == "New"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [AgentActionStatusEnum.COMPLETED, AgentActionStatusEnum.REJECTED],
)
async def test_retry_refuses_a_finished_resume(
    service: HitlResumeService,
    repository: MagicMock,
    loaded_action: _Action,
    orchestrator: MagicMock,
    status: AgentActionStatusEnum,
) -> None:
    loaded_action.status = status
    repository.get.side_effect = [loaded_action]

    with pytest.raises(ApprovalResumeNotAllowedError):
        await service.retry(approval=_approval())

    orchestrator.run_approved_tool.assert_not_awaited()
    orchestrator.resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_refuses_an_undecided_approval(
    service: HitlResumeService, repository: MagicMock
) -> None:
    with pytest.raises(ApprovalResumeNotAllowedError):
        await service.retry(approval=_approval(None))

    repository.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_permission_is_rechecked_before_a_fresh_call(
    service: HitlResumeService, authorization: MagicMock
) -> None:
    assert await _resume(service) is HitlResumeStatusEnum.COMPLETED

    authorization.authorize_action.assert_awaited_once_with(
        user_id="user-1",
        action="action-dto",
    )


@pytest.mark.asyncio
async def test_a_user_no_longer_permitted_is_not_sent_for(
    service: HitlResumeService,
    orchestrator: MagicMock,
    authorization: MagicMock,
    loaded_action: _Action,
) -> None:
    authorization.authorize_action.return_value = SimpleNamespace(
        is_allowed=False, reason="Action is not authorized."
    )

    assert await _resume(service) is HitlResumeStatusEnum.COMPLETED

    orchestrator.run_approved_tool.assert_not_awaited()
    tool_result = orchestrator.resume.await_args.kwargs["tool_result"]
    assert tool_result.success is False
    assert tool_result.execution_metadata["error_type"] == "PermissionDenied"
    # Stored, so a retry doesn't decide it again.
    assert loaded_action.result["tool_result"]["success"] is False


@pytest.mark.asyncio
async def test_a_stored_result_is_not_rechecked(
    service: HitlResumeService, authorization: MagicMock, loaded_action: _Action
) -> None:
    loaded_action.result = {"tool_result": SENT.to_dict(), "approval_id": APPROVAL_ID}

    assert await _resume(service) is HitlResumeStatusEnum.COMPLETED

    authorization.authorize_action.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_rejection_is_not_authorized_at_all(
    service: HitlResumeService, authorization: MagicMock
) -> None:
    await _resume(service, ApprovalDecisionEnum.REJECT)

    authorization.authorize_action.assert_not_awaited()
