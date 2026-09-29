"""
Retrying an agent's reasoning call (review R1).

Only unusable model output is retried (build_retry_classifier), with
backoff, and only while the backoff plus a whole attempt still fits the
turn's time budget and the enclosing deadline.
"""

from __future__ import annotations

import pytest

from agentic.execution.config import ExecutionRetryPolicy
from core.deadline import deadline_within
from core.enums import ExecutionStatusEnum
from core.exceptions.client import (
    ClientConnectionError,
    ClientInvalidResponseError,
    ClientProviderError,
    ClientRateLimitError,
    ClientServiceUnavailableError,
    ClientTimeoutError,
)
from tests.unit.agentic.agents.runtime.test_delegation import PARENT_ANSWER, _final, _llm, _Runtime
from wiring.factories.executor import build_retry_classifier

INVALID = ClientInvalidResponseError(message="LLM returned an invalid structured response.")


@pytest.fixture
def delays(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """The backoff sleeps, recorded instead of slept."""

    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("agentic.agents.runtime.execution.asyncio.sleep", sleep)
    return slept


def _runtime(*outcomes, policy: ExecutionRetryPolicy | None = None) -> _Runtime:
    """The legal agent's LLM returns or raises each of ``outcomes`` in turn."""

    legal = _llm()
    legal.generate_structured.side_effect = list(outcomes)
    runtime = _Runtime(legal=legal, contract=_llm())
    runtime.legal_llm = legal
    # As production wires it (wiring/factories/executor.py).
    runtime.execution._retry_policy = policy or ExecutionRetryPolicy()
    runtime.execution._retry_classifier = build_retry_classifier()
    return runtime


def test_only_unusable_output_is_retried() -> None:
    classifier = build_retry_classifier()

    assert classifier.is_retryable(error=INVALID)
    for error in (
        ClientRateLimitError(),
        ClientTimeoutError(),
        ClientConnectionError(),
        ClientServiceUnavailableError(),
        ClientProviderError(),
    ):
        assert not classifier.is_retryable(error=error), type(error).__name__


@pytest.mark.asyncio
async def test_invalid_output_is_retried_and_the_turn_succeeds(delays: list[float]) -> None:
    """
    Before the fix the first retry crashed: reason() asked the policy for
    the delay of retry 0, which raises ValueError.
    """

    runtime = _runtime(INVALID, _final(PARENT_ANSWER))

    handle = await runtime.execution.start(agent_id="legal", request=_request())
    result = await handle.reason()

    assert result.status is not ExecutionStatusEnum.FAILED
    assert result.decision.final_response == PARENT_ANSWER
    assert result.retry_count == 1
    assert runtime.legal_llm.generate_structured.await_count == 2
    assert delays == [0.5]  # retry 1 waits base_delay_seconds


@pytest.mark.asyncio
async def test_retries_stop_at_max_attempts(delays: list[float]) -> None:
    runtime = _runtime(INVALID, INVALID, INVALID, _final(PARENT_ANSWER))

    handle = await runtime.execution.start(
        agent_id="legal",
        request=_request(),
    )
    result = await handle.reason()

    assert result.status is ExecutionStatusEnum.FAILED
    assert result.retry_count == 2
    assert runtime.legal_llm.generate_structured.await_count == 3
    assert delays == [0.5, 1.0]


@pytest.mark.asyncio
async def test_a_provider_outage_is_not_retried_here(delays: list[float]) -> None:
    """Already retried by the SDK and failed over; not multiplied here."""

    runtime = _runtime(ClientRateLimitError(), _final(PARENT_ANSWER))

    handle = await runtime.execution.start(agent_id="legal", request=_request())
    result = await handle.reason()

    assert result.status is ExecutionStatusEnum.FAILED
    assert runtime.legal_llm.generate_structured.await_count == 1
    assert delays == []


@pytest.mark.asyncio
async def test_no_retry_when_the_deadline_leaves_too_little_time(delays: list[float]) -> None:
    """
    The deadline doesn't cancel an LLM call, so a retry started with a
    few seconds left would overrun the graph timeout.
    """

    runtime = _runtime(INVALID, _final(PARENT_ANSWER))

    handle = await runtime.execution.start(agent_id="legal", request=_request())
    with deadline_within(10):  # < 0.5 s backoff + 15 s minimum attempt
        result = await handle.reason()

    assert result.status is ExecutionStatusEnum.FAILED
    assert runtime.legal_llm.generate_structured.await_count == 1
    assert delays == []


@pytest.mark.asyncio
async def test_a_retry_that_fits_the_deadline_still_runs(delays: list[float]) -> None:
    runtime = _runtime(INVALID, _final(PARENT_ANSWER))

    handle = await runtime.execution.start(agent_id="legal", request=_request())
    with deadline_within(60):
        result = await handle.reason()

    assert result.status is not ExecutionStatusEnum.FAILED
    assert runtime.legal_llm.generate_structured.await_count == 2


@pytest.mark.asyncio
async def test_no_retry_when_the_turn_budget_is_nearly_spent(delays: list[float]) -> None:
    runtime = _runtime(
        INVALID,
        _final(PARENT_ANSWER),
        policy=ExecutionRetryPolicy(min_attempt_seconds=1_000.0),  # > the turn's 120 s
    )

    handle = await runtime.execution.start(agent_id="legal", request=_request())
    result = await handle.reason()

    assert result.status is ExecutionStatusEnum.FAILED
    assert runtime.legal_llm.generate_structured.await_count == 1


def test_min_attempt_seconds_must_not_be_negative() -> None:
    with pytest.raises(ValueError):
        ExecutionRetryPolicy(min_attempt_seconds=-1)


def _request():
    from core.dto.agent import AgentContextDTO, AgentRequestDTO
    from core.dto.conversation import ConversationDTO
    from core.dto.message import MessageDTO
    from core.enums import MessageRoleEnum

    return AgentRequestDTO(
        conversation=ConversationDTO(
            messages=(MessageDTO(role=MessageRoleEnum.USER, content="What notice does it need?"),),
        ),
        instruction="Answer the user's question.",
        arguments={},
        context=AgentContextDTO(
            user_id="u", execution_id="e", thread_id="t", conversation_event_id="c"
        ),
    )
