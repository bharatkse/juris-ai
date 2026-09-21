"""
E2E: /chat/stream end-to-end, over real HTTP, real Postgres, real
LangGraph checkpointer, real guardrails -- the final verification pass
for the whole 5-phase /chat/stream feature.

What's real: FastAPI routing/middleware/DI, JWT auth, Postgres (users,
conversations, conversation_events, compliance_log), the real Postgres
-backed LangGraph checkpointer, the real execution graph including
AgentExecutionNode's streaming branch (get_stream_writer(),
ExecutionSession.execute_streaming()'s "custom"+"values" stream
modes), AIOrchestrator.stream()'s full-buffer-per-attempt guardrail
sequencing, and the real OutputGuardrailService (real, local, no-
network Presidio PII detection -- see agentic/guardrails/pii.py).

What's mocked, and why -- same external/non-deterministic/costly LLM
boundary every other e2e test in this suite mocks, nothing more:
  - LLMPlanGenerator.generate() / BaseAgent._reason(): scripted to
    produce a FINAL decision directly, no tool call (same pattern as
    test_agent_decision_compliance_log.py).
  - BaseAgent.stream_final_answer(): NEW for this test -- the Phase 2
    freeform-completion call streaming actually depends on. Scripted
    to yield a few real AgentStreamChunkDTO chunks instead of making a
    real LLM streaming call.

One real architectural note, not a bug: _reason()'s decision.final_response
(TEXT_A, what gets aggregated/guardrail-reviewed/persisted) and
stream_final_answer()'s chunks (TEXT_B, what gets streamed to the
client) come from two genuinely separate LLM calls in production --
confirmed and accepted back when Phase 2 was scoped (a structured
decision can't be meaningfully token-streamed). The two fakes below
are scripted to agree so this test's assertions are meaningful; a real
LLM's two calls are not guaranteed to produce byte-identical text
either, which is exactly why AIOrchestrator.stream() guardrail-reviews
the buffered STREAMED chunks' own aggregated content, not a separately
-generated string -- see orchestrator.py's stream() docstring.

Requires the real Postgres/Redis docker compose services running
(`./setup.sh --install --dependency postgres
--dependency redis`). Run via `make test-e2e`.
"""

from __future__ import annotations

import json
from contextlib import AsyncExitStack
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from adapters.persistence.sqlalchemy.repositories.compliance_log import (
    ComplianceLogRepository,
)
from adapters.persistence.sqlalchemy.repositories.conversation_event import (
    ConversationEventRepository,
)
from adapters.persistence.sqlalchemy.repositories.usage_record import (
    UsageRecordRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.agents.base import BaseAgent
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.planning.llm_planner import LLMPlanGenerator
from application.services.compliance_log import _hash
from core.dto.agent import AgentStreamChunkDTO
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import (
    AgentTypeEnum,
    ComplianceEventTypeEnum,
    ExecutionModeEnum,
    IntentEnum,
    MessageRoleEnum,
)

CHAT_MESSAGE = "What does section 2(1)(ta) of the IT Act 2000 define?"

FINAL_ANSWER = (
    "Section 2(1)(ta) of the IT Act 2000 defines 'electronic signature' "
    "as authentication of an electronic record by a subscriber using an "
    "electronic technique."
)

# Split the same text across two chunks -- proves multi-chunk ordering,
# not just a single-shot stream.
FINAL_ANSWER_CHUNKS = (
    "Section 2(1)(ta) of the IT Act 2000 defines 'electronic signature' ",
    "as authentication of an electronic record by a subscriber using an " "electronic technique.",
)

PII_MESSAGE = "What format does an Indian PAN number follow?"
RAW_PII_ANSWER = (
    "A PAN follows a fixed alphanumeric format -- for example, ABCDE1234F "
    "is a validly formatted PAN, structured as five letters, four digits, "
    "and one letter."
)


def _sse_events(raw_body: str) -> list[tuple[str | None, dict]]:
    """
    Parse encode_sse_event()'s wire format (api/utilities/streaming.py)
    into (event_name, data) pairs, in order.
    """

    events: list[tuple[str | None, dict]] = []
    event_name: str | None = None
    data_lines: list[str] = []

    for line in raw_body.split("\n"):
        if line.startswith("event:"):
            event_name = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
        elif line == "":
            if data_lines:
                events.append((event_name, json.loads("".join(data_lines))))
            event_name = None
            data_lines = []

    return events


def _plan(*, message: str) -> ExecutionPlanDTO:
    return ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepDTO(
                id="step-1",
                agent=AgentTypeEnum.LEGAL,
                instruction=message,
                depends_on=(),
                stage=1,
                arguments={},
            ),
        ),
        metadata={},
    )


@pytest.mark.asyncio
async def test_stream_chat_completes_end_to_end_with_real_db_rows(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    """
    Normal stream-through-to-final: real HTTP, real streaming, then
    real Postgres rows identical in shape to what chat() (non-
    streaming) produces for an equivalent turn -- the same three
    assertions test_agent_decision_compliance_log.py already makes
    for chat(), now for stream_chat().
    """

    final_decision = AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        reason="Answering directly from known statute text.",
        final_response=FINAL_ANSWER,
    )

    async def fake_reason(self, *, request, context=()):
        return final_decision

    async def fake_plan_generate(self, *, request):
        return _plan(message=CHAT_MESSAGE)

    async def fake_stream_final_answer(self, *, request, context=()):
        yield AgentStreamChunkDTO(content=FINAL_ANSWER_CHUNKS[0], is_final=False)
        yield AgentStreamChunkDTO(
            content=FINAL_ANSWER_CHUNKS[1],
            is_final=True,
            finish_reason="stop",
        )

    request_start = datetime.now(UTC)

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))
        patches.enter_context(
            patch.object(BaseAgent, "stream_final_answer", fake_stream_final_answer)
        )

        async with e2e_client.stream(
            "POST",
            "/api/v1/chat/stream",
            data={"conversation_id": conversation_id, "message": CHAT_MESSAGE},
            headers=registered_user["headers"],
        ) as response:
            assert response.status_code == 200
            raw_body = (await response.aread()).decode("utf-8")

    events = _sse_events(raw_body)

    # --------------------------------------------------------------
    # SSE shape: events arrive in order, is_final only on the last one.
    # --------------------------------------------------------------

    assert len(events) == 3, events

    for event_name, data in events[:-1]:
        assert event_name == "message"
        assert data["is_final"] is False

    final_event_name, final_data = events[-1]
    assert final_event_name == "complete"
    assert final_data["is_final"] is True

    assert [data["content"] for _, data in events[:2]] == list(FINAL_ANSWER_CHUNKS)
    # Terminal chunk content is deliberately empty -- the full text
    # already reached the client via the two chunks above (see
    # AIOrchestrator.stream()'s docstring on why).
    assert final_data["content"] == ""

    # --------------------------------------------------------------
    # Real DB rows, matching chat()'s non-streaming shape exactly.
    # --------------------------------------------------------------

    async with session_factory() as session:
        conversation_events = await ConversationEventRepository(session=session).list(
            conversation_id=conversation_id,
        )

    assistant_events = [e for e in conversation_events if e.role == MessageRoleEnum.ASSISTANT]
    assert len(assistant_events) == 1, conversation_events
    assert assistant_events[0].content == FINAL_ANSWER

    async with session_factory() as session:
        compliance_rows = await ComplianceLogRepository(session=session).list_for_user(
            user_id=registered_user["user_id"],
            start=request_start - timedelta(seconds=5),
            end=datetime.now(UTC) + timedelta(seconds=5),
            event_type=ComplianceEventTypeEnum.RESPONSE_RETURNED,
        )

    assert len(compliance_rows) == 1, compliance_rows
    payload = compliance_rows[0].payload
    assert payload["content_hash"] == _hash(FINAL_ANSWER)
    assert payload["content_length"] == len(FINAL_ANSWER)
    assert payload["action_required"] is False

    # --------------------------------------------------------------
    # Usage: a real, pre-existing gap, not a streaming-specific one --
    # confirmed while building this test (traced AgentResponseMapper.
    # map(), which never sets AgentResponseDTO.usage at all -- true
    # for chat() too, mocked or fully real LLM calls, streaming or
    # not). UsageService.record()'s own zero-token guard means no row
    # is written. Asserting that honestly here, not fabricating usage
    # data that no real code path supplies today, per this session's
    # standing rule against guessing past real gaps.
    # --------------------------------------------------------------

    day_window = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    async with session_factory() as session:
        daily_tokens = await UsageRecordRepository(session=session).get_daily_token_usage(
            user_id=registered_user["user_id"],
            window_start=day_window,
        )

    assert daily_tokens == 0


@pytest.mark.asyncio
async def test_stream_chat_redacts_pii_with_zero_raw_pii_reaching_the_client(
    e2e_client: AsyncClient,
    registered_user: dict,
    conversation_id: str,
) -> None:
    """
    The specific bug Phase 4's investigation found, now verified at
    the real HTTP boundary: a REDACTED guardrail verdict must never
    let the raw, pre-redaction text reach the client -- not via any
    streamed chunk, not via the terminal chunk's content. Only the
    real, local Presidio IN_PAN recognizer (agentic/guardrails/pii.py)
    -- not mocked -- decides this; the LLM layer is what's faked, same
    as every other test in this file/suite.
    """

    final_decision = AgentDecision(
        decision_type=AgentDecisionType.FINAL,
        reason="Answering from the user's own account record.",
        final_response=RAW_PII_ANSWER,
    )

    async def fake_reason(self, *, request, context=()):
        return final_decision

    async def fake_plan_generate(self, *, request):
        return _plan(message=PII_MESSAGE)

    async def fake_stream_final_answer(self, *, request, context=()):
        # Same raw PII text the structured decision produced -- a
        # realistic scenario where both generations surface it.
        yield AgentStreamChunkDTO(content=RAW_PII_ANSWER, is_final=True, finish_reason="stop")

    async with AsyncExitStack() as patches:
        patches.enter_context(patch.object(LLMPlanGenerator, "generate", fake_plan_generate))
        patches.enter_context(patch.object(BaseAgent, "_reason", fake_reason))
        patches.enter_context(
            patch.object(BaseAgent, "stream_final_answer", fake_stream_final_answer)
        )

        async with e2e_client.stream(
            "POST",
            "/api/v1/chat/stream",
            data={"conversation_id": conversation_id, "message": PII_MESSAGE},
            headers=registered_user["headers"],
        ) as response:
            assert response.status_code == 200
            raw_body = (await response.aread()).decode("utf-8")

    events = _sse_events(raw_body)

    # REDACTED collapses to exactly one non-streamed terminal chunk --
    # see AIOrchestrator.stream()'s docstring for why the buffered raw
    # chunk must never be replayed here.
    assert len(events) == 1, events

    event_name, data = events[0]
    assert event_name == "complete"
    assert data["is_final"] is True
    assert "ABCDE1234F" not in data["content"]
    assert "[REDACTED" in data["content"]

    # Also check the raw response body directly, not just the parsed
    # event -- proves the PAN never appeared anywhere on the wire,
    # not just outside the one field this test happens to check.
    assert "ABCDE1234F" not in raw_body

    async with session_factory() as session:
        conversation_events = await ConversationEventRepository(session=session).list(
            conversation_id=conversation_id,
        )

    assistant_events = [e for e in conversation_events if e.role == MessageRoleEnum.ASSISTANT]
    assert len(assistant_events) == 1
    assert "ABCDE1234F" not in assistant_events[0].content
    assert "[REDACTED" in assistant_events[0].content
