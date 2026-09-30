"""
Unit tests for ConversationSummarizationService's LLM call: its tokens
count toward the request's usage and token quota, and it is bounded by
the request's deadline (review G1).

The LLM client is a stub under the real LLMClient.generate(), so the
quota check and the usage recording run as they do in production.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from adapters.clients.llm.base import LLMClient
from application.services.conversation_summarization import (
    UNSUMMARIZED_EVENT_LIMIT,
    ConversationSummarizationService,
)
from core.deadline import deadline_within
from core.dto.clients.llm import LLMRequestDTO, LLMResponseDTO, LLMStreamChunkDTO
from core.enums import MessageRoleEnum
from core.exceptions.rate_limit import RequestTokenQuotaExceededError
from core.usage import check_request_token_quota, request_token_quota, usage_scope, usage_tally
from tests.builders.adapters.clients.llm import build_llm_response, build_llm_token_usage

pytestmark = pytest.mark.asyncio

SUMMARY_USAGE = build_llm_token_usage(prompt_tokens=300, completion_tokens=50, total_tokens=350)


class _StubClient(LLMClient):
    def __init__(self, *, delay: float = 0.0) -> None:
        self.calls = 0
        self._delay = delay

    @property
    def provider(self) -> str:
        return "groq"

    @property
    def model(self) -> str:
        return "summarizer"

    async def _generate(self, *, request: LLMRequestDTO) -> LLMResponseDTO:
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        return build_llm_response(
            content="Summary of the earlier turns.",
            provider="groq",
            model="summarizer",
            usage=SUMMARY_USAGE,
        )

    async def stream(self, *, request: LLMRequestDTO) -> AsyncIterator[LLMStreamChunkDTO]:
        raise NotImplementedError


def _conversation() -> SimpleNamespace:
    return SimpleNamespace(
        id="conversation-1",
        rolling_summary=None,
        rolling_summary_through_created_at=None,
    )


def _events(count: int) -> list[SimpleNamespace]:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    return [
        SimpleNamespace(
            role=MessageRoleEnum.USER if i % 2 == 0 else MessageRoleEnum.ASSISTANT,
            content=f"message {i}",
            created_at=start + timedelta(minutes=i),
        )
        for i in range(count)
    ]


def _service(client: LLMClient) -> ConversationSummarizationService:
    event_service = AsyncMock()
    event_service.list.return_value = _events(UNSUMMARIZED_EVENT_LIMIT + 5)
    return ConversationSummarizationService(
        session=AsyncMock(),
        conversation_event_service=event_service,
        llm_client=client,
    )


async def test_summarization_tokens_reach_the_request_usage_tally() -> None:
    client = _StubClient()

    with usage_tally() as tally:
        conversation = await _service(client).ensure_summarized(conversation=_conversation())

    assert client.calls == 1
    assert conversation.rolling_summary == "Summary of the earlier turns."
    assert (tally.prompt_tokens, tally.completion_tokens) == (300, 50)


async def test_summarization_tokens_count_toward_the_request_token_quota() -> None:
    """
    A later call of the same request (the orchestrator's scope) is
    refused once summarization has used up the quota.
    """

    client = _StubClient()

    with request_token_quota(1000):
        await _service(client).ensure_summarized(conversation=_conversation())

        with (
            usage_scope(estimate_tokens=len),
            pytest.raises(RequestTokenQuotaExceededError) as raised,
        ):
            check_request_token_quota(["x" * 651])  # 350 used + 651 > 1000

    assert client.calls == 1
    assert raised.value.used == 350


async def test_summarization_over_the_request_quota_is_skipped_not_made() -> None:
    client = _StubClient()
    conversation = _conversation()

    with request_token_quota(1):
        result = await _service(client).ensure_summarized(conversation=conversation)

    # Refused before the provider call; best-effort: the request goes on
    # unsummarized, and its next call is refused by the same quota.
    assert client.calls == 0
    assert result.rolling_summary is None


async def test_slow_summarization_is_cut_off_at_the_request_deadline() -> None:
    client = _StubClient(delay=5)
    conversation = _conversation()

    started = time.monotonic()
    with deadline_within(0.2):
        result = await _service(client).ensure_summarized(conversation=conversation)

    assert time.monotonic() - started < 2
    assert client.calls == 1
    assert result.rolling_summary is None


async def test_summarization_has_its_own_time_limit_without_a_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from config.settings import get_settings

    monkeypatch.setattr(get_settings().llm, "SUMMARIZATION_TIMEOUT_S", 0.2)
    client = _StubClient(delay=5)

    started = time.monotonic()
    result = await _service(client).ensure_summarized(conversation=_conversation())

    assert time.monotonic() - started < 2
    assert result.rolling_summary is None


async def test_summarization_with_no_time_left_is_not_attempted() -> None:
    client = _StubClient()

    with deadline_within(-1):
        result = await _service(client).ensure_summarized(conversation=_conversation())

    assert client.calls == 0
    assert result.rolling_summary is None
