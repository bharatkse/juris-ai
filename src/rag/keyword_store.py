"""
Keyword search over document_chunks.

Thin adapter over DocumentChunkRepository.keyword_search — see
pgvector_store.py for why this delegates to a repository rather than
running its own SQL.
"""

from __future__ import annotations

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.document_chunk import (
    DocumentChunkRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from rag.indexer import Chunk

log = get_logger(__name__)


class KeywordStore:
    """
    Postgres full-text search over the document_chunks table.
    """

    def __init__(self) -> None:
        self._session_factory = session_factory

    async def search(
        self,
        *,
        query: str,
        top_k: int,
        allowed_document_ids: set[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        async with self._session_factory() as session:
            repository = DocumentChunkRepository(session=session)
            results = await repository.keyword_search(
                query=query,
                top_k=top_k,
                allowed_document_ids=allowed_document_ids,
            )

        return [(Chunk.from_orm(row), score) for row, score in results]
