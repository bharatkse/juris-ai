"""
Hybrid retriever.

The full retrieval pipeline for Juris-AI's RAG:

    query
      │
      ├──> vector search (PgVectorStore)    ─┐
      │                                       ├─> Reciprocal Rank Fusion
      └──> keyword search (KeywordStore)    ─┘         │
                                                         ▼
                                              fused candidate set (top ~20)
                                                         │
                                                         ▼
                                          CrossEncoderReranker (top_k, e.g. 5)
                                                         │
                                                         ▼
                                          relevance threshold filter
                                                         │
                                                         ▼
                                              final chunks returned to agent

Two deliberate design choices worth calling out:

1. Hybrid over vector-only: dense embeddings are good at semantic
   similarity ("indemnification obligations" ~ "party shall hold
   harmless") but routinely underweight exact tokens that matter a
   lot in legal text — section numbers, defined terms, case
   citations. Keyword search catches those; RRF fusion means neither
   signal has to "win" a hard vote, both contribute.

2. Rerank after fusion, not instead of it: cross-encoders are far
   more accurate per-pair but too slow to run over an entire corpus.
   Retrieve broad and cheap first (vector + keyword), then spend the
   expensive, accurate model only on the ~20 candidates that already
   passed a cheap filter.

ACL enforcement happens at the retrieval layer (allowed_document_ids
passed to both underlying stores), not just at the tool/agent
authorization layer — belt-and-suspenders against a document leaking
through retrieval even if some other component's authorization check
was missed.
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from src.core.logger import get_logger
from src.rag.embeddings import EmbeddingProvider
from src.rag.indexer import Chunk
from src.rag.reranker import CrossEncoderReranker

log = get_logger(__name__)

DEFAULT_FUSION_CANDIDATES = 20  # how many each of vector/keyword search contribute pre-fusion
RRF_K = 60  # standard RRF constant from the original paper; rarely needs tuning
DEFAULT_MIN_RERANK_SCORE = (
    0.3  # scores are sigmoid-bounded [0,1]; tune against eval set (see rag/evaluation/)
)


class VectorSearcher(Protocol):
    async def query(
        self,
        *,
        vector: list[float],
        top_k: int,
        allowed_document_ids: set[str] | None = None,
        embedding_model: str | None = None,
    ) -> list[tuple[Chunk, float]]: ...


class KeywordSearcher(Protocol):
    async def search(
        self,
        *,
        query: str,
        top_k: int,
        allowed_document_ids: set[str] | None = None,
    ) -> list[tuple[Chunk, float]]: ...


class HybridRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorSearcher,
        keyword_store: KeywordSearcher,
        reranker: CrossEncoderReranker,
        min_rerank_score: float = DEFAULT_MIN_RERANK_SCORE,
    ) -> None:
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._keyword_store = keyword_store
        self._reranker = reranker
        self._min_rerank_score = min_rerank_score

    async def retrieve(
        self,
        *,
        query: str,
        top_k: int = 5,
        allowed_document_ids: set[str] | None = None,
        fusion_candidates: int = DEFAULT_FUSION_CANDIDATES,
    ) -> list[tuple[Chunk, float]]:
        vector = await self._embeddings.embed_one(text=query)

        # Run vector and keyword searches concurrently
        vector_results, keyword_results = await asyncio.gather(
            self._vector_store.query(
                vector=vector,
                top_k=fusion_candidates,
                allowed_document_ids=allowed_document_ids,
                embedding_model=self._embeddings.model_name,
            ),
            self._keyword_store.search(
                query=query,
                top_k=fusion_candidates,
                allowed_document_ids=allowed_document_ids,
            ),
        )

        fused = self._reciprocal_rank_fusion(
            ranked_lists=[
                [chunk for chunk, _ in vector_results],
                [chunk for chunk, _ in keyword_results],
            ]
        )

        if not fused:
            log.debug("No candidates found for query=%r after fusion.", query)
            return []

        # Cap fused pool before reranking (e.g. 2 * fusion_candidates)
        rerank_pool = [(chunk, 0.0) for chunk in fused[: fusion_candidates * 2]]

        reranked = await self._reranker.rerank(
            query=query,
            candidates=rerank_pool,
            top_k=top_k,
        )

        filtered = [(chunk, score) for chunk, score in reranked if score >= self._min_rerank_score]

        log.debug(
            "retrieve(query=%r): %d vector + %d keyword -> %d fused -> "
            "%d reranked -> %d above threshold.",
            query,
            len(vector_results),
            len(keyword_results),
            len(fused),
            len(reranked),
            len(filtered),
        )

        return filtered

    @staticmethod
    def _reciprocal_rank_fusion(
        *,
        ranked_lists: list[list[Chunk]],
        k: int = RRF_K,
    ) -> list[Chunk]:
        """
        Standard RRF: score(doc) = sum over lists of 1 / (k + rank).
        Chunks appearing in both lists (even at different ranks) rise
        to the top without either retriever needing to "win" outright.
        """

        scores: dict[str, float] = {}
        chunks_by_id: dict[str, Chunk] = {}

        for ranked_list in ranked_lists:
            for rank, chunk in enumerate(ranked_list):
                scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
                chunks_by_id[chunk.id] = chunk

        ordered_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)

        return [chunks_by_id[cid] for cid in ordered_ids]
