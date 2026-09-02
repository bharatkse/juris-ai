from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestRAGSourceFiltering:
    async def test_vector_retrieval_returns_only_first_allowed_source(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify vector retrieval returns only chunks from the first
        indexed legal source.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_id = rag_smoke_environment.source_ids[0]

        embedding_provider = rag_smoke_environment.embedding_provider
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="reservation of articles for production",
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

    async def test_vector_retrieval_returns_only_second_allowed_source(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify vector retrieval returns only chunks from the second
        indexed legal source.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_id = rag_smoke_environment.source_ids[1]

        embedding_provider = rag_smoke_environment.embedding_provider
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="electronic records and electronic signatures",
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

    async def test_keyword_retrieval_returns_only_first_allowed_source(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify keyword retrieval returns only chunks from the first
        indexed legal source.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_id = rag_smoke_environment.source_ids[0]

        repository = rag_smoke_environment.retrieval_repository

        results = await repository.keyword_search(
            query="electronic records electronic signatures",
            top_k=10,
            metadata_filters={
                "source_id": source_id,
            },
        )

        assert results

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _score in results}

        assert returned_source_ids == {source_id}

    async def test_keyword_retrieval_returns_only_second_allowed_source(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify keyword retrieval returns only chunks from the second
        indexed legal source.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_id = rag_smoke_environment.source_ids[1]

        repository = rag_smoke_environment.retrieval_repository

        results = await repository.keyword_search(
            query="handlooms reservation production",
            top_k=10,
            metadata_filters={
                "source_id": source_id,
            },
        )

        assert results

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _score in results}

        assert returned_source_ids == {source_id}

    async def test_vector_retrieval_does_not_leak_first_source_into_second(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify vector retrieval does not return chunks from the first
        source when retrieval is restricted to the second source.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_a = rag_smoke_environment.source_ids[0]
        source_b = rag_smoke_environment.source_ids[1]

        embedding_provider = rag_smoke_environment.embedding_provider
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="electronic records and electronic signatures",
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

    async def test_keyword_retrieval_does_not_leak_first_source_into_second(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify keyword retrieval does not return chunks from the first
        source when retrieval is restricted to the second source.
        """

        assert len(rag_smoke_environment.source_ids) >= 2

        source_a = rag_smoke_environment.source_ids[0]
        source_b = rag_smoke_environment.source_ids[1]

        repository = rag_smoke_environment.retrieval_repository

        results = await repository.keyword_search(
            query="handlooms reservation production",
            top_k=10,
            metadata_filters={
                "source_id": source_b,
            },
        )

        assert results

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _score in results}

        assert source_b in returned_source_ids
        assert source_a not in returned_source_ids

    async def test_vector_retrieval_with_empty_source_set_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify an explicitly empty vector source filter returns
        no results.
        """

        embedding_provider = rag_smoke_environment.embedding_provider
        vector_store = rag_smoke_environment.retrieval_vector_store

        query_vector = await embedding_provider.embed_one(
            text="reservation of articles for production",
        )

        results = await vector_store.query(
            vector=query_vector,
            top_k=10,
            embedding_model=embedding_provider.metadata.model_name,
            allowed_source_ids=set(),
        )

        assert results == []

    async def test_keyword_retrieval_with_empty_source_set_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify an explicitly empty keyword source filter returns
        no results.
        """

        repository = rag_smoke_environment.retrieval_repository

        results = await repository.keyword_search(
            query="reservation articles production",
            top_k=10,
            source_ids=set(),
        )

        assert results == []

    async def test_vector_retrieval_without_source_filter_can_find_indexed_data(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify vector retrieval works across the indexed corpus
        without a source restriction.
        """

        embedding_provider = rag_smoke_environment.embedding_provider
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

        returned_source_ids = {result.chunk.metadata["source_id"] for result in results}

        assert returned_source_ids
        assert returned_source_ids.issubset(set(rag_smoke_environment.source_ids))

    async def test_keyword_retrieval_without_source_filter_can_find_indexed_data(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify keyword retrieval works across the indexed corpus
        without a source restriction.
        """

        repository = rag_smoke_environment.retrieval_repository

        results = await repository.keyword_search(
            query="handlooms reservation production",
            top_k=10,
            source_ids=None,
        )

        assert results

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _score in results}

        assert returned_source_ids
        assert returned_source_ids.issubset(set(rag_smoke_environment.source_ids))
