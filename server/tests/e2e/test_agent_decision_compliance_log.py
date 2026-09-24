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
relevance), and the agent's real evidence seeding (A1) through the
real RetrieverTool and tool policy.

What's mocked, and why:
  - LLMPlanGenerator.generate() / BaseAgent._reason(): scripted to
    produce a FINAL decision directly -- the same non-deterministic
    LLM-reasoning boundary test_hitl_approval_flow.py mocks.
  - The groundedness judge (an LLM call): stubbed by conftest's
    hermetic_llm fixture.
  - HybridRetriever.retrieve (the Postgres/pgvector corpus, empty in
    dev and CI): the statute_evidence fixture returns one statute chunk.
    Without it, the answer is replaced with the "no sources" answer
    (see the second test).

Requires the real Postgres/Redis docker compose services running
(`./setup.sh --install --dependency postgres
--dependency redis`). Run via `make test-e2e`.
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
from application.services.compliance_log import _hash
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import AgentTypeEnum, ComplianceEventTypeEnum, ExecutionModeEnum, IntentEnum

CHAT_MESSAGE = "What does section 2(1)(ta) of the IT Act 2000 define?"

# Deliberately echoes the question closely -- relevance is computed for
# real via local embeddings and must clear the real min_relevance (0.60)
# threshold on the first attempt for this test to stay fast.
FINAL_ANSWER = (
    "Section 2(1)(ta) of the IT Act 2000 defines 'electronic signature' "
    "as authentication of an electronic record by a subscriber using an "
    "electronic technique."
)


@pytest.mark.asyncio
def _plan() -> ExecutionPlanDTO:
    return ExecutionPlanDTO(
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


async def _agent_decision_payloads(*, user_id: str, since: datetime) -> list[dict]:
    async with session_factory() as session:
        rows = await ComplianceLogRepository(session=session).list_for_user(
            user_id=user_id,
            start=since - timedelta(seconds=5),
            end=datetime.now(UTC) + timedelta(seconds=5),
            event_type=ComplianceEventTypeEnum.AGENT_DECISION,
        )

    return [row.payload for row in rows]


@pytest.mark.asyncio
async def test_final_decision_records_real_evaluation_scores_in_compliance_log(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    statute_evidence: list[str],
    hermetic_llm,
) -> None:
    final_decision = AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        reason="Answering directly from known statute text.",
        final_response=FINAL_ANSWER,
    )

    async def fake_reason(self, *, request, context=()):
        return final_decision

    async def fake_plan_generate(self, *, request):
        return _plan()

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

    # A1: the agent's evidence was seeded by a real retriever call for
    # the user's question, and the answer cites it.
    assert statute_evidence == [CHAT_MESSAGE]
    assert body["response"]["citations"], body["response"]
    assert hermetic_llm.groundedness_calls == 1

    # ------------------------------------------------------------
    # Verify: the real AGENT_DECISION compliance log row carries the
    # real evaluation's scores, not None.
    # ------------------------------------------------------------

    payloads = await _agent_decision_payloads(
        user_id=registered_user["user_id"],
        since=request_start,
    )

    assert len(payloads) == 1, f"expected exactly one AGENT_DECISION row, got {len(payloads)}"
    payload = payloads[0]

    # relevance is genuinely computed (real embeddings, on-topic
    # answer) and must be a real, non-null float clearing the real
    # min_relevance threshold.
    assert payload["relevance"] is not None
    assert isinstance(payload["relevance"], float)
    assert payload["relevance"] >= 0.60

    # groundedness was judged against the seeded evidence (the judge
    # itself is stubbed to 1.0 by hermetic_llm).
    assert payload["groundedness"] == 1.0
    assert payload["answer_verified"] is True

    assert payload["decision_type"] == "final"


@pytest.mark.asyncio
async def test_answer_without_sources_is_replaced_and_logged_unverified(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    hermetic_llm,
) -> None:
    """
    A1 over real HTTP and Postgres: the corpus is empty, so seeding and
    the gate's one corrective retrieval (both real, against the real,
    empty knowledge tables) find nothing. The model's answer from its own
    knowledge is replaced with the fixed "no sources" answer and logged
    as unverified -- the model is not asked again.
    """

    from agentic.agents.runtime.continuation import NO_SOURCES_ANSWER_MESSAGE

    reason_calls = 0

    async def fake_reason(self, *, request, context=()):
        nonlocal reason_calls
        reason_calls += 1
        return AgentDecision(
            decision_type=AgentDecisionType.FINAL,
            reason="Answering from memory.",
            final_response=FINAL_ANSWER,
        )

    async def fake_plan_generate(self, *, request):
        return _plan()

    request_start = datetime.now(UTC)

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))

        chat_response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
            headers=registered_user["headers"],
        )

    assert chat_response.status_code == 200, chat_response.text
    response = chat_response.json()["data"]["response"]
    assert response["content"] == NO_SOURCES_ANSWER_MESSAGE
    assert FINAL_ANSWER not in response["content"]
    assert response["citations"] == []

    assert reason_calls == 1
    assert hermetic_llm.groundedness_calls == 0

    payloads = await _agent_decision_payloads(
        user_id=registered_user["user_id"],
        since=request_start,
    )
    assert len(payloads) == 1
    assert payloads[0]["answer_verified"] is False


@pytest.mark.asyncio
async def test_unverified_answer_is_replaced_and_logged_unverified(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
    statute_evidence: list[str],
    hermetic_llm,
) -> None:
    """
    S5 over real HTTP and Postgres: evidence exists, but the answer never
    passes the groundedness check. The gate retries with corrective
    retrievals that keep returning the same chunk until the runtime's
    no-progress budget ends the execution, and the answer is replaced
    with the fixed "couldn't verify" message -- returned to the client
    and recorded in the AGENT_DECISION compliance row with
    answer_verified=False and the rejected answer's scores. (Before the
    fix, a budget closing the handle mid-retry made this request fail
    with HTTP 500.)
    """

    from agentic.agents.runtime.continuation import UNVERIFIED_ANSWER_MESSAGE

    hermetic_llm.groundedness = 0.0

    async def fake_reason(self, *, request, context=()):
        return AgentDecision(
            decision_type=AgentDecisionType.FINAL,
            reason="Answering without using the evidence.",
            final_response=FINAL_ANSWER,
        )

    async def fake_plan_generate(self, *, request):
        return _plan()

    request_start = datetime.now(UTC)

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))

        chat_response = await e2e_client.post(
            "/api/v1/chat",
            data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
            headers=registered_user["headers"],
        )

    assert chat_response.status_code == 200, chat_response.text
    content = chat_response.json()["data"]["response"]["content"]
    assert content == UNVERIFIED_ANSWER_MESSAGE
    assert FINAL_ANSWER not in content

    # Seeded, then at least one corrective retrieval.
    assert len(statute_evidence) >= 2
    assert hermetic_llm.groundedness_calls >= 1

    payloads = await _agent_decision_payloads(
        user_id=registered_user["user_id"],
        since=request_start,
    )
    assert len(payloads) == 1
    assert payloads[0]["answer_verified"] is False
    assert payloads[0]["groundedness"] == 0.0
    assert payloads[0]["relevance"] >= 0.60

    async with session_factory() as session:
        response_rows = await ComplianceLogRepository(session=session).list_for_user(
            user_id=registered_user["user_id"],
            start=request_start - timedelta(seconds=5),
            end=datetime.now(UTC) + timedelta(seconds=5),
            event_type=ComplianceEventTypeEnum.RESPONSE_RETURNED,
        )

    assert len(response_rows) == 1
    assert response_rows[0].payload["content_hash"] == _hash(UNVERIFIED_ANSWER_MESSAGE)
