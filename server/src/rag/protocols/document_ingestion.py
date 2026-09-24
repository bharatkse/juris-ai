"""
Document ingestion capability contract.

Defines the application-facing contract for document ingestion.

Concrete ingestion implementations may represent different ingestion
modes, such as:

    - local/offline document ingestion
    - online document ingestion
    - updated document ingestion
    - future remote or event-driven ingestion

The indexing layer depends on this protocol rather than on a specific
ingestion implementation.

The protocol produces ingestion-domain chunks. Conversion into the
RAG data-plane Chunk is handled separately by ChunkMapper.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from rag.ingestion.models import (
    DocumentSource,
    IngestionChunk,
)


class DocumentIngestionProtocol(Protocol):
    """
    Capability contract for document ingestion.

    Implementations are responsible for producing a lazy stream of
    IngestionChunk objects for a DocumentSource.

    The protocol intentionally contains no knowledge of:

        - RAG Chunk
        - embeddings
        - vector stores
        - keyword stores
        - retrieval
        - reranking
        - LLMs
        - agents
        - persistence
    """

    def ingest(
        self,
        *,
        source: DocumentSource,
    ) -> Iterator[IngestionChunk]:
        """
        Lazily ingest a document source.

        Args:
            source:
                Source descriptor identifying the document and its
                location.

        Returns:
            Lazy iterator of ingestion-domain chunks.
        """

        ...
