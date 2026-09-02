from __future__ import annotations

import pytest

from rag.embeddings import SentenceTransformerEmbeddingProvider

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestRAGVectorRetrieval:
    async def test_retrieves_relevant_legal_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that pgvector can retrieve relevant chunks from the
        multi-document legal corpus indexed by the session-scoped
        RAG fixture.
        """

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
            allowed_source_ids=None,
        )

        assert results
        assert len(results) <= 5

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()
            assert result.chunk.metadata["source_id"]
            assert result.score is not None
            assert result.embeddings

            assert result.embeddings[0].model_name == embedding_provider.metadata.model_name

            assert result.embeddings[0].dimension == embedding_provider.metadata.dimension

    async def test_vector_retrieval_respects_top_k(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that pgvector does not return more results than requested.
        """

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
            allowed_source_ids=None,
        )

        assert len(results) <= top_k

    async def test_vector_results_are_ranked_by_similarity(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that vector retrieval returns results in descending
        similarity order.
        """

        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="articles reserved for production under the Act",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=5,
            embedding_model=embedding_provider.metadata.model_name,
            allowed_source_ids=None,
        )

        assert results

        scores = [result.score for result in results]

        assert scores == sorted(
            scores,
            reverse=True,
        )

    async def test_vector_retrieval_returns_unique_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that the vector retrieval result set does not contain
        duplicate chunk IDs.
        """

        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="handlooms reservation production",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
            allowed_source_ids=None,
        )

        assert results

        chunk_ids = [result.chunk.id for result in results]

        assert len(chunk_ids) == len(set(chunk_ids))

    async def test_vector_retrieval_respects_first_source_filter(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that vector retrieval returns only chunks from the
        first indexed legal source.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_id = rag_smoke_environment.source_ids[0]

        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="handlooms reservation production",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
            metadata_filters={
                "source_id": source_id,
            },
        )

        assert results

        returned_source_ids = {result.chunk.metadata["source_id"] for result in results}

        assert returned_source_ids == {source_id}

    async def test_vector_retrieval_respects_second_source_filter(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that vector retrieval returns only chunks from the
        second indexed legal source.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_id = rag_smoke_environment.source_ids[1]

        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="electronic records electronic signatures",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
            metadata_filters={
                "source_id": source_id,
            },
        )

        assert results

        returned_source_ids = {result.chunk.metadata["source_id"] for result in results}

        assert returned_source_ids == {source_id}

    async def test_vector_retrieval_does_not_leak_between_sources(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that filtering for the second source prevents chunks
        from the first source from being returned.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_a = rag_smoke_environment.source_ids[0]
        source_b = rag_smoke_environment.source_ids[1]

        embedding_provider = SentenceTransformerEmbeddingProvider()
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="electronic records electronic signatures",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
            metadata_filters={
                "source_id": source_b,
            },
        )

        assert results

        returned_source_ids = {result.chunk.metadata["source_id"] for result in results}

        assert source_b in returned_source_ids
        assert source_a not in returned_source_ids

    async def test_vector_retrieval_without_source_filter_searches_indexed_corpus(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that vector retrieval can search the complete indexed
        corpus when no source restriction is provided.
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
            allowed_source_ids=None,
        )

        assert results

        returned_source_ids = {result.chunk.metadata["source_id"] for result in results}

        assert returned_source_ids

        assert returned_source_ids.issubset(set(rag_smoke_environment.source_ids))

    async def test_vector_retrieval_with_empty_source_filter_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that an explicitly empty source filter returns no
        vector retrieval results.
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
            allowed_source_ids=set(),
        )

        assert results == []
