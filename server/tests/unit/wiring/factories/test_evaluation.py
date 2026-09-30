"""
Unit tests for build_llm_judge()'s cache hit/miss instrumentation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.exceptions.client import (
    ClientAuthenticationError,
    ClientConnectionError,
    ClientInvalidResponseError,
    ClientRateLimitError,
    ClientServiceUnavailableError,
    ClientTimeoutError,
)
from core.judge_availability import judge_availability_probe
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


async def test_the_judge_builds_its_client_once_and_reuses_it() -> None:
    """R17: no new Groq/Ollama clients per judge call (they were never closed)."""

    client = MagicMock()
    client.provider = "groq"
    client.generate = AsyncMock(return_value=build_llm_response(content="verdict"))
    resolver = MagicMock()
    resolver.get.return_value = client

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    with patch("wiring.factories.evaluation.build_llm_resolver", return_value=resolver) as build:
        judge = build_llm_judge(settings=_settings(), cache=cache)
        await judge("first prompt")
        await judge("second prompt")

    build.assert_called_once()
    assert client.generate.await_count == 2


async def test_the_judge_uses_the_apps_shared_resolver_when_given() -> None:
    client = MagicMock()
    client.provider = "groq"
    client.generate = AsyncMock(return_value=build_llm_response(content="verdict"))
    shared = MagicMock()
    shared.get.return_value = client

    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    with patch("wiring.factories.evaluation.build_llm_resolver") as build:
        judge = build_llm_judge(settings=_settings(), cache=cache, llm_resolver=shared)
        await judge("a prompt")

    build.assert_not_called()
    client.generate.assert_awaited_once()


@pytest.mark.parametrize(
    "error",
    [
        ClientConnectionError("connection refused"),
        ClientServiceUnavailableError("503"),
        ClientTimeoutError("timed out"),
        ClientRateLimitError("429"),
    ],
)
async def test_a_judge_call_the_provider_couldnt_serve_is_recorded(error: Exception) -> None:
    """R17: an unavailable judge provider is recorded, and the error still raised."""

    judge = _judge_failing_with(error)

    with judge_availability_probe() as probe, pytest.raises(type(error)):
        await judge("a prompt")

    assert probe.provider_unavailable is True


@pytest.mark.parametrize(
    "error",
    [ClientAuthenticationError("bad key"), ClientInvalidResponseError("empty")],
)
async def test_other_judge_failures_are_not_an_outage(error: Exception) -> None:
    judge = _judge_failing_with(error)

    with judge_availability_probe() as probe, pytest.raises(type(error)):
        await judge("a prompt")

    assert probe.provider_unavailable is False


def _judge_failing_with(error: Exception):
    client = MagicMock()
    client.provider = "groq"
    client.generate = AsyncMock(side_effect=error)
    resolver = MagicMock()
    resolver.get.return_value = client
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return build_llm_judge(settings=_settings(), cache=cache, llm_resolver=resolver)
