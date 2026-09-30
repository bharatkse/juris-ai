"""
Unit tests for FailoverLLMClient.
"""

from __future__ import annotations

import asyncio
import time

import pytest
from pydantic import BaseModel

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.failover import FAILOVER_ERRORS, FailoverLLMClient
from core.deadline import deadline_within
from core.dto.clients.llm import (
    LLMMessageDTO,
    LLMRequestDTO,
    LLMResponseDTO,
    LLMStreamChunkDTO,
    LLMTokenUsageDTO,
)
from core.dto.inference import LLMInferenceConfig
from core.enums import MessageRoleEnum
from core.exceptions.client import (
    ClientAuthenticationError,
    ClientConfigurationError,
    ClientConnectionError,
    ClientError,
    ClientProviderError,
    ClientRateLimitError,
    ClientServiceUnavailableError,
    ClientTimeoutError,
)

REQUEST = LLMRequestDTO(
    messages=(LLMMessageDTO(role=MessageRoleEnum.USER, content="What is an FIR?"),),
    inference=LLMInferenceConfig(model="openai/gpt-oss-120b", temperature=0.0),
    response_schema={"type": "object"},
)


class FakeClient(LLMClient):
    def __init__(
        self,
        *,
        provider: str,
        error: ClientError | None = None,
        content: str = "answer",
        chunks: tuple[str, ...] = (),
        fail_after_chunks: bool = False,
        usage: LLMTokenUsageDTO | None = None,
    ) -> None:
        self._usage = usage
        self._provider = provider
        self._error = error
        self._content = content
        self._chunks = chunks
        self._fail_after_chunks = fail_after_chunks
        self.requests: list[LLMRequestDTO] = []

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return f"{self._provider}-model"

    async def _generate(self, *, request: LLMRequestDTO) -> LLMResponseDTO:
        self.requests.append(request)
        if self._error is not None:
            raise self._error
        return LLMResponseDTO(
            content=self._content, provider=self._provider, model=self.model, usage=self._usage
        )

    async def stream(self, *, request: LLMRequestDTO):
        self.requests.append(request)
        if self._error is not None and not self._fail_after_chunks:
            raise self._error
        for chunk in self._chunks:
            yield LLMStreamChunkDTO(content=chunk)
        if self._error is not None:
            raise self._error


def _failover(
    primary: FakeClient,
    fallback: FakeClient,
    *,
    fits: bool = True,
    min_seconds: float = 60.0,
) -> FailoverLLMClient:
    return FailoverLLMClient(
        primary=primary,
        fallback=fallback,
        fits_fallback=lambda _r: fits,
        min_fallback_seconds=min_seconds,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", FAILOVER_ERRORS)
async def test_an_unavailable_primary_fails_over_to_the_fallback(error_type) -> None:
    primary = FakeClient(provider="groq", error=error_type())
    fallback = FakeClient(provider="local", content="local answer")

    response = await _failover(primary, fallback).generate(request=REQUEST)

    assert response.content == "local answer"
    assert response.provider == "local"
    (sent,) = fallback.requests
    # Same prompt and schema; the primary's model override is dropped.
    assert sent.messages == REQUEST.messages
    assert sent.response_schema == REQUEST.response_schema
    assert sent.inference.model is None
    assert sent.inference.temperature == REQUEST.inference.temperature


def test_failover_errors_are_the_availability_errors() -> None:
    assert set(FAILOVER_ERRORS) == {
        ClientRateLimitError,
        ClientTimeoutError,
        ClientConnectionError,
        ClientServiceUnavailableError,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ClientAuthenticationError(),
        ClientConfigurationError(),
        # A 4xx, or a response that couldn't be used.
        ClientProviderError(message="400 bad request"),
        ClientProviderError(message="LLM returned an invalid structured response."),
    ],
)
async def test_other_errors_still_fail_the_call(error) -> None:
    primary = FakeClient(provider="groq", error=error)
    fallback = FakeClient(provider="local")

    with pytest.raises(type(error)):
        await _failover(primary, fallback).generate(request=REQUEST)

    assert fallback.requests == []


@pytest.mark.asyncio
async def test_a_healthy_primary_is_used_alone() -> None:
    primary = FakeClient(provider="groq", content="groq answer")
    fallback = FakeClient(provider="local")

    response = await _failover(primary, fallback).generate(request=REQUEST)

    assert response.content == "groq answer"
    assert primary.requests == [REQUEST]
    assert fallback.requests == []


@pytest.mark.asyncio
async def test_a_prompt_too_big_for_the_fallback_is_not_failed_over() -> None:
    primary = FakeClient(provider="groq", error=ClientRateLimitError())
    fallback = FakeClient(provider="local")

    with pytest.raises(ClientRateLimitError):
        await _failover(primary, fallback, fits=False).generate(request=REQUEST)

    assert fallback.requests == []


@pytest.mark.asyncio
async def test_when_the_fallback_also_fails_the_primary_error_is_raised() -> None:
    primary = FakeClient(provider="groq", error=ClientTimeoutError())
    fallback = FakeClient(provider="local", error=ClientConnectionError())

    with pytest.raises(ClientTimeoutError):
        await _failover(primary, fallback).generate(request=REQUEST)

    assert len(fallback.requests) == 1


@pytest.mark.asyncio
async def test_structured_calls_fail_over_too() -> None:
    class Answer(BaseModel):
        text: str

    primary = FakeClient(provider="groq", error=ClientServiceUnavailableError())
    fallback = FakeClient(provider="local", content='{"text": "from local"}')

    result = await _failover(primary, fallback).generate_structured(
        request=REQUEST,
        response_model=Answer,
    )

    assert result == Answer(text="from local")
    # The narrower per-request schema travels with the request, for a
    # client that decodes against it (LocalLLMClient).
    assert fallback.requests[0].response_schema == {"type": "object"}


def test_reports_the_primary_provider_and_model() -> None:
    client = _failover(FakeClient(provider="groq"), FakeClient(provider="local"))

    assert client.provider == "groq"
    assert client.model == "groq-model"


@pytest.mark.asyncio
async def test_a_stream_that_fails_before_its_first_chunk_fails_over() -> None:
    primary = FakeClient(provider="groq", error=ClientRateLimitError())
    fallback = FakeClient(provider="local", chunks=("a", "b"))

    chunks = [c.content async for c in _failover(primary, fallback).stream(request=REQUEST)]

    assert chunks == ["a", "b"]
    assert fallback.requests[0].inference.model is None


@pytest.mark.asyncio
async def test_a_stream_that_fails_midway_is_not_failed_over() -> None:
    primary = FakeClient(
        provider="groq", error=ClientConnectionError(), chunks=("a",), fail_after_chunks=True
    )
    fallback = FakeClient(provider="local", chunks=("x",))
    received: list[str] = []

    with pytest.raises(ClientConnectionError):
        async for chunk in _failover(primary, fallback).stream(request=REQUEST):
            received.append(chunk.content)

    assert received == ["a"]
    assert fallback.requests == []


@pytest.mark.asyncio
async def test_generate_structured_asks_the_provider_for_the_models_own_schema() -> None:
    """The narrower response_schema never changes what Groq is sent."""

    class Answer(BaseModel):
        text: str

    client = FakeClient(provider="groq", content='{"text": "ok"}')

    await client.generate_structured(request=REQUEST, response_model=Answer)

    (sent,) = client.requests
    assert sent.response_format["json_schema"]["schema"] == Answer.model_json_schema()
    assert sent.response_schema == REQUEST.response_schema


class SlowClient(FakeClient):
    def __init__(self, *, seconds: float) -> None:
        super().__init__(provider="local")
        self._seconds = seconds

    async def _generate(self, *, request: LLMRequestDTO) -> LLMResponseDTO:
        self.requests.append(request)
        await asyncio.sleep(self._seconds)
        return LLMResponseDTO(content="late", provider="local", model=self.model)


@pytest.mark.asyncio
async def test_no_failover_when_too_little_of_the_deadline_is_left() -> None:
    primary = FakeClient(provider="groq", error=ClientRateLimitError())
    fallback = FakeClient(provider="local")

    with deadline_within(30), pytest.raises(ClientRateLimitError):
        await _failover(primary, fallback, min_seconds=60).generate(request=REQUEST)

    assert fallback.requests == []


@pytest.mark.asyncio
async def test_failover_proceeds_with_enough_of_the_deadline_left() -> None:
    primary = FakeClient(provider="groq", error=ClientRateLimitError())
    fallback = FakeClient(provider="local", content="local answer")

    with deadline_within(120):
        response = await _failover(primary, fallback, min_seconds=60).generate(request=REQUEST)

    assert response.content == "local answer"


@pytest.mark.asyncio
async def test_a_fallback_call_still_running_at_the_deadline_is_cut_off() -> None:
    primary = FakeClient(provider="groq", error=ClientTimeoutError())
    fallback = SlowClient(seconds=5)
    started = time.monotonic()

    with deadline_within(0.2), pytest.raises(ClientTimeoutError):
        await _failover(primary, fallback, min_seconds=0.1).generate(request=REQUEST)

    # Failed fast with the primary's error, not after the slow call.
    assert time.monotonic() - started < 2
    assert len(fallback.requests) == 1


@pytest.mark.asyncio
async def test_a_failed_over_call_counts_the_fallbacks_usage_once() -> None:
    """
    FailoverLLMClient adds no usage of its own; each client's generate()
    records its own call, so the fallback's tokens are counted exactly
    once, under its own provider (R3).
    """

    from core.usage import usage_scope

    primary = FakeClient(provider="groq", error=ClientRateLimitError(message="429"))
    fallback = FakeClient(
        provider="ollama",
        usage=LLMTokenUsageDTO(prompt_tokens=40, completion_tokens=10, total_tokens=50),
    )

    with usage_scope() as meter:
        await _failover(primary, fallback).generate(request=REQUEST)

    assert (meter.calls, meter.total_tokens, meter.provider) == (1, 50, "ollama")


@pytest.mark.asyncio
async def test_an_answer_from_the_fallback_is_marked_on_the_request() -> None:
    """So a judge that then discards it can say so (review R17)."""

    from core.usage import fallback_answered, usage_scope

    primary = FakeClient(provider="groq", error=FAILOVER_ERRORS[0]())
    fallback = FakeClient(provider="local", content="local answer")

    with usage_scope():
        assert not fallback_answered()
        await _failover(primary, fallback).generate(request=REQUEST)
        assert fallback_answered()
