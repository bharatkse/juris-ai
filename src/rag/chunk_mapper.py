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

from collections.abc import Iterable, Iterator

from core.types import prefixed_id_field
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

        chunk_id = self._build_chunk_id()

        metadata: dict[str, str] = {
            "sequence": str(chunk.sequence),
            "source": chunk.source,
        }

        if chunk.title:
            metadata["title"] = chunk.title

        if chunk.mime_type:
            metadata["mime_type"] = chunk.mime_type

        # source.location is a natural fit for a future "url" key once a
        # URL-sourced DocumentSource implementation exists (see
        # DocumentSource's docstring) -- no such path exists today, so
        # no url key is set here.
        if source.location:
            metadata["source_id"] = source.location

        if source.id:
            metadata["knowledge_source_id"] = source.id

        return Chunk(
            id=chunk_id,
            source_id=source.id,
            text=chunk.text,
            metadata=metadata,
        )

    @staticmethod
    def _build_chunk_id() -> str:
        """
        Build a deterministic chunk identifier.

        The same source and sequence always produce the same ID,
        allowing downstream upsert operations to remain idempotent.
        """

        return prefixed_id_field("kchn")
