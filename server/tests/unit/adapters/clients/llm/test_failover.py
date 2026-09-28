"""
Unit tests for FailoverLLMClient.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import BaseModel

from adapters.clients.llm.base import LLMClient
from adapters.clients.llm.failover import FAILOVER_ERRORS, FailoverLLMClient
from core.dto.clients.llm import (
    LLMMessageDTO,
    LLMRequestDTO,
    LLMResponseDTO,
    LLMStreamChunkDTO,
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
    ) -> None:
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
        return LLMResponseDTO(content=self._content, provider=self._provider, model=self.model)

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
) -> FailoverLLMClient:
    return FailoverLLMClient(primary=primary, fallback=fallback, fits_fallback=lambda _r: fits)


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
    # The request's own schema is what the fallback is held to.
    assert fallback.requests[0].response_format["json_schema"]["schema"] == {"type": "object"}


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
async def test_generate_structured_uses_the_request_schema_when_set() -> None:
    class Answer(BaseModel):
        text: str

    client = FakeClient(provider="groq", content='{"text": "ok"}')

    await client.generate_structured(request=REQUEST, response_model=Answer)
    await client.generate_structured(
        request=replace(REQUEST, response_schema=None),
        response_model=Answer,
    )

    narrowed, default = (r.response_format["json_schema"]["schema"] for r in client.requests)
    assert narrowed == {"type": "object"}
    assert default == Answer.model_json_schema()
