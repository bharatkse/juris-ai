"""
Unit tests for LLMClient.generate()'s call-duration/token instrumentation.

Uses a minimal concrete subclass implementing only _generate() -- the
provider-specific hook -- to exercise the base class's own generate()
wrapper in isolation from any real provider (Groq/Ollama).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from adapters.clients.llm.base import LLMClient
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMStreamChunkDTO
from core.exceptions.client import ClientProviderError
from tests.builders.adapters.clients.llm import (
    build_llm_request,
    build_llm_response,
    build_llm_token_usage,
)

pytestmark = pytest.mark.asyncio


class _StubClient(LLMClient):
    def __init__(
        self, *, response: LLMResponseDTO | None = None, error: Exception | None = None
    ) -> None:
        self._response = response
        self._error = error

    @property
    def provider(self) -> str:
        return "stub-provider"

    @property
    def model(self) -> str:
        return "stub-default-model"

    async def _generate(self, *, request: LLMRequestDTO) -> LLMResponseDTO:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response

    async def stream(self, *, request: LLMRequestDTO) -> AsyncIterator[LLMStreamChunkDTO]:
        raise NotImplementedError


async def test_generate_records_duration_and_tokens_using_the_responses_own_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The recorded provider/model must come from the response (which
    reflects any per-request inference.model override), not from
    self.provider/self.model (the client's own default) -- this is
    the exact bug class build_llm_judge()'s per-call model override
    would silently misreport if generate() used self.model instead.
    """

    response = build_llm_response(
        provider="groq",
        model="overridden-judge-model",
        usage=build_llm_token_usage(prompt_tokens=7, completion_tokens=3),
    )

    client = _StubClient(response=response)

    mock_record = MagicMock()
    monkeypatch.setattr("adapters.clients.llm.base.metrics.record_llm_call", mock_record)

    result = await client.generate(request=build_llm_request())

    assert result is response

    mock_record.assert_called_once()
    _, kwargs = mock_record.call_args
    assert kwargs["provider"] == "groq"
    assert kwargs["model"] == "overridden-judge-model"
    assert kwargs["usage"] is response.usage
    assert isinstance(kwargs["duration"], float)
    assert kwargs["duration"] >= 0


async def test_generate_records_duration_using_client_identity_when_it_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    No response exists to read provider/model/usage from when
    _generate() raises -- must fall back to self.provider/self.model,
    with usage=None, and must still re-raise the original error.
    """

    client = _StubClient(error=ClientProviderError(message="boom"))

    mock_record = MagicMock()
    monkeypatch.setattr("adapters.clients.llm.base.metrics.record_llm_call", mock_record)

    with pytest.raises(ClientProviderError):
        await client.generate(request=build_llm_request())

    mock_record.assert_called_once()
    _, kwargs = mock_record.call_args
    assert kwargs["provider"] == "stub-provider"
    assert kwargs["model"] == "stub-default-model"
    assert kwargs["usage"] is None
