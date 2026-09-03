from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.document_chunk import (
    DocumentChunk,
)
from adapters.persistence.sqlalchemy.models.document_chunk_embedding import (
    DocumentChunkEmbedding,
)
from adapters.persistence.sqlalchemy.repositories.rag_retrieval import (
    RAGRetrievalRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from application.services.document_indexing import DocumentIndexingService
from application.services.offline_ingestion import OfflineIngestionService
from rag.chunk_mapper import ChunkMapper
from rag.embeddings import SentenceTransformerEmbeddingProvider
from rag.hybrid_retriever import HybridRetriever
from rag.indexer import RAGIndexer
from rag.ingestion.models import DocumentSource
from rag.keyword_store import PostgresKeywordStore
from rag.models import IndexedRepresentation
from rag.pgvector_store import PgVectorStore
from rag.reranker import CrossEncoderReranker

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DATASETS_DIR = PROJECT_ROOT / "tests/datasets/rag/raw_datasets"


@dataclass(frozen=True)
class RAGSmokeEnvironment:
    """
    Shared RAG smoke-test state.

    The environment is created once per pytest session and reused by
    every RAG smoke-test module.
    """

    source_paths: tuple[Path, ...]
    source_ids: tuple[str, ...]
    sources: tuple[DocumentSource, ...]

    indexing_service: DocumentIndexingService

    embedding_provider: SentenceTransformerEmbeddingProvider
    retrieval_vector_store: PgVectorStore
    keyword_store: PostgresKeywordStore
    reranker: CrossEncoderReranker
    hybrid_retriever: HybridRetriever

    results: tuple[IndexedRepresentation, ...]

    retrieval_repository: RAGRetrievalRepository
    session: AsyncSession


def _find_legal_documents() -> tuple[Path, ...]:
    """
    Find all supported legal documents under raw_datasets/.
    """

    supported_extensions = {
        ".pdf",
        ".docx",
        ".txt",
        ".md",
        ".html",
        ".htm",
    }

    candidates = tuple(
        sorted(
            path
            for path in RAW_DATASETS_DIR.rglob("*")
            if path.is_file() and path.suffix.lower() in supported_extensions
        )
    )

    if not candidates:
        pytest.fail(
            "No legal source documents found under raw_datasets/. "
            "Add at least one legal document before running "
            "the RAG smoke tests."
        )

    return candidates


def _build_indexing_service() -> DocumentIndexingService:
    """
    Build the existing production ingestion/indexing pipeline.

    The indexing vector store does not require retrieval repository
    configuration because it is only used for persistence.
    """

    embedding_provider = SentenceTransformerEmbeddingProvider()

    vector_store = PgVectorStore()

    indexer = RAGIndexer(
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )

    ingestion_service = OfflineIngestionService()

    return DocumentIndexingService(
        ingestion_service=ingestion_service,
        chunk_mapper=ChunkMapper(),
        indexer=indexer,
    )


@pytest_asyncio.fixture(
    scope="session",
    loop_scope="session",
)
async def rag_smoke_environment() -> RAGSmokeEnvironment:
    """
    Create the shared RAG smoke-test environment.

    All legal documents under raw_datasets/ are indexed exactly once
    for the pytest session.

    The retrieval repository and its SQLAlchemy session remain alive
    for the lifetime of the smoke-test environment.
    """

    source_paths = _find_legal_documents()

    source_ids = tuple(str(source_path.resolve()) for source_path in source_paths)

    sources = tuple(
        DocumentSource(
            id=source_id,
            location=source_id,
        )
        for source_id in source_ids
    )

    indexing_service = _build_indexing_service()

    results: list[IndexedRepresentation] = []

    for source in sources:
        result = await indexing_service.index(
            source=source,
        )

        assert result.chunk_count > 0, (
            "RAG ingestion completed but produced zero chunks " f"for source: {source.id}"
        )

        assert result.embedding_model, (
            "RAG ingestion completed without an embedding model " f"for source: {source.id}"
        )

        assert result.embedding_dimension > 0, (
            "RAG ingestion completed with an invalid embedding "
            f"dimension for source: {source.id}"
        )

        results.append(result)

    indexed_results = tuple(results)

    session = session_factory()

    retrieval_repository = RAGRetrievalRepository(
        session=session,
    )

    retrieval_vector_store = PgVectorStore()

    embedding_provider = SentenceTransformerEmbeddingProvider()

    keyword_store = PostgresKeywordStore()

    reranker = CrossEncoderReranker()

    hybrid_retriever = HybridRetriever(
        embedding_provider=embedding_provider,
        vector_store=retrieval_vector_store,
        keyword_store=keyword_store,
        reranker=reranker,
    )

    environment = RAGSmokeEnvironment(
        source_paths=source_paths,
        source_ids=source_ids,
        sources=sources,
        indexing_service=indexing_service,
        embedding_provider=embedding_provider,
        retrieval_vector_store=retrieval_vector_store,
        keyword_store=keyword_store,
        reranker=reranker,
        hybrid_retriever=hybrid_retriever,
        results=indexed_results,
        retrieval_repository=retrieval_repository,
        session=session,
    )

    try:
        yield environment

    finally:
        await session.close()

        await _cleanup_rag_smoke_data(
            source_ids=source_ids,
        )


async def _cleanup_rag_smoke_data(
    *,
    source_ids: tuple[str, ...],
) -> None:
    """
    Remove all RAG data created by the smoke-test ingestion.
    """

    source_ids = tuple(source_id for source_id in source_ids if source_id.strip())

    if not source_ids:
        return

    async with session_factory() as session:
        chunk_ids_result = await session.execute(
            select(DocumentChunk.id).where(
                DocumentChunk.chunk_metadata["source_id"]
                .as_string()
                .in_(
                    source_ids,
                ),
            )
        )

        chunk_ids = list(
            chunk_ids_result.scalars().all(),
        )

        if not chunk_ids:
            return

        await session.execute(
            delete(DocumentChunkEmbedding).where(
                DocumentChunkEmbedding.chunk_id.in_(chunk_ids),
            )
        )

        await session.execute(
            delete(DocumentChunk).where(
                DocumentChunk.id.in_(chunk_ids),
            )
        )

        await session.commit()
