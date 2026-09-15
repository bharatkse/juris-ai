"""
Cache-wrapping decorator for EmbeddingProviderProtocol.

Embeddings for a given (model, text) pair are fully deterministic --
pure feed-forward inference, no sampling involved -- making them a
safe, unconditional caching candidate (unlike LLM-judge calls, which
are only deterministic-in-practice via temperature=0.0; see
wiring/factories/evaluation.py::build_llm_judge()).

Wraps rag.hybrid_retriever's query embedding, agentic.evaluation.
similarity's answer/evidence embedding, and rag.indexer's ingestion-time
embedding -- all three share the one process-lifetime instance built in
wiring/factories/rag.py, so wrapping it there covers all three call
sites with a single change.
"""

from __future__ import annotations

import hashlib

from adapters.cache.base import AbstractCache
from adapters.observability.metrics import metrics
from rag.models import EmbeddingMetadata
from rag.protocols.embedding_provider import EmbeddingProviderProtocol

_CACHE_KEY_VERSION = "v1"


class CachingEmbeddingProvider:
    """
    Memoizes embed() per-text against a shared AbstractCache.

    embed() checks the cache for every text in the batch, sends only
    the cache misses to the wrapped provider in one batch call (never
    one-by-one -- preserves the wrapped provider's own batching), then
    merges and back-fills the cache, preserving input order throughout.
    """

    def __init__(
        self,
        *,
        wrapped: EmbeddingProviderProtocol,
        cache: AbstractCache,
        ttl_seconds: int,
    ) -> None:
        self._wrapped = wrapped
        self._cache = cache
        self._ttl_seconds = ttl_seconds

    @property
    def metadata(self) -> EmbeddingMetadata:
        return self._wrapped.metadata

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()

        return f"jurisai:cache:embed:{_CACHE_KEY_VERSION}:{self.metadata.model_name}:{digest}"

    async def embed(
        self,
        *,
        texts: list[str],
    ) -> list[list[float]]:
        if not texts:
            return await self._wrapped.embed(texts=texts)

        keys = [self._cache_key(text) for text in texts]
        cached = [await self._cache.get(key) for key in keys]

        miss_indices = [index for index, value in enumerate(cached) if value is None]

        hit_count = len(texts) - len(miss_indices)

        if hit_count:
            metrics.record_cache_request(result="hit", cache="embedding", count=hit_count)

        if miss_indices:
            metrics.record_cache_request(result="miss", cache="embedding", count=len(miss_indices))
            miss_texts = [texts[index] for index in miss_indices]

            computed = await self._wrapped.embed(texts=miss_texts)

            for index, vector in zip(miss_indices, computed, strict=True):
                cached[index] = vector

                await self._cache.set(
                    keys[index],
                    vector,
                    ttl=self._ttl_seconds,
                )

        return cached

    async def embed_one(
        self,
        *,
        text: str,
    ) -> list[float]:
        # Routed through this class's own (cached) embed(), not
        # self._wrapped.embed_one() -- the wrapped provider's
        # embed_one() calls its OWN embed(), bypassing this cache
        # entirely if called directly.
        vectors = await self.embed(texts=[text])

        return vectors[0]
