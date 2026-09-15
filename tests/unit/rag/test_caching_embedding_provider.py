"""
Unit tests for CachingEmbeddingProvider's cache hit/miss instrumentation.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from rag.caching_embedding_provider import CachingEmbeddingProvider
from rag.models import EmbeddingMetadata

pytestmark = pytest.mark.asyncio


def _provider(*, wrapped: MagicMock, cache: MagicMock) -> CachingEmbeddingProvider:
    wrapped.metadata = EmbeddingMetadata(model_name="test-model", dimension=3)

    return CachingEmbeddingProvider(
        wrapped=wrapped,
        cache=cache,
        ttl_seconds=3600,
    )


async def test_embed_records_a_miss_and_a_hit_for_the_metric_it_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    First call (nothing cached yet): all misses. Second call with the
    same text (now cached): all hits. Verified against the real
    module-level `metrics` singleton, not a bespoke mock, so this
    fails if record_cache_request's call signature or attribute names
    ever drift from what metrics.py actually defines.
    """

    wrapped = MagicMock()
    wrapped.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    store: dict[str, list[float]] = {}
    cache = MagicMock()
    cache.get = AsyncMock(side_effect=lambda key: store.get(key))
    cache.set = AsyncMock(side_effect=lambda key, value, ttl: store.__setitem__(key, value))

    provider = _provider(wrapped=wrapped, cache=cache)

    mock_record = MagicMock()
    monkeypatch.setattr(
        "rag.caching_embedding_provider.metrics.record_cache_request",
        mock_record,
    )

    await provider.embed(texts=["hello"])

    mock_record.assert_called_once_with(result="miss", cache="embedding", count=1)
    mock_record.reset_mock()

    await provider.embed(texts=["hello"])

    mock_record.assert_called_once_with(result="hit", cache="embedding", count=1)


async def test_embed_records_split_hit_and_miss_counts_within_one_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A batch with some texts already cached and some not must record
    both a hit count and a miss count for that single embed() call,
    not just one or the other.
    """

    wrapped = MagicMock()
    wrapped.embed = AsyncMock(return_value=[[0.9, 0.9, 0.9]])

    cache = MagicMock()
    cache.get = AsyncMock(side_effect=[[0.1, 0.1, 0.1], None])
    cache.set = AsyncMock()

    provider = _provider(wrapped=wrapped, cache=cache)

    mock_record = MagicMock()
    monkeypatch.setattr(
        "rag.caching_embedding_provider.metrics.record_cache_request",
        mock_record,
    )

    await provider.embed(texts=["cached-already", "not-cached-yet"])

    mock_record.assert_any_call(result="hit", cache="embedding", count=1)
    mock_record.assert_any_call(result="miss", cache="embedding", count=1)
    assert mock_record.call_count == 2
