"""
Unit tests for EmbeddingSimilarity: an embedding failure or a call that
runs too long surfaces as SimilarityUnavailableError, which the answer
gate treats as "couldn't score" (review G2), never as a crash.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock

import pytest

from agentic.evaluation.similarity import EmbeddingSimilarity
from core.exceptions.rag import EmbeddingError, SimilarityUnavailableError

pytestmark = pytest.mark.asyncio


def _provider(**kwargs) -> AsyncMock:
    provider = AsyncMock()
    provider.embed = AsyncMock(**kwargs)
    return provider


async def test_similar_texts_score_by_cosine() -> None:
    similarity = EmbeddingSimilarity(
        embedding_provider=_provider(return_value=[[1.0, 0.0], [1.0, 0.0]]),
    )

    assert await similarity("a", "b") == pytest.approx(1.0)


@pytest.mark.parametrize(
    "error",
    [EmbeddingError("model not loaded"), RuntimeError("CUDA out of memory")],
    ids=["embedding-error", "unexpected-error"],
)
async def test_an_embedding_failure_is_reported_as_unavailable(error: Exception) -> None:
    similarity = EmbeddingSimilarity(embedding_provider=_provider(side_effect=error))

    with pytest.raises(SimilarityUnavailableError):
        await similarity("a", "b")


async def test_an_embedding_call_past_its_time_limit_is_reported_as_unavailable() -> None:
    async def slow(**_kwargs):
        await asyncio.sleep(5)

    similarity = EmbeddingSimilarity(
        embedding_provider=_provider(side_effect=slow),
        timeout_seconds=0.1,
    )

    started = time.monotonic()
    with pytest.raises(SimilarityUnavailableError):
        await similarity("a", "b")

    assert time.monotonic() - started < 2


async def test_cancellation_still_propagates() -> None:
    similarity = EmbeddingSimilarity(
        embedding_provider=_provider(side_effect=asyncio.CancelledError()),
    )

    with pytest.raises(asyncio.CancelledError):
        await similarity("a", "b")
