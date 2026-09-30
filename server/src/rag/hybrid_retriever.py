"""
Hybrid RAG retriever.

Combines vector and keyword/BM25 retrieval using Reciprocal Rank
Fusion (RRF), followed by cross-encoder reranking.

Retrieval flow:

    Query
      ↓
    EmbeddingProvider.embed_one()
      ↓
    ┌──────────────────────┐
    │                      │
    ↓                      ↓
    VectorStore.query()   KeywordStore.query()
    │                      │
    └──────────┬───────────┘
               ↓
        Reciprocal Rank Fusion
               ↓
        RerankerProtocol
               ↓
        RetrievalResult[]

One failed component degrades the search instead of failing it (review
R4): see HybridRetriever._search() for the modes.

This module belongs to the RAG retrieval/data plane.

It does NOT:

    - parse documents
    - sanitize documents
    - validate documents
    - chunk documents
    - generate document embeddings
    - persist chunks
    - upsert vectors
    - upsert keyword indexes
    - manage database transactions
    - call an LLM
    - execute agents
    - execute MCP tools
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Literal

from adapters.observability.logger import get_logger
from adapters.observability.metrics import metrics
from adapters.observability.tracing import span
from core.exceptions.rag import RAGError, RetrievalUnavailableError
from rag.models import RetrievalResult
from rag.protocols.embedding_provider import EmbeddingProviderProtocol
from rag.protocols.keyword import KeywordStoreProtocol
from rag.protocols.vector import VectorStoreProtocol
from rag.reranker import RerankerProtocol

logger = get_logger(__name__)

DEFAULT_FUSION_CANDIDATES = 20
DEFAULT_RRF_K = 60

# How a search ran: every component ("full"), or around one that failed
# (review R4). Recorded as a metric and a span attribute.
RetrievalMode = Literal["full", "no_rerank", "keyword_only", "vector_only"]


def _warn_degraded(message: str, error: BaseException) -> None:
    """Log a degraded search: the cause's type only, never the query."""

    logger.warning(message, extra={"error_type": type(error).__name__})


class HybridRetriever:
    """
    Hybrid vector + keyword/BM25 retriever.

    The retriever depends only on RAG capability protocols:

        EmbeddingProviderProtocol
        VectorStoreProtocol
        KeywordStoreProtocol
        RerankerProtocol

    Concrete infrastructure implementations are injected through
    the constructor.
    """

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProviderProtocol,
        vector_store: VectorStoreProtocol,
        keyword_store: KeywordStoreProtocol,
        reranker: RerankerProtocol,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> None:
        """
        Initialize the hybrid retriever.

        Args:
            embedding_provider:
                Query embedding capability.

            vector_store:
                Vector similarity retrieval capability.

            keyword_store:
                Keyword/BM25 retrieval capability.

            reranker:
                Final candidate reranking capability.

            rrf_k:
                RRF ranking constant.
        """

        if rrf_k <= 0:
            raise ValueError(
                "rrf_k must be greater than zero.",
            )

        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._keyword_store = keyword_store
        self._reranker = reranker
        self._rrf_k = rrf_k

    async def retrieve(
        self,
        *,
        query: str,
        top_k: int,
        fusion_candidates: int = DEFAULT_FUSION_CANDIDATES,
    ) -> list[RetrievalResult]:
        """
        Retrieve relevant chunks using hybrid vector and keyword
        retrieval.

        The query is embedded once. Vector and keyword retrieval are
        then executed concurrently.

        Args:
            query:
                User retrieval query.

            top_k:
                Maximum number of final results.

            fusion_candidates:
                Number of candidates requested from each retrieval
                strategy before fusion.

        Returns:
            Final reranked retrieval results.

        Raises:
            RetrievalUnavailableError:
                If no search could run (see _search()): one failed
                component degrades the search instead.
            RAGError:
                If fusion itself fails.
        """

        if not query or not query.strip():
            return []

        if top_k <= 0:
            return []

        if fusion_candidates <= 0:
            return []

        with span(
            "rag.hybrid_retrieve",
            attributes={"retrieval.top_k": top_k},
        ) as current_span:
            try:
                results, mode = await self._search(
                    query=query,
                    top_k=top_k,
                    fusion_candidates=fusion_candidates,
                )

            except RetrievalUnavailableError:
                current_span.set_attribute("retrieval.mode", "unavailable")
                metrics.record_retrieval(mode="unavailable")
                logger.error(
                    "Hybrid retrieval unavailable: no search could run.",
                    extra={"top_k": top_k},
                )
                raise

            except (RAGError, asyncio.CancelledError):
                raise

            except Exception as exc:
                logger.exception(
                    "Unexpected hybrid RAG retrieval failure.",
                    extra={
                        "top_k": top_k,
                        "fusion_candidates": fusion_candidates,
                    },
                )

                raise RAGError(
                    message="Hybrid RAG retrieval failed.",
                ) from exc

            current_span.set_attribute("retrieval.mode", mode)
            metrics.record_retrieval(mode=mode)

            return results

    async def _search(
        self,
        *,
        query: str,
        top_k: int,
        fusion_candidates: int,
    ) -> tuple[list[RetrievalResult], RetrievalMode]:
        """
        The search, degraded around one failed component (review R4):

        - embeddings or vector store down: keyword-only, reranked;
        - keyword store down: vector-only, reranked;
        - reranker down: the fused (RRF) order, its scores rescaled to
          [0, 1] like the reranker's, since they reach the agent's prompt
          as "relevance".

        Two failures at once (or no store answering) raise
        RetrievalUnavailableError. Each failure is logged as a warning
        naming the component and the error type, never the query.
        Cancellation always propagates.
        """

        vector_results: list[RetrievalResult] = []
        keyword_results: list[RetrievalResult] = []
        failed: list[str] = []

        query_vector: list[float] | None = None

        try:
            query_vector = await self._embedding_provider.embed_one(
                text=query,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            _warn_degraded("Query embedding failed; searching by keyword only.", exc)
            failed.append("embedding")

        if query_vector is None:
            keyword_outcome: list[RetrievalResult] | BaseException
            try:
                keyword_outcome = await self._keyword_store.query(
                    query=query,
                    top_k=fusion_candidates,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                keyword_outcome = exc
            vector_outcome: list[RetrievalResult] | BaseException = []
        else:
            vector_outcome, keyword_outcome = await asyncio.gather(
                self._vector_store.query(
                    vector=query_vector,
                    top_k=fusion_candidates,
                    embedding_model=self._embedding_provider.metadata.model_name,
                ),
                self._keyword_store.query(query=query, top_k=fusion_candidates),
                return_exceptions=True,
            )

        for outcome in (vector_outcome, keyword_outcome):
            if isinstance(outcome, asyncio.CancelledError):
                raise outcome

        if isinstance(vector_outcome, BaseException):
            _warn_degraded("Vector search failed; searching by keyword only.", vector_outcome)
            failed.append("vector")
        else:
            vector_results = list(vector_outcome)

        if isinstance(keyword_outcome, BaseException):
            _warn_degraded("Keyword search failed; searching by vector only.", keyword_outcome)
            failed.append("keyword")
        else:
            keyword_results = list(keyword_outcome)

        semantic_down = "embedding" in failed or "vector" in failed

        if semantic_down and "keyword" in failed:
            raise RetrievalUnavailableError(
                message="No retrieval store could be searched.",
            )

        mode: RetrievalMode = (
            "keyword_only" if semantic_down else "vector_only" if "keyword" in failed else "full"
        )

        ranked_lists = [results for results in (vector_results, keyword_results) if results]
        fused = self._rrf_scored(ranked_lists=ranked_lists)

        if not fused:
            logger.debug(
                "Hybrid retrieval returned no candidates.",
                extra={
                    "top_k": top_k,
                    "fusion_candidates": fusion_candidates,
                    "mode": mode,
                },
            )
            return [], mode

        rerank_candidates = [result for result, _ in fused[:fusion_candidates]]

        try:
            reranked_results = await self._reranker.rerank(
                query=query,
                candidates=rerank_candidates,
                top_k=top_k,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if mode != "full":
                _warn_degraded("Reranking failed on an already degraded search.", exc)
                raise RetrievalUnavailableError(
                    message="Retrieval is degraded in two components.",
                ) from exc

            _warn_degraded("Reranking failed; using the fused order.", exc)
            return self._rescaled(fused=fused, lists=len(ranked_lists))[:top_k], "no_rerank"

        logger.debug(
            "Hybrid retrieval completed.",
            extra={
                "mode": mode,
                "vector_results": len(vector_results),
                "keyword_results": len(keyword_results),
                "fused_results": len(fused),
                "rerank_candidates": len(rerank_candidates),
                "final_results": len(reranked_results),
            },
        )

        return reranked_results, mode

    def _rescaled(
        self,
        *,
        fused: list[tuple[RetrievalResult, float]],
        lists: int,
    ) -> list[RetrievalResult]:
        """
        Fused results with their RRF scores divided by the highest score
        possible (first in every list), so they fall in [0, 1] like the
        reranker's instead of keeping a store's own (cosine, ts_rank) scale.
        """

        best_possible = lists / (self._rrf_k + 1)

        return [result.with_score(min(score / best_possible, 1.0)) for result, score in fused]

    def _reciprocal_rank_fusion(
        self,
        *,
        ranked_lists: Sequence[Sequence[RetrievalResult]],
    ) -> list[RetrievalResult]:
        """
        Fuse ranked retrieval results using Reciprocal Rank Fusion.

        Formula:

            RRF score = Σ 1 / (rrf_k + rank)

        RRF is used only to determine candidate ordering.

        The original RetrievalResult objects are preserved.
        """

        return [result for result, _ in self._rrf_scored(ranked_lists=ranked_lists)]

    def _rrf_scored(
        self,
        *,
        ranked_lists: Sequence[Sequence[RetrievalResult]],
    ) -> list[tuple[RetrievalResult, float]]:
        """
        The fused results, best first, each with its RRF score.
        """

        scores: dict[str, float] = {}
        results_by_chunk_id: dict[str, RetrievalResult] = {}

        for ranked_results in ranked_lists:
            for rank, result in enumerate(
                ranked_results,
                start=1,
            ):
                chunk_id = str(result.chunk.id)

                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (self._rrf_k + rank)

                existing = results_by_chunk_id.get(
                    chunk_id,
                )

                if existing is None:
                    results_by_chunk_id[chunk_id] = result
                    continue

                results_by_chunk_id[chunk_id] = self._merge_results(
                    existing,
                    result,
                )

        ordered_chunk_ids = sorted(
            scores,
            key=lambda chunk_id: scores[chunk_id],
            reverse=True,
        )

        return [(results_by_chunk_id[chunk_id], scores[chunk_id]) for chunk_id in ordered_chunk_ids]

    @staticmethod
    def _merge_results(
        first: RetrievalResult,
        second: RetrievalResult,
    ) -> RetrievalResult:
        """
        Merge retrieval results representing the same chunk.

        Embedding representations are deduplicated by:

            model_name + dimension

        The original chunk is preserved and the higher retrieval score
        is retained.
        """

        embeddings = {
            (
                embedding.model_name,
                embedding.dimension,
            ): embedding
            for embedding in first.embeddings
        }

        for embedding in second.embeddings:
            embeddings.setdefault(
                (
                    embedding.model_name,
                    embedding.dimension,
                ),
                embedding,
            )

        return RetrievalResult(
            chunk=first.chunk,
            score=max(
                first.score,
                second.score,
            ),
            embeddings=list(
                embeddings.values(),
            ),
        )
