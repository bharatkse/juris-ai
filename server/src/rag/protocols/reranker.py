"""
Reranker capability contract.

Defines the interface required by the RAG retrieval layer for
second-stage candidate reranking.

Concrete implementations, such as CrossEncoderReranker, implement
this protocol.
"""

from __future__ import annotations

from typing import Protocol

from rag.models import RetrievalResult


class RerankerProtocol(Protocol):
    """
    Capability contract for RAG candidate reranking.
    """

    async def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        """
        Rerank retrieval candidates for the supplied query.

        Args:
            query:
                User retrieval query.

            candidates:
                Candidates produced by vector/keyword retrieval and
                hybrid fusion.

            top_k:
                Maximum number of reranked results to return.

        Returns:
            Reranked RetrievalResult objects ordered by relevance.
        """

        ...
