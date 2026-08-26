"""
DocumentChunk repository.

Owns all persistence for RAG chunks — vector upsert, vector search,
keyword (full-text) search, and deletion. Previously this logic lived
directly inside PgVectorStore/KeywordStore as hand-written raw SQL
(text()); moved here to match how the rest of the project accesses
the database (DocumentRepository, etc. all own their table's queries
as a repository, not embedded in a client/service class).

PgVectorStore and KeywordStore (rag/pgvector_store.py,
rag/keyword_store.py) now become thin adapters satisfying the
VectorStore protocol expected by VectorIndexer/HybridRetriever, and
delegate the actual query work to this repository.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from src.core.exceptions.rag import VectorStoreError
from src.core.logger import get_logger
from src.db.models.document_chunk import DocumentChunk

log = get_logger(__name__)


class DocumentChunkRepository:
    """
    Repository for the document_chunks table.
    """

    def __init__(self, *, session: AsyncSession) -> None:
        self._session = session

    async def upsert_many(
        self,
        *,
        rows: list[dict],
    ) -> None:
        """
        rows: list of dicts with keys id, document_id, text,
        chunk_metadata, embedding_model, embedding.
        """

        if not rows:
            return

        try:
            for row in rows:
                stmt = pg_insert(DocumentChunk).values(**row)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[DocumentChunk.id],
                    set_={
                        "text": stmt.excluded.text,
                        "chunk_metadata": stmt.excluded.chunk_metadata,
                        "embedding_model": stmt.excluded.embedding_model,
                        "embedding": stmt.excluded.embedding,
                    },
                )
                await self._session.execute(stmt)

            await self._session.commit()

        except SQLAlchemyError as exc:
            await self._session.rollback()
            log.exception("Failed to upsert %d chunk row(s).", len(rows))
            raise VectorStoreError(message="Failed to write chunks to vector store.") from exc

        log.debug("Upserted %d chunk row(s).", len(rows))

    async def vector_search(
        self,
        *,
        vector: list[float],
        top_k: int,
        allowed_document_ids: set[str] | None = None,
        embedding_model: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        embedding_model: when provided, restricts the search to
        chunks embedded with that exact model. Cosine distance is
        only meaningful between vectors from the same embedding
        space — comparing a query vector against chunks embedded by a
        different (e.g. previously swapped-out) model produces
        numerically valid but semantically meaningless scores with no
        error to signal it. This filter is what makes an embedding
        model migration safe: old and new vectors coexist in the same
        table without silently cross-contaminating similarity scores.
        """

        if allowed_document_ids is not None and not allowed_document_ids:
            return []

        try:
            distance = DocumentChunk.embedding.cosine_distance(vector)

            stmt = select(DocumentChunk, (1 - distance).label("score")).order_by(distance)

            if allowed_document_ids is not None:
                stmt = stmt.where(DocumentChunk.document_id.in_(allowed_document_ids))

            if embedding_model is not None:
                stmt = stmt.where(DocumentChunk.embedding_model == embedding_model)

            stmt = stmt.limit(top_k)

            result = await self._session.execute(stmt)
            rows = result.all()

        except SQLAlchemyError as exc:
            log.exception("Vector search failed.")
            raise VectorStoreError(message="Vector search failed.") from exc

        return [(row.DocumentChunk, float(row.score)) for row in rows]

    async def keyword_search(
        self,
        *,
        query: str,
        top_k: int,
        allowed_document_ids: set[str] | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        if allowed_document_ids is not None and not allowed_document_ids:
            return []

        try:
            tsquery = func.plainto_tsquery("english", query)
            rank = func.ts_rank(DocumentChunk.text_tsv, tsquery).label("score")

            stmt = (
                select(DocumentChunk, rank)
                .where(DocumentChunk.text_tsv.op("@@")(tsquery))
                .order_by(rank.desc())
            )

            if allowed_document_ids is not None:
                stmt = stmt.where(DocumentChunk.document_id.in_(allowed_document_ids))

            stmt = stmt.limit(top_k)

            result = await self._session.execute(stmt)
            rows = result.all()

        except SQLAlchemyError as exc:
            log.exception("Keyword search failed for query=%r.", query)
            raise VectorStoreError(message="Keyword search failed.") from exc

        return [(row.DocumentChunk, float(row.score)) for row in rows]

    async def delete_by_document_id(self, *, document_id: str) -> int:
        try:
            result = await self._session.execute(
                select(DocumentChunk).where(DocumentChunk.document_id == document_id)
            )
            chunks = result.scalars().all()

            for chunk in chunks:
                await self._session.delete(chunk)

            await self._session.commit()

        except SQLAlchemyError as exc:
            await self._session.rollback()
            log.exception("Failed to delete chunks for document '%s'.", document_id)
            raise VectorStoreError(
                message=f"Failed to delete chunks for document '{document_id}'."
            ) from exc

        return len(chunks)
