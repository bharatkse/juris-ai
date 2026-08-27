"""
pgvector-backed vector store.

Thin adapter satisfying the VectorStore protocol expected by
VectorIndexer/HybridRetriever (rag/indexer.py). Actual persistence
lives in repositories/document_chunk.py, matching how every other
table in this project is accessed — a session-scoped repository, not
raw SQL embedded in a client class.
"""

from __future__ import annotations

from src.core.logger import get_logger
from src.db.session import session_factory
from src.rag.indexer import Chunk
from src.repositories.document_chunk import DocumentChunkRepository

log = get_logger(__name__)


class PgVectorStore:
    """
    Vector store backed by Postgres + pgvector.
    """

    def __init__(self) -> None:
        # session_factory is the module-level async_sessionmaker
        # instance from src/db/session.py — callable per-use, not
        # called once and cached. (Previous version called it once at
        # construction and stored the result, which only worked by
        # accident depending on what that call happened to return.)
        self._session_factory = session_factory

    async def upsert(
        self,
        *,
        chunks: list[Chunk],
        vectors: list[list[float]],
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length.")

        rows = [
            {
                "id": chunk.id,
                "document_id": chunk.document_id,
                "text": chunk.text,
                "chunk_metadata": chunk.metadata,
                "embedding_model": chunk.embedding_model,
                "embedding": vector,
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        async with self._session_factory() as session:
            repository = DocumentChunkRepository(session=session)
            await repository.upsert_many(rows=rows)

    async def query(
        self,
        *,
        vector: list[float],
        top_k: int,
        allowed_document_ids: set[str] | None = None,
        embedding_model: str | None = None,
    ) -> list[tuple[Chunk, float]]:
        async with self._session_factory() as session:
            repository = DocumentChunkRepository(session=session)
            results = await repository.vector_search(
                vector=vector,
                top_k=top_k,
                allowed_document_ids=allowed_document_ids,
                embedding_model=embedding_model,
            )

        return [(Chunk.from_orm(row), score) for row, score in results]

    async def delete_document(self, *, document_id: str) -> int:
        async with self._session_factory() as session:
            repository = DocumentChunkRepository(session=session)
            return await repository.delete_by_document_id(document_id=document_id)
