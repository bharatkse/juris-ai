"""
E2E: an approval decision is durable on its own, independent of what
happens after it.

Each test drives a real chat turn to a real pending approval, decides
it over real HTTP, then reads the approval back from Postgres in a
fresh session (not the request's session or objects), so what's
asserted is what was actually committed.

Mocked, for the same reasons as test_hitl_approval_flow.py: the two
LLM calls, the answer-quality gate, and the RBAC stub. The resume
failure test additionally makes AIOrchestrator.resume() raise, standing
in for any failure while acting on an approved decision.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import update

from adapters.persistence.sqlalchemy.models.approval import Approval
from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from adapters.persistence.sqlalchemy.repositories.agent_policy import (
    AgentPolicyRepository,
)
from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.agents.base import BaseAgent
from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, AgentToolCall
from agentic.evaluation.answer import AnswerEvaluationSummary
from agentic.orchestration.orchestrator import AIOrchestrator
from agentic.planning.llm_planner import LLMPlanGenerator
from application.authorization.rbac.resolver import RBACService
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import (
    AgentActionStatusEnum,
    AgentTypeEnum,
    ApprovalStatusEnum,
    ExecutionModeEnum,
    HitlResumeStatusEnum,
    IntentEnum,
)

CHAT_MESSAGE = "Check my email for updates on case 84021 and let me know."


@pytest_asyncio.fixture
async def legal_agent_email_policy() -> AsyncIterator[None]:
    """
    Temporarily grant the "legal" agent the "email" tool (see
    test_hitl_approval_flow.py's fixture of the same name).
    """

    async with session_factory() as session:
        repository = AgentPolicyRepository(session=session)
        original = await repository.get_by_agent_id(agent_id="legal")
        original_tools = (
            list(original.allowed_tools) if original else ["retriever", "case_law_search"]
        )
        await repository.upsert(agent_id="legal", allowed_tools=[*original_tools, "email"])
        await session.commit()

    try:
        yield
    finally:
        async with session_factory() as session:
            repository = AgentPolicyRepository(session=session)
            await repository.upsert(agent_id="legal", allowed_tools=original_tools)
            await session.commit()


@pytest_asyncio.fixture
async def llm_boundaries() -> AsyncIterator[None]:
    """
    Script the planner and agent so the chat turn pauses on a gated
    "email" TOOL_CALL.
    """

    tool_call = AgentDecision(
        decision_type=AgentDecisionType.TOOL_CALL,
        reason="Need to check email.",
        tool_call=AgentToolCall(tool_name="email", parameters={"query": "case 84021"}),
    )

    async def fake_reason(self, *, request, context=()):
        return tool_call

    plan = ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepDTO(
                id="step-1",
                agent=AgentTypeEnum.LEGAL,
                instruction=CHAT_MESSAGE,
                depends_on=(),
                stage=1,
                arguments={},
            ),
        ),
        metadata={},
    )

    async def fake_plan_generate(self, *, request):
        return plan

    async def fake_gate_final(self, *, handle, result):
        return None, AnswerEvaluationSummary(groundedness=0.95, relevance=0.90)

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))
        patches.enter_context(
            patch.object(AgentContinuationService, "_gate_final", fake_gate_final)
        )
        patches.enter_context(patch.object(RBACService, "check_action", lambda self, request: True))
        yield


@pytest_asyncio.fixture
async def pending_approval(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    legal_agent_email_policy: None,
    llm_boundaries: None,
) -> dict:
    """
    A real WAITING approval owned by registered_user.
    """

    response = await e2e_client.post(
        "/api/v1/chat",
        data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
        headers=registered_user["headers"],
    )
    assert response.status_code == 200, response.text
    approval = response.json()["data"]["assistant_event"]["event_metadata"]["approval"]
    assert approval["status"] == ApprovalStatusEnum.WAITING.value
    return approval


async def _fetch_approval(approval_id: str) -> Approval:
    async with session_factory() as session:
        approval = await ApprovalRepository(session=session).get(approval_id)
    assert approval is not None
    return approval


@pytest.mark.asyncio
async def test_edit_is_committed(
    e2e_client: AsyncClient, registered_user: dict, pending_approval: dict
) -> None:
    approval_id = pending_approval["approval_id"]

    response = await e2e_client.post(
        f"/api/v1/approvals/{approval_id}",
        json={"decision": "edit", "edited_payload": {"query": "case 84022"}},
        headers=registered_user["headers"],
    )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == ApprovalStatusEnum.EDITED.value
    assert body["resume_status"] == HitlResumeStatusEnum.NOT_RESUMED.value

    stored = await _fetch_approval(approval_id)
    assert stored.status == ApprovalStatusEnum.EDITED
    assert stored.edited_payload == {"query": "case 84022"}
    assert stored.decided_at is not None


@pytest.mark.asyncio
async def test_approve_survives_resume_failure(
    e2e_client: AsyncClient, registered_user: dict, pending_approval: dict
) -> None:
    approval_id = pending_approval["approval_id"]

    async def failing_resume(self, **kwargs):
        raise RuntimeError("resume failed")

    with patch.object(AIOrchestrator, "resume", failing_resume):
        response = await e2e_client.post(
            f"/api/v1/approvals/{approval_id}",
            json={"decision": "approve"},
            headers=registered_user["headers"],
        )

    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["status"] == ApprovalStatusEnum.APPROVED.value
    assert body["resume_status"] == HitlResumeStatusEnum.FAILED.value

    stored = await _fetch_approval(approval_id)
    assert stored.status == ApprovalStatusEnum.APPROVED
    assert stored.approved_by == registered_user["user_id"]

    # The failure itself is recorded on the action, not only logged.
    async with session_factory() as session:
        action = await AgentActionRepository(session=session).get(stored.agent_action_id)
    assert action is not None
    assert action.status == AgentActionStatusEnum.FAILED
    assert action.result is not None
    assert action.result.get("error") == "RuntimeError"

    # Deciding again is refused as already decided, not re-applied.
    again = await e2e_client.post(
        f"/api/v1/approvals/{approval_id}",
        json={"decision": "reject"},
        headers=registered_user["headers"],
    )
    assert again.status_code == 409, again.text


@pytest.mark.asyncio
async def test_expired_status_is_committed(
    e2e_client: AsyncClient, registered_user: dict, pending_approval: dict
) -> None:
    approval_id = pending_approval["approval_id"]

    async with session_factory() as session:
        await session.execute(
            update(Approval)
            .where(Approval.id == approval_id)
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        await session.commit()

    response = await e2e_client.post(
        f"/api/v1/approvals/{approval_id}",
        json={"decision": "approve"},
        headers=registered_user["headers"],
    )

    assert response.status_code == 410, response.text

    stored = await _fetch_approval(approval_id)
    assert stored.status == ApprovalStatusEnum.EXPIRED
