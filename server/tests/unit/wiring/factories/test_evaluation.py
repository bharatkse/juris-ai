"""
Unit tests for build_llm_judge()'s cache hit/miss instrumentation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.builders.adapters.clients.llm import build_llm_response
from wiring.factories.evaluation import build_llm_judge

pytestmark = pytest.mark.asyncio


def _settings() -> MagicMock:
    settings = MagicMock()
    settings.llm.JUDGE_MODEL.value = "judge-model"
    settings.security.CACHE_TTL_SECONDS = 3600
    return settings


@patch("wiring.factories.evaluation.build_llm_resolver")
async def test_judge_records_a_cache_hit_and_never_calls_the_llm(
    mock_build_resolver: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.provider = "groq"
    client.generate = AsyncMock()

    resolver = MagicMock()
    resolver.get.return_value = client
    mock_build_resolver.return_value = resolver

    cache = MagicMock()
    cache.get = AsyncMock(return_value="cached answer")
    cache.set = AsyncMock()

    mock_record = MagicMock()
    monkeypatch.setattr("wiring.factories.evaluation.metrics.record_cache_request", mock_record)

    judge = build_llm_judge(settings=_settings(), cache=cache)
    result = await judge("some prompt")

    assert result == "cached answer"
    client.generate.assert_not_awaited()
    cache.set.assert_not_awaited()

    mock_record.assert_called_once_with(result="hit", cache="judge")


@patch("wiring.factories.evaluation.build_llm_resolver")
async def test_judge_records_a_cache_miss_and_calls_the_llm(
    mock_build_resolver: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.provider = "groq"
    client.generate = AsyncMock(return_value=build_llm_response(content="fresh answer"))

    resolver = MagicMock()
    resolver.get.return_value = client
    mock_build_resolver.return_value = resolver

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    mock_record = MagicMock()
    monkeypatch.setattr("wiring.factories.evaluation.metrics.record_cache_request", mock_record)

    judge = build_llm_judge(settings=_settings(), cache=cache)
    result = await judge("some prompt")

    assert result == "fresh answer"
    client.generate.assert_awaited_once()
    cache.set.assert_awaited_once()

    mock_record.assert_called_once_with(result="miss", cache="judge")
