"""
Chunk mapping boundary.

Maps ingestion-layer IngestionChunk objects into the RAG data-plane
Chunk representation consumed by indexing.

Flow:

    IngestionChunk
          ↓
      ChunkMapper
          ↓
    rag.models.Chunk

"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Iterator

from rag.ingestion.models import DocumentSource, IngestionChunk
from rag.models import Chunk


class ChunkMapper:
    """
    Converts ingestion chunks into RAG chunks.

    The mapper is stateless and streaming.
    """

    def map_stream(
        self,
        *,
        chunks: Iterable[IngestionChunk],
        source: DocumentSource,
    ) -> Iterator[Chunk]:
        """
        Lazily convert ingestion chunks into RAG chunks.

        Args:
            chunks:
                Lazy stream of ingestion-domain chunks.

            source:
                Stable RAG source identifier.

        Yields:
            RAG-domain Chunk objects.
        """

        if not source:
            raise ValueError(
                "source must not be empty.",
            )

        for chunk in chunks:
            yield self.map(
                chunk=chunk,
                source=source,
            )

    def map(
        self,
        *,
        chunk: IngestionChunk,
        source: DocumentSource,
    ) -> Chunk:
        """
        Convert one ingestion chunk into one RAG chunk.
        """

        if not chunk.text.strip():
            raise ValueError(
                "chunk.text must not be empty.",
            )

        chunk_id = self._build_chunk_id(
            source=source,
            sequence=chunk.sequence,
        )

        metadata: dict[str, str] = {
            "sequence": str(chunk.sequence),
            "source": chunk.source,
        }

        if chunk.mime_type:
            metadata["mime_type"] = chunk.mime_type

        if source.location:
            metadata["source_id"] = source.location

        return Chunk(
            id=chunk_id,
            source_id=source.id,
            text=chunk.text,
            metadata=metadata,
        )

    @staticmethod
    def _build_chunk_id(
        *,
        source: str,
        sequence: int,
    ) -> str:
        """
        Build a deterministic chunk identifier.

        The same source and sequence always produce the same ID,
        allowing downstream upsert operations to remain idempotent.
        """

        identity = f"{source}:{sequence}"

        return hashlib.sha256(
            identity.encode("utf-8"),
        ).hexdigest()
