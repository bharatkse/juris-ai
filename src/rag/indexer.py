"""
Vector indexer.

Handles ingestion: chunking documents and writing embeddings to the
vector store. Run offline/async (e.g. triggered on document upload,
or as a periodic batch job) — not on the request path of retrieve().

The vector store is pluggable behind the VectorStore protocol so the
current pgvector-backed implementation can be swapped for a dedicated
vector DB later without touching this class.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from adapters.observability.logger import get_logger
from core.exceptions.rag import RAGError
from rag.chunker import chunk_text
from rag.embeddings import EmbeddingProvider

log = get_logger(__name__)

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100


@dataclass(frozen=True, slots=True)
class Chunk:
    id: str
    document_id: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)
    # Recorded so a later embedding-model change is detectable rather
    # than silently mixing incompatible vector spaces in one table.
    embedding_model: str = ""

    @classmethod
    def from_orm(cls, row: object) -> Chunk:
        return cls(
            id=row.id,
            document_id=row.document_id,
            text=row.text,
            metadata=getattr(row, "chunk_metadata", None) or {},
            embedding_model=getattr(row, "embedding_model", ""),
        )


class VectorStore(Protocol):
    """
    Minimal vector store contract. Implementations: pgvector-backed
    store (reusing existing Postgres), or a dedicated vector adapters.persistence.sqlalchemy
    """

    async def upsert(
        self,
        *,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None: ...

    async def query(
        self,
        *,
        vector: list[float],
        top_k: int,
        allowed_document_ids: set[str] | None = None,
        embedding_model: str | None = None,
    ) -> list[tuple[Chunk, float]]: ...

    async def delete_document(self, *, document_id: str) -> int: ...


class VectorIndexer:
    """
    Chunks documents and writes their embeddings to the vector store.
    """

    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        self._embeddings = embedding_provider
        self._store = vector_store
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def _build_chunks(
        self,
        *,
        document_id: str,
        text: str,
        metadata: dict[str, str] | None,
    ) -> list[Chunk]:
        pieces = chunk_text(
            text=text,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
        )

        return [
            Chunk(
                id=f"{document_id}:{index}",
                document_id=document_id,
                text=piece,
                metadata={**(metadata or {}), "chunk_index": str(index)},
                embedding_model=self._embeddings.model_name,
            )
            for index, piece in enumerate(pieces)
        ]

    async def index_document(
        self,
        *,
        document_id: str,
        text: str,
        metadata: dict[str, str] | None = None,
        replace_existing: bool = True,
    ) -> int:
        """
        Chunk and index a single document. Returns the number of
        chunks written.

        replace_existing: if True (default), any previously indexed
        chunks for this document_id are deleted first. This handles
        the update case correctly — without it, re-indexing an edited
        document leaves stale chunks from the old version alongside
        the new ones, and both get returned at query time.
        """

        if not text or not text.strip():
            log.warning("Empty text for document '%s' — nothing to index.", document_id)
            return 0

        if replace_existing:
            await self.remove_document(document_id=document_id)

        chunks = self._build_chunks(document_id=document_id, text=text, metadata=metadata)

        if not chunks:
            log.warning("No chunks produced for document '%s'.", document_id)
            return 0

        try:
            # Generate embeddings before modifying the store to avoid losing data on failure
            vectors = await self._embeddings.embed(texts=[c.text for c in chunks])
            await self._store.upsert(chunks=chunks, vectors=vectors)

        except RAGError:
            log.exception("Indexing failed for document '%s'.", document_id)
            raise

        log.info(
            "Indexed document '%s' into %d chunk(s) (model=%s).",
            document_id,
            len(chunks),
            self._embeddings.model_name,
        )

        return len(chunks)

    async def remove_document(self, *, document_id: str) -> int:
        """
        Delete all indexed chunks for a document. Call this when a
        document is deleted, or before re-indexing an edited one
        (see index_document's replace_existing).
        """

        try:
            deleted = await self._store.delete_document(document_id=document_id)

        except RAGError:
            log.exception("Failed to delete chunks for document '%s'.", document_id)
            raise

        if deleted:
            log.info("Deleted %d existing chunk(s) for document '%s'.", deleted, document_id)
        return deleted
