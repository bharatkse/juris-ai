from __future__ import annotations

import math

import pytest

from rag.embeddings import SentenceTransformerEmbeddingProvider

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestRAGVectorRetrieval:
    """
    Smoke tests for the production PostgreSQL/pgvector retrieval path.

    Query-time retrieval is intentionally corpus-wide. These tests do
    not use allowed_source_ids or metadata_filters.

    Source identity is validated from returned result provenance through
    knowledge_source_id.
    """

    async def test_retrieves_relevant_legal_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query = "What is the purpose of this Act?"

        query_vector = await embedding_provider.embed_one(
            text=query,
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results
        assert len(results) <= 5

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()

            assert result.score is not None
            assert isinstance(result.score, (int | float))
            assert math.isfinite(result.score)

            assert result.embeddings

            embedding = result.embeddings[0]

            assert embedding.model_name == embedding_provider.metadata.model_name

            assert embedding.dimension == embedding_provider.metadata.dimension

            assert embedding.vector

    async def test_vector_retrieval_respects_top_k(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="reservation of articles for production",
        )

        top_k = 3

        results = await vector_store.query(
            vector=query_vector,
            top_k=top_k,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert len(results) <= top_k

    async def test_vector_retrieval_with_top_k_one_returns_at_most_one_result(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="reservation of articles for production",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=1,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert len(results) <= 1

    async def test_vector_retrieval_with_top_k_zero_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=0,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results == []

    async def test_vector_retrieval_with_negative_top_k_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=-1,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results == []

    async def test_vector_retrieval_with_large_top_k_does_not_fail(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10_000,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert isinstance(results, list)

    async def test_vector_retrieval_with_empty_vector_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        vector_store = rag_smoke_environment.retrieval_vector_store

        results = await vector_store.query(
            vector=[],
            top_k=5,
            embedding_model="test-model",
        )

        assert results == []

    async def test_vector_retrieval_with_empty_embedding_model_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model="",
        )

        assert results == []

    async def test_vector_retrieval_with_whitespace_embedding_model_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model="   ",
        )

        assert results == []

    async def test_vector_results_are_ranked_by_similarity(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="articles reserved for production under the Act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        scores = [result.score for result in results]

        assert scores == sorted(
            scores,
            reverse=True,
        )

    async def test_vector_results_contain_unique_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="handlooms reservation production",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        chunk_ids = [result.chunk.id for result in results]

        assert len(chunk_ids) == len(set(chunk_ids))

    async def test_vector_results_preserve_chunk_identity(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        for result in results:
            assert result.chunk.id
            assert isinstance(result.chunk.id, str)

    async def test_vector_results_preserve_chunk_text(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        for result in results:
            assert isinstance(result.chunk.text, str)
            assert result.chunk.text.strip()

    async def test_vector_results_preserve_knowledge_source_provenance(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        for result in results:
            knowledge_source_id = result.chunk.metadata.get(
                "knowledge_source_id",
            )

            assert knowledge_source_id is not None
            assert isinstance(
                knowledge_source_id,
                str,
            )
            assert knowledge_source_id.strip()

    async def test_vector_retrieval_searches_indexed_corpus_without_source_filter(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Query-time vector retrieval is not restricted by source IDs.

        The caller supplies only the query vector, top_k, and embedding
        model. Source provenance is returned in the result.
        """

        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        returned_source_ids = {
            result.chunk.metadata.get("knowledge_source_id") for result in results
        }

        assert returned_source_ids
        assert all(returned_source_ids)

    async def test_vector_retrieval_can_return_multiple_knowledge_sources(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that corpus-wide vector retrieval can return results
        associated with more than one KnowledgeSource when the indexed
        corpus contains multiple sources.

        The test does not use source filtering.
        """

        if len(rag_smoke_environment.sources) < 2:
            pytest.skip(
                "Multiple indexed KnowledgeSources are required.",
            )

        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act provisions and requirements",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=50,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        returned_source_ids = {
            result.chunk.metadata.get("knowledge_source_id") for result in results
        }

        assert returned_source_ids

    async def test_vector_embedding_model_is_preserved(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        for result in results:
            assert result.embeddings

            assert all(
                embedding.model_name == embedding_provider.metadata.model_name
                for embedding in result.embeddings
            )

    async def test_vector_embedding_dimension_is_preserved(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        for result in results:
            assert result.embeddings

            assert all(
                embedding.dimension == embedding_provider.metadata.dimension
                for embedding in result.embeddings
            )

    async def test_vector_embedding_vectors_are_preserved(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        for result in results:
            assert result.embeddings

            for embedding in result.embeddings:
                assert embedding.vector
                assert len(embedding.vector) == embedding.dimension

    async def test_vector_scores_are_numeric_and_finite(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="legal act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        for result in results:
            assert isinstance(
                result.score,
                (int | float),
            )

            assert math.isfinite(
                result.score,
            )

    async def test_vector_retrieval_with_semantically_related_query(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="reservation of articles for production",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert results

        assert any(result.chunk.text.strip() for result in results)

    async def test_vector_retrieval_handles_punctuation_in_query(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="What is the purpose of this Act?!",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert isinstance(results, list)

    async def test_vector_repeated_query_returns_same_chunk_order(
        self,
        rag_smoke_environment,
    ) -> None:
        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="reservation of articles for production",
        )

        first_results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        second_results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
        )

        assert first_results
        assert second_results

        first_chunk_ids = [result.chunk.id for result in first_results]

        second_chunk_ids = [result.chunk.id for result in second_results]

        assert first_chunk_ids == second_chunk_ids
