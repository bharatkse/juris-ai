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
from pathlib import PurePosixPath

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
            source_id=source.id,
            sequence=chunk.sequence,
        )

        # Human-readable filename with extension (e.g. "it_act_2000.pdf"),
        # kept distinct from source.id (the ksrc_ hash) -- see
        # Chunk.source's docstring for why the two must not be
        # conflated.
        filename = PurePosixPath(source.location).name if source.location else None

        metadata: dict[str, str] = {
            "sequence": str(chunk.sequence),
            "source": chunk.source,
        }

        if chunk.title:
            metadata["title"] = chunk.title

        if chunk.mime_type:
            metadata["mime_type"] = chunk.mime_type

        if source.id:
            metadata["knowledge_source_id"] = source.id

        if filename:
            metadata["source"] = filename

        return Chunk(
            id=chunk_id,
            source=filename,
            text=chunk.text,
            metadata=metadata,
        )

    @staticmethod
    def _build_chunk_id(*, source_id: str, sequence: int) -> str:
        """
        Build a deterministic chunk identifier.

        The same source and sequence always produce the same ID,
        allowing downstream upsert operations to remain idempotent.

        Previously this returned prefixed_id_field("kchn") -- a fresh
        random UUID on every call, ignoring source/sequence entirely.
        That contradicted this docstring and made re-ingestion of the
        same source non-idempotent: RAGIndexPersistenceService.persist()
        keys its create-vs-update decision on this ID via
        chunk_repository.get_by_id(), so a random ID never matches an
        existing row and every re-run silently inserted a full
        duplicate set of chunks/embeddings under the same
        knowledge_source_id instead of replacing them.
        """

        digest = hashlib.sha256(
            f"{source_id}:{sequence}".encode(),
        ).hexdigest()

        return f"kchn_{digest[:32]}"
