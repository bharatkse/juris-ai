"""
E2E: AGENT_DECISION compliance log entries carry real groundedness/
relevance scores, over real HTTP, real Postgres.

This is the verification vehicle for threading AnswerEvaluationSummary
from AgentContinuationService._gate_final up through AgentResponseDTO.
metadata to AIOrchestrator's compliance-log write (see
application/services/compliance_log.py, agentic/evaluation/answer.py).

What's real: FastAPI routing/middleware/DI, JWT auth, Postgres (users,
conversations, agent_policies, compliance_log), the real Postgres-
backed LangGraph checkpointer, the real execution graph,
AgentContinuationService._gate_final() itself (UNPATCHED, unlike
test_hitl_approval_flow.py -- that test's whole point is the HITL
control plane, this test's whole point is the evaluation gate, so it
stays real here), the real AnswerEvaluator (real local embeddings for
relevance -- no network; groundedness needs evidence to invoke the
real Groq-backed judge at all, so the no-tool-call scenario below
deliberately never reaches that network call, keeping this test fast
and offline-safe while still exercising 100% real evaluation code, not
a mock of it).

What's mocked, and why -- same non-deterministic LLM-reasoning
boundary test_hitl_approval_flow.py mocks, nothing more:
  - LLMPlanGenerator.generate() / BaseAgent._reason(): scripted to
    produce a FINAL decision directly, no tool call -- keeps this test
    deterministic and fast without touching the one thing it verifies
    (_gate_final's real evaluation + the compliance write it feeds).

Requires the real Postgres/Redis docker compose services running
(`make docker-up`). Run via `make test-e2e`.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from adapters.persistence.sqlalchemy.repositories.compliance_log import (
    ComplianceLogRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.agents.base import BaseAgent
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.planning.llm_planner import LLMPlanGenerator
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ComplianceEventTypeEnum, ExecutionModeEnum, IntentEnum

CHAT_MESSAGE = "What does section 2(1)(ta) of the IT Act 2000 define?"

# Deliberately echoes the question closely -- this test's FINAL answer
# never goes through a tool call (no retrieval evidence), so
# groundedness is genuinely "not applicable" (real code path, see
# AnswerEvaluator._evaluate_groundedness), but relevance IS computed
# for real via local embeddings and must clear the real min_relevance
# (0.60) threshold on the first attempt for this test to stay fast.
FINAL_ANSWER = (
    "Section 2(1)(ta) of the IT Act 2000 defines 'electronic signature' "
    "as authentication of an electronic record by a subscriber using an "
    "electronic technique."
)


@pytest.mark.asyncio
async def test_final_decision_records_real_evaluation_scores_in_compliance_log(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    final_decision = AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        reason="Answering directly from known statute text.",
        final_response=FINAL_ANSWER,
    )

    async def fake_reason(self, *, request, context=()):
        return final_decision

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

    request_start = datetime.now(UTC)

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))

        # _gate_final is deliberately NOT patched -- see module docstring.
        chat_response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
            headers=registered_user["headers"],
        )

    assert chat_response.status_code == 200, chat_response.text
    body = chat_response.json()["data"]
    assert body["response"]["content"] == FINAL_ANSWER

    # ------------------------------------------------------------
    # Verify: the real AGENT_DECISION compliance log row carries the
    # real evaluation's scores, not None.
    # ------------------------------------------------------------

    async with session_factory() as session:
        repository = ComplianceLogRepository(session=session)
        rows = await repository.list_for_user(
            user_id=registered_user["user_id"],
            start=request_start - timedelta(seconds=5),
            end=datetime.now(UTC) + timedelta(seconds=5),
            event_type=ComplianceEventTypeEnum.AGENT_DECISION,
        )

    assert len(rows) == 1, f"expected exactly one AGENT_DECISION row, got {len(rows)}"
    payload = rows[0].payload

    # relevance is genuinely computed (real embeddings, on-topic
    # answer) and must be a real, non-null float clearing the real
    # min_relevance threshold.
    assert payload["relevance"] is not None
    assert isinstance(payload["relevance"], float)
    assert payload["relevance"] >= 0.60

    # groundedness is real too -- 0.0 because no evidence was ever
    # gathered (no tool call in this scenario), which is the correct,
    # honest value for "not applicable", not a threading failure.
    assert payload["groundedness"] == 0.0

    assert payload["decision_type"] == "final"
