from __future__ import annotations

import pytest

from rag.models import RetrievalResult

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestRAGKeywordRetrieval:
    async def test_retrieves_relevant_legal_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify PostgreSQL keyword/full-text retrieval against the
        session-ingested multi-document legal corpus.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="reservation articles production",
            top_k=5,
        )

        assert rows
        assert len(rows) <= 5

        results: list[RetrievalResult] = []

        for chunk, score in rows:
            assert chunk.id
            assert chunk.text.strip()

            assert chunk.chunk_metadata is not None
            assert chunk.chunk_metadata["source_id"]

            assert score is not None

            results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=float(score),
                    embeddings=[],
                ),
            )

        assert results

    async def test_keyword_retrieval_respects_top_k(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that keyword retrieval never returns more results
        than requested.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="handlooms production",
            top_k=3,
        )

        assert len(rows) <= 3

    async def test_keyword_retrieval_respects_top_k_one(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that top_k=1 returns at most one result.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="handlooms production",
            top_k=1,
        )

        assert len(rows) <= 1

    async def test_keyword_retrieval_with_top_k_zero_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that top_k=0 produces no results.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="handlooms production",
            top_k=0,
        )

        assert rows == []

    async def test_keyword_retrieval_with_large_top_k_does_not_fail(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that a large top_k does not fail and still returns
        no more than the available matching chunks.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="handlooms production",
            top_k=10_000,
        )

        assert len(rows) <= 10_000

    async def test_keyword_results_are_ranked_by_score(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that keyword retrieval returns results in
        descending relevance-score order.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="articles reserved production",
            top_k=10,
        )

        assert rows

        scores = [float(score) for _, score in rows]

        assert scores == sorted(
            scores,
            reverse=True,
        )

    async def test_keyword_results_contain_unique_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that keyword retrieval does not return duplicate chunks.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="handlooms reservation",
            top_k=10,
        )

        assert rows

        chunk_ids = [chunk.id for chunk, _ in rows]

        assert len(chunk_ids) == len(set(chunk_ids))

    async def test_keyword_retrieval_with_empty_query_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that an empty query does not retrieve unrelated chunks.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="",
            top_k=10,
        )

        assert rows == []

    async def test_keyword_retrieval_with_whitespace_query_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that a whitespace-only query does not retrieve
        unrelated chunks.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="   ",
            top_k=10,
        )

        assert rows == []

    async def test_keyword_retrieval_with_duplicate_terms_does_not_duplicate_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that repeated query terms do not cause duplicate chunks.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="reservation reservation reservation",
            top_k=10,
        )

        if rows:
            chunk_ids = [chunk.id for chunk, _ in rows]

            assert len(chunk_ids) == len(set(chunk_ids))

    async def test_keyword_retrieval_handles_query_punctuation(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that ordinary legal-query punctuation does not cause
        keyword retrieval to fail.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="reservation, production; articles!",
            top_k=10,
        )

        assert rows

    async def test_keyword_retrieval_respects_first_source_filter(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that keyword retrieval can be restricted to the
        first legal source.
        """

        repository = rag_smoke_environment.retrieval_repository

        source_id = rag_smoke_environment.source_ids[0]

        rows = await repository.keyword_search(
            query="electronic records electronic signatures",
            top_k=10,
            metadata_filters={
                "source_id": source_id,
            },
        )

        assert rows

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _ in rows}

        assert returned_source_ids == {source_id}

    async def test_keyword_retrieval_respects_second_source_filter(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that keyword retrieval can be restricted to the
        second legal source.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        repository = rag_smoke_environment.retrieval_repository

        source_id = rag_smoke_environment.source_ids[1]

        rows = await repository.keyword_search(
            query="handlooms reservation production",
            top_k=10,
            metadata_filters={
                "source_id": source_id,
            },
        )

        assert rows

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _ in rows}

        assert returned_source_ids == {source_id}

    async def test_keyword_retrieval_with_multiple_source_filter(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that filtering by multiple indexed sources allows
        results from those sources.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        repository = rag_smoke_environment.retrieval_repository

        source_a = rag_smoke_environment.source_ids[0]
        source_b = rag_smoke_environment.source_ids[1]

        rows = await repository.keyword_search(
            query="legal act",
            top_k=10,
            metadata_filters={
                "source_id": {
                    source_a,
                    source_b,
                },
            },
        )

        assert rows

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _ in rows}

        assert returned_source_ids
        assert returned_source_ids.issubset(
            {source_a, source_b},
        )

    async def test_keyword_retrieval_does_not_leak_between_sources(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that a source-filtered keyword query cannot return
        chunks belonging to another legal source.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        repository = rag_smoke_environment.retrieval_repository

        source_a = rag_smoke_environment.source_ids[0]
        source_b = rag_smoke_environment.source_ids[1]

        rows = await repository.keyword_search(
            query="handlooms reservation production",
            top_k=10,
            metadata_filters={
                "source_id": source_b,
            },
        )

        assert rows

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _ in rows}

        assert source_b in returned_source_ids
        assert source_a not in returned_source_ids

    async def test_keyword_retrieval_filtered_results_respect_top_k(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that source filtering and top_k constraints are
        applied together.
        """

        repository = rag_smoke_environment.retrieval_repository

        source_id = rag_smoke_environment.source_ids[1]

        rows = await repository.keyword_search(
            query="handlooms reservation production",
            top_k=2,
            metadata_filters={
                "source_id": source_id,
            },
        )

        assert len(rows) <= 2

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _ in rows}

        if rows:
            assert returned_source_ids == {source_id}

    async def test_keyword_retrieval_without_source_filter_searches_all_documents(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that omitting the source filter allows retrieval
        across the complete indexed corpus.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="legal act",
            top_k=10,
            metadata_filters=None,
        )

        assert rows

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _ in rows}

        assert returned_source_ids
        assert returned_source_ids.issubset(
            set(rag_smoke_environment.source_ids),
        )

    async def test_keyword_retrieval_with_empty_source_filter_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that an explicitly empty source filter means
        "match no sources", rather than "search all sources".
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="legal act",
            top_k=10,
            source_ids=set(),
        )

        assert rows == []

    async def test_keyword_retrieval_with_nonexistent_source_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that filtering by a source ID that is not indexed
        returns no results.
        """

        repository = rag_smoke_environment.retrieval_repository

        nonexistent_source_id = "/nonexistent/legal/document.pdf"

        rows = await repository.keyword_search(
            query="legal act",
            top_k=10,
            metadata_filters={
                "source_id": nonexistent_source_id,
            },
        )

        assert rows == []

    async def test_keyword_retrieval_with_valid_and_nonexistent_sources(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that a mixed source filter returns results only from
        indexed sources.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        repository = rag_smoke_environment.retrieval_repository

        valid_source = rag_smoke_environment.source_ids[0]
        nonexistent_source = "/nonexistent/legal/document.pdf"

        rows = await repository.keyword_search(
            query="legal act",
            top_k=10,
            metadata_filters={
                "source_id": {
                    valid_source,
                    nonexistent_source,
                },
            },
        )

        assert rows

        returned_source_ids = {chunk.chunk_metadata["source_id"] for chunk, _ in rows}

        assert returned_source_ids == {valid_source}

    async def test_keyword_retrieval_with_no_matching_terms_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that a query containing terms absent from the
        indexed legal corpus does not produce unrelated chunks.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="xyzzy_nonexistent_legal_term_987654",
            top_k=10,
        )

        assert rows == []

    async def test_keyword_retrieval_with_source_filter_and_no_matching_terms_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that source filtering does not manufacture matches
        when the query has no matching terms.
        """

        repository = rag_smoke_environment.retrieval_repository

        source_id = rag_smoke_environment.source_ids[0]

        rows = await repository.keyword_search(
            query="xyzzy_nonexistent_legal_term_987654",
            top_k=10,
            metadata_filters={
                "source_id": source_id,
            },
        )

        assert rows == []

    async def test_keyword_retrieval_preserves_source_metadata(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that every retrieved chunk contains the source
        provenance metadata used by source filtering.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="legal act",
            top_k=10,
        )

        assert rows

        expected_source_ids = set(
            rag_smoke_environment.source_ids,
        )

        for chunk, _ in rows:
            assert chunk.chunk_metadata is not None

            source_id = chunk.chunk_metadata.get(
                "source_id",
            )

            assert source_id
            assert source_id in expected_source_ids

    async def test_keyword_retrieval_scores_are_numeric(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that every keyword result contains a numeric
        relevance score.
        """

        repository = rag_smoke_environment.retrieval_repository

        rows = await repository.keyword_search(
            query="reservation production",
            top_k=10,
        )

        assert rows

        for _, score in rows:
            assert score is not None

            # PostgreSQL numeric-like values such as Decimal are
            # acceptable as long as they represent a valid number.
            numeric_score = float(score)

            assert numeric_score == numeric_score


class TestPostgresKeywordStore:
    async def test_keyword_store_retrieves_relevant_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify the application-level keyword store adapter.
        """

        store = rag_smoke_environment.keyword_store

        results = await store.query(
            query="reservation articles production",
            top_k=5,
        )

        assert results
        assert len(results) <= 5

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()
            assert result.chunk.source_id
            assert result.score is not None

    async def test_keyword_store_respects_first_allowed_source(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that allowed_source_ids is translated correctly by
        the keyword-store adapter for offline-ingested documents.
        """

        store = rag_smoke_environment.keyword_store

        source_id = rag_smoke_environment.source_ids[0]

        results = await store.query(
            query="electronic records electronic signatures",
            top_k=10,
            allowed_source_ids={source_id},
        )

        assert results

        returned_source_ids = {result.chunk.source_id for result in results}

        assert returned_source_ids == {source_id}

    async def test_keyword_store_respects_second_allowed_source(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify source isolation for the second legal document
        through the application-level keyword store.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        store = rag_smoke_environment.keyword_store

        source_id = rag_smoke_environment.source_ids[1]

        results = await store.query(
            query="handlooms reservation production",
            top_k=10,
            allowed_source_ids={source_id},
        )

        assert results

        returned_source_ids = {result.chunk.source_id for result in results}

        assert returned_source_ids == {source_id}

    async def test_keyword_store_does_not_leak_between_sources(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that the keyword-store adapter cannot return chunks
        from a disallowed source.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        store = rag_smoke_environment.keyword_store

        source_a = rag_smoke_environment.source_ids[0]
        source_b = rag_smoke_environment.source_ids[1]

        results = await store.query(
            query="handlooms reservation production",
            top_k=10,
            allowed_source_ids={source_b},
        )

        assert results

        returned_source_ids = {result.chunk.source_id for result in results}

        assert source_a not in returned_source_ids
        assert returned_source_ids == {source_b}

    # async def test_keyword_store_with_invalid_allowed_sources_returns_no_results(
    #     self,
    #     rag_smoke_environment,
    # ) -> None:
    #     """
    #     Verify that an explicitly empty allowed-source set means
    #     "match no sources".
    #     """

    #     store = rag_smoke_environment.keyword_store

    #     results = await store.query(
    #         query="legal act",
    #         top_k=10,
    #         allowed_source_ids=set("invalid-id",),
    #     )

    #     assert results == []

    async def test_keyword_store_with_nonexistent_allowed_source_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that an unknown allowed source cannot produce results.
        """

        store = rag_smoke_environment.keyword_store

        results = await store.query(
            query="legal act",
            top_k=10,
            allowed_source_ids={
                "/nonexistent/legal/document.pdf",
            },
        )

        assert results == []

    async def test_keyword_store_with_multiple_allowed_sources(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that multiple allowed sources can participate in
        keyword retrieval.
        """

        assert (
            len(
                rag_smoke_environment.source_ids,
            )
            >= 2
        )

        store = rag_smoke_environment.keyword_store

        allowed_sources = set(
            rag_smoke_environment.source_ids[:2],
        )

        results = await store.query(
            query="legal act",
            top_k=10,
            allowed_source_ids=allowed_sources,
        )

        assert results

        returned_source_ids = {result.chunk.source_id for result in results}

        assert returned_source_ids
        assert returned_source_ids.issubset(
            allowed_sources,
        )

    async def test_keyword_store_with_no_matching_terms_returns_no_results(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify that the adapter does not manufacture results for
        an unmatched query.
        """

        store = rag_smoke_environment.keyword_store

        results = await store.query(
            query="xyzzy_nonexistent_legal_term_987654",
            top_k=10,
        )

        assert results == []
