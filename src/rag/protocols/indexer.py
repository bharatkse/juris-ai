"""
RAG indexing capability contract.

Defines the application-facing capability required to index
RAG-domain chunks.

Concrete indexing implementations provide embedding generation
and vector persistence through the configured capabilities.

Keyword/BM25 retrieval is intentionally outside this indexing
capability. PostgreSQL full-text/BM25 indexing is derived from
the persisted DocumentChunk representation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from rag.models import Chunk, IndexedRepresentation


class RAGIndexerProtocol(Protocol):
    """
    Capability contract for RAG indexing.

    Implementations are responsible for:

        - generating embeddings for RAG chunks
        - persisting vector representations
        - returning indexing statistics

    Keyword/BM25 retrieval is not part of this capability.

    The protocol intentionally contains no knowledge of:

        - document parsing
        - ingestion modes
        - keyword retrieval
        - vector retrieval
        - reranking
        - LLMs
        - agents
        - persistence implementations
        - database technology
    """

    async def index(
        self,
        *,
        source_id: str,
        chunks: Iterable[Chunk],
    ) -> IndexedRepresentation:
        """
        Incrementally index a stream of RAG chunks.

        Args:
            source_id:
                Stable source identifier.

            chunks:
                Lazy iterable of RAG-domain chunks.

        Returns:
            Statistics describing the completed indexing operation.
        """

        ...
