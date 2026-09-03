"""
Keyword-search capability contract.

Defines the interface required for keyword/full-text retrieval.

Keyword indexing is derived from persisted DocumentChunk.text through
the database's configured full-text-search representation. Therefore
the keyword-store capability does not expose a separate persistence
operation.

Concrete keyword-store implementations provide keyword retrieval.
"""

from __future__ import annotations

from typing import Protocol

from rag.models import RetrievalResult


class KeywordStoreProtocol(Protocol):
    """
    Capability contract for keyword/full-text search retrieval.

    Keyword-search persistence is handled as part of DocumentChunk
    persistence. The keyword store is therefore responsible only for
    querying the persisted keyword-search representation.

    The protocol intentionally contains no knowledge of:

        - SQLAlchemy
        - PostgreSQL
        - PostgreSQL tsvector
        - BM25 implementation details
        - document ingestion
        - chunking
        - embedding generation
        - vector search
        - reranking
        - LLMs
    """

    async def query(
        self,
        *,
        query: str,
        top_k: int,
        allowed_source_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        """
        Retrieve keyword-search candidates.

        Args:
            query:
                User keyword/full-text search query.

            top_k:
                Maximum number of candidates to return.

            allowed_source_ids:
                Optional set of source identifiers restricting the
                retrieval scope.

        Returns:
            Keyword-search retrieval results.

        Raises:
            RAGError:
                If keyword retrieval fails.
        """

        ...
