from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestRAGHybridRetrieval:
    async def test_retrieves_relevant_legal_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval can retrieve relevant chunks
        from the multi-document legal corpus.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="What is the purpose of this Act?",
            top_k=5,
            allowed_source_ids=None,
        )

        assert results
        assert len(results) <= 5

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()
            assert result.chunk.source_id
            assert result.score is not None
            assert 0.0 <= result.score <= 1.0
            assert result.embeddings

    async def test_hybrid_retrieval_respects_top_k(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval does not return more results
        than requested.
        """

        top_k = 3

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation of articles for production",
            top_k=top_k,
            allowed_source_ids=None,
        )

        assert len(results) <= top_k

    async def test_hybrid_retrieval_respects_top_k_one(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify top_k=1 returns at most one result.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation production",
            top_k=1,
            allowed_source_ids=None,
        )

        assert len(results) <= 1

    async def test_hybrid_results_are_ranked_by_reranker_score(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid results are returned in descending
        reranker-score order.
        """

        source_id = rag_smoke_environment.source_ids[1]

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="handlooms reservation production",
            top_k=5,
            allowed_source_ids={source_id},
        )

        assert results

        scores = [result.score for result in results]

        assert scores == sorted(
            scores,
            reverse=True,
        )

    async def test_hybrid_results_contain_unique_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval does not return duplicate chunks.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="handlooms reservation",
            top_k=10,
            allowed_source_ids=None,
        )

        assert results

        chunk_ids = [result.chunk.id for result in results]

        assert len(chunk_ids) == len(set(chunk_ids))

    async def test_hybrid_results_preserve_embedding_metadata(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval preserves embedding metadata
        from vector retrieval.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="articles reserved for production",
            top_k=5,
            allowed_source_ids=None,
        )

        assert results

        for result in results:
            assert result.embeddings

            for embedding in result.embeddings:
                assert embedding.model_name
                assert embedding.dimension > 0

    async def test_hybrid_retrieval_respects_first_source_filter(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval can be restricted to the
        first indexed legal source.
        """

        source_id = rag_smoke_environment.source_ids[0]

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="electronic records electronic signatures",
            top_k=10,
            allowed_source_ids={source_id},
        )

        assert results

        returned_source_ids = {result.chunk.source_id for result in results}

        assert returned_source_ids == {source_id}

    async def test_hybrid_retrieval_respects_second_source_filter(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval can be restricted to the
        second indexed legal source.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        source_id = rag_smoke_environment.source_ids[1]

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="handlooms reservation production",
            top_k=10,
            allowed_source_ids={source_id},
        )

        assert results

        returned_source_ids = {result.chunk.source_id for result in results}

        assert returned_source_ids == {source_id}

    async def test_hybrid_retrieval_does_not_leak_between_sources(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify source filtering prevents chunks from another
        legal document from appearing in the result set.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        source_a = rag_smoke_environment.source_ids[0]
        source_b = rag_smoke_environment.source_ids[1]

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="handlooms reservation production",
            top_k=10,
            allowed_source_ids={source_b},
        )

        assert results

        returned_source_ids = {result.chunk.source_id for result in results}

        assert source_b in returned_source_ids
        assert source_a not in returned_source_ids

    async def test_hybrid_retrieval_filtered_results_respect_top_k(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify source filtering and top_k constraints are
        applied together.
        """

        source_id = rag_smoke_environment.source_ids[1]

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="handlooms reservation production",
            top_k=2,
            allowed_source_ids={source_id},
        )

        assert len(results) <= 2

        if results:
            returned_source_ids = {result.chunk.source_id for result in results}

            assert returned_source_ids == {source_id}

    async def test_hybrid_retrieval_without_source_filter_can_search_all_documents(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval can operate across the entire
        indexed legal corpus when no source filter is provided.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=10,
            allowed_source_ids=None,
        )

        assert results

        returned_source_ids = {result.chunk.source_id for result in results}

        assert returned_source_ids

        assert returned_source_ids.issubset(
            set(rag_smoke_environment.source_ids),
        )

    async def test_hybrid_retrieval_with_empty_source_filter_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify an explicitly empty source filter means
        "match no sources".
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=10,
            allowed_source_ids=set(),
        )

        assert results == []

    async def test_hybrid_retrieval_with_nonexistent_source_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify filtering by a source ID that is not indexed
        returns no results.
        """

        nonexistent_source_id = "/nonexistent/legal/document.pdf"

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=10,
            allowed_source_ids={nonexistent_source_id},
        )

        assert results == []

    async def test_hybrid_retrieval_handles_no_matching_terms(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval safely handles a query containing
        terms that do not exist in the indexed corpus.

        Vector retrieval is semantic and may still return nearest
        neighbors, so an empty result set is not required.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="xyzzy_nonexistent_legal_term_987654",
            top_k=10,
            allowed_source_ids=None,
        )

        assert len(results) <= 10

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()
            assert result.chunk.source_id
            assert result.score is not None

    async def test_hybrid_retrieval_with_source_filter_and_no_matching_terms_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify source filtering does not manufacture matches when
        the query contains no matching terms.
        """

        source_id = rag_smoke_environment.source_ids[0]

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="xyzzy_nonexistent_legal_term_987654",
            top_k=10,
            allowed_source_ids={source_id},
        )

        assert results == []

    async def test_hybrid_results_preserve_source_provenance(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify every hybrid result preserves source provenance
        in the returned chunk.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=10,
            allowed_source_ids=None,
        )

        assert results

        expected_source_ids = set(
            rag_smoke_environment.source_ids,
        )

        for result in results:
            assert result.chunk.source_id
            assert result.chunk.source_id in expected_source_ids

    async def test_hybrid_results_have_valid_scores(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify every hybrid result contains a valid normalized
        reranker score.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation production",
            top_k=10,
            allowed_source_ids=None,
        )

        assert results

        for result in results:
            assert result.score is not None
            assert 0.0 <= result.score <= 1.0

    async def test_hybrid_results_have_non_empty_embedding_vectors(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid results contain populated embedding
        representations rather than empty embedding metadata.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation production",
            top_k=10,
            allowed_source_ids=None,
        )

        assert results

        for result in results:
            assert result.embeddings

            for embedding in result.embeddings:
                assert embedding.vector
                assert len(embedding.vector) == embedding.dimension
