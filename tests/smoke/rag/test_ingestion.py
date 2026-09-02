from __future__ import annotations

import pytest
from sqlalchemy import select

from adapters.persistence.sqlalchemy.models.document_chunk import DocumentChunk
from adapters.persistence.sqlalchemy.models.document_chunk_embedding import (
    DocumentChunkEmbedding,
)
from adapters.persistence.sqlalchemy.session import session_factory

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestRAGIngestion:
    async def test_legal_corpus_is_persisted(
        self,
        rag_smoke_environment,
    ) -> None:
        source_ids = rag_smoke_environment.source_ids
        results = rag_smoke_environment.results

        # ---------------------------------------------------------
        # Verify that the smoke environment discovered multiple
        # legal documents.
        # ---------------------------------------------------------

        assert source_ids, "No legal sources were discovered."

        assert len(source_ids) >= 2, (
            "Multi-document RAG smoke tests require at least " "two legal source documents."
        )

        assert len(source_ids) == len(results), (
            "The number of indexed results does not match "
            "the number of discovered source documents."
        )

        assert len(source_ids) == len(
            set(source_ids)
        ), "Duplicate legal source IDs were discovered."

        async with session_factory() as session:
            for source_id, result in zip(source_ids, results, strict=False):
                # -------------------------------------------------
                # Verify indexing result returned by
                # DocumentIndexingService.
                # -------------------------------------------------

                assert result.chunk_count > 0, (
                    "RAG indexing completed but produced zero chunks " f"for source {source_id!r}."
                )

                assert result.embedding_model, (
                    "RAG indexing completed without an embedding model "
                    f"for source {source_id!r}."
                )

                assert result.embedding_dimension > 0, (
                    "RAG indexing completed with an invalid embedding "
                    f"dimension for source {source_id!r}."
                )

                # -------------------------------------------------
                # Verify persisted chunks for THIS source only.
                #
                # source_id is stored as provenance metadata.
                #
                # document_id is an optional FK to documents.id and
                # remains NULL because offline ingestion does not
                # create a Document entity.
                # -------------------------------------------------

                chunks_result = await session.execute(
                    select(DocumentChunk).where(
                        DocumentChunk.chunk_metadata["source_id"].as_string() == source_id
                    )
                )

                chunks = chunks_result.scalars().all()

                assert chunks, (
                    "Offline ingestion completed but no DocumentChunk "
                    f"records were persisted for source {source_id!r}."
                )

                assert len(chunks) == result.chunk_count, (
                    f"Expected {result.chunk_count} persisted chunks for "
                    f"source {source_id!r}, but found {len(chunks)}."
                )

                chunk_ids = [chunk.id for chunk in chunks]

                assert len(chunk_ids) == len(set(chunk_ids)), (
                    "Duplicate DocumentChunk IDs were persisted " f"for source {source_id!r}."
                )

                for chunk in chunks:
                    assert chunk.id

                    # Offline ingestion does not create a Document row.
                    assert chunk.document_id is None

                    assert chunk.text.strip()

                    assert chunk.chunk_metadata is not None

                    assert chunk.chunk_metadata["source_id"] == source_id

                    assert chunk.chunk_metadata["source"] == "file"

                    assert chunk.chunk_metadata["mime_type"] == "application/pdf"

                    assert chunk.text_tsv is not None

                # -------------------------------------------------
                # Verify persisted embeddings for THIS source.
                # -------------------------------------------------

                embeddings_result = await session.execute(
                    select(DocumentChunkEmbedding).where(
                        DocumentChunkEmbedding.chunk_id.in_(chunk_ids),
                    )
                )

                embeddings = embeddings_result.scalars().all()

                assert embeddings, (
                    "Offline ingestion completed but no "
                    "DocumentChunkEmbedding records were persisted "
                    f"for source {source_id!r}."
                )

                assert len(embeddings) == result.chunk_count, (
                    f"Expected {result.chunk_count} persisted embeddings "
                    f"for source {source_id!r}, but found {len(embeddings)}."
                )

                # -------------------------------------------------
                # Verify embedding identity and one-to-one coverage.
                # -------------------------------------------------

                embedding_ids = [embedding.id for embedding in embeddings]

                assert len(embedding_ids) == len(set(embedding_ids)), (
                    "Duplicate DocumentChunkEmbedding IDs were "
                    f"persisted for source {source_id!r}."
                )

                embedding_chunk_ids = [embedding.chunk_id for embedding in embeddings]

                assert len(embedding_chunk_ids) == len(set(embedding_chunk_ids)), (
                    "Multiple embeddings were persisted for the same "
                    f"chunk in source {source_id!r}."
                )

                assert set(embedding_chunk_ids) == set(chunk_ids), (
                    "Persisted embeddings do not provide exactly one "
                    "embedding for every persisted smoke-test chunk "
                    f"for source {source_id!r}."
                )

                # -------------------------------------------------
                # Verify embedding representation.
                # -------------------------------------------------

                for embedding in embeddings:
                    assert embedding.chunk_id in chunk_ids

                    assert embedding.embedding_model == result.embedding_model

                    assert embedding.embedding_dimension == result.embedding_dimension

                    assert embedding.embedding is not None

                    assert len(embedding.embedding) == embedding.embedding_dimension
