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

from adapters.observability.logger import get_logger
from core.exceptions.rag import RAGError
from rag.models import RetrievalResult
from rag.protocols.embedding_provider import EmbeddingProviderProtocol
from rag.protocols.keyword import KeywordStoreProtocol
from rag.protocols.vector import VectorStoreProtocol
from rag.reranker import RerankerProtocol

logger = get_logger(__name__)

DEFAULT_FUSION_CANDIDATES = 20
DEFAULT_RRF_K = 60


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
        allowed_source_ids: set[str] | None = None,
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

            allowed_source_ids:
                Optional source identifiers restricting retrieval.

            fusion_candidates:
                Number of candidates requested from each retrieval
                strategy before fusion.

        Returns:
            Final reranked retrieval results.

        Raises:
            RAGError:
                If retrieval or fusion fails.
        """

        if not query or not query.strip():
            return []

        if top_k <= 0:
            return []

        if fusion_candidates <= 0:
            return []

        if fusion_candidates <= 0:
            return []

        if allowed_source_ids is not None and not allowed_source_ids:
            return []

        try:
            query_vector = await self._embedding_provider.embed_one(
                text=query,
            )

            embedding_metadata = self._embedding_provider.metadata

            vector_results, keyword_results = await asyncio.gather(
                self._vector_store.query(
                    vector=query_vector,
                    top_k=fusion_candidates,
                    embedding_model=embedding_metadata.model_name,
                    allowed_source_ids=allowed_source_ids,
                ),
                self._keyword_store.query(
                    query=query,
                    top_k=fusion_candidates,
                    allowed_source_ids=allowed_source_ids,
                ),
            )

            fused_results = self._reciprocal_rank_fusion(
                ranked_lists=(
                    vector_results,
                    keyword_results,
                ),
            )

            if not fused_results:
                logger.debug(
                    "Hybrid retrieval returned no candidates.",
                    extra={
                        "top_k": top_k,
                        "fusion_candidates": fusion_candidates,
                    },
                )
                return []

            rerank_candidates = fused_results[:fusion_candidates]

            reranked_results = await self._reranker.rerank(
                query=query,
                candidates=rerank_candidates,
                top_k=top_k,
            )

            logger.debug(
                "Hybrid retrieval completed.",
                extra={
                    "vector_results": len(vector_results),
                    "keyword_results": len(keyword_results),
                    "fused_results": len(fused_results),
                    "rerank_candidates": len(rerank_candidates),
                    "final_results": len(reranked_results),
                },
            )

            return reranked_results

        except RAGError:
            logger.exception(
                "Hybrid RAG retrieval failed.",
                extra={
                    "top_k": top_k,
                    "fusion_candidates": fusion_candidates,
                },
            )
            raise

        except asyncio.CancelledError:
            logger.warning(
                "Hybrid RAG retrieval cancelled.",
            )
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

        return [results_by_chunk_id[chunk_id] for chunk_id in ordered_chunk_ids]

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
