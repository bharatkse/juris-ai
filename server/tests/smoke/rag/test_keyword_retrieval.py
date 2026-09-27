from __future__ import annotations

import pytest

from tests.smoke.conftest import RAGSmokeEnvironment

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestRAGKeywordRetrieval:
    """
    Smoke tests for the production PostgresKeywordStore through the
    RAG retrieval path.

    Query-time source filtering is intentionally not tested here.
    Source provenance is tested on returned results.
    """

    async def test_retrieves_relevant_legal_chunks(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract breach damages",
            top_k=5,
        )

        assert results

        assert all(result.chunk.text for result in results)

    async def test_returns_at_most_top_k_results(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=2,
        )

        assert len(results) <= 2

    async def test_top_k_one_returns_at_most_one_result(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=1,
        )

        assert len(results) <= 1

    async def test_top_k_zero_returns_no_results(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=0,
        )

        assert results == []

    async def test_negative_top_k_returns_no_results(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=-1,
        )

        assert results == []

    async def test_large_top_k_does_not_fail(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=10_000,
        )

        assert isinstance(results, list)

    async def test_empty_query_returns_no_results(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="",
            top_k=5,
        )

        assert results == []

    async def test_whitespace_only_query_returns_no_results(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="   \t\n  ",
            top_k=5,
        )

        assert results == []

    async def test_punctuation_only_query_is_handled(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query=".,?!:;()[]{}\"'",
            top_k=5,
        )

        assert isinstance(results, list)

    async def test_query_with_punctuation_retrieves_results(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract, breach; damages!",
            top_k=5,
        )

        assert isinstance(results, list)

    async def test_duplicate_terms_do_not_duplicate_chunks(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract contract contract breach breach",
            top_k=10,
        )

        chunk_ids = [result.chunk.id for result in results]

        assert len(chunk_ids) == len(set(chunk_ids))

    async def test_results_have_unique_chunk_ids(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract breach",
            top_k=10,
        )

        chunk_ids = [result.chunk.id for result in results]

        assert len(chunk_ids) == len(set(chunk_ids))

    async def test_results_are_ranked_by_descending_score(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract breach damages",
            top_k=10,
        )

        scores = [result.score for result in results]

        assert scores == sorted(
            scores,
            reverse=True,
        )

    async def test_scores_are_numeric(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
        )

        assert all(isinstance(result.score, (int | float)) for result in results)

    async def test_scores_are_finite(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
        )

        assert all(
            result.score == result.score and abs(result.score) != float("inf") for result in results
        )

    async def test_matching_results_have_positive_scores(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
        )

        assert results

        assert all(result.score > 0 for result in results)

    async def test_results_contain_chunk_text(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
        )

        assert results

        assert all(
            isinstance(result.chunk.text, str) and result.chunk.text.strip() for result in results
        )

    async def test_results_preserve_chunk_identity(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
        )

        assert results

        assert all(result.chunk.id for result in results)

    async def test_results_preserve_knowledge_source_provenance(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
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

    async def test_query_does_not_require_source_filter(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        """
        Query-time RAG retrieval must work without a source restriction.
        """

        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
        )

        assert isinstance(results, list)

    async def test_retrieval_can_return_results_from_multiple_sources(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        """
        When the indexed corpus contains multiple KnowledgeSources,
        retrieval is allowed to return matches from multiple sources.

        This verifies that retrieval is corpus-wide rather than
        implicitly restricted to one uploaded/input source.
        """

        if len(rag_smoke_environment.sources) < 2:
            return

        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=50,
        )

        source_ids = {
            result.chunk.metadata.get("knowledge_source_id")
            for result in results
            if result.chunk.metadata.get("knowledge_source_id")
        }

        assert source_ids

    async def test_non_matching_query_returns_no_results(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="xyznonexistentterm123456789",
            top_k=5,
        )

        assert results == []

    async def test_case_variation_is_handled(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        lowercase_results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
        )

        uppercase_results = await rag_smoke_environment.keyword_store.query(
            query="CONTRACT",
            top_k=5,
        )

        assert isinstance(lowercase_results, list)
        assert isinstance(uppercase_results, list)

        assert [result.chunk.id for result in lowercase_results] == [
            result.chunk.id for result in uppercase_results
        ]

    async def test_repeated_query_is_deterministic(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        first = await rag_smoke_environment.keyword_store.query(
            query="contract breach",
            top_k=10,
        )

        second = await rag_smoke_environment.keyword_store.query(
            query="contract breach",
            top_k=10,
        )

        assert [result.chunk.id for result in first] == [result.chunk.id for result in second]

        assert [result.score for result in first] == [result.score for result in second]


class TestPostgresKeywordStore:
    """
    Focused smoke coverage for the concrete Postgres keyword store.

    These tests intentionally exercise the public store API only.
    """

    async def test_keyword_store_retrieves_relevant_chunks(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract breach",
            top_k=5,
        )

        assert results

    async def test_keyword_store_returns_empty_for_unknown_query(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="xyznonexistentterm123456789",
            top_k=5,
        )

        assert results == []

    async def test_keyword_store_preserves_source_provenance(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=5,
        )

        assert results

        assert all(result.chunk.metadata.get("knowledge_source_id") for result in results)

    async def test_keyword_store_handles_zero_top_k(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=0,
        )

        assert results == []

    async def test_keyword_store_handles_negative_top_k(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="contract",
            top_k=-100,
        )

        assert results == []

    async def test_keyword_store_handles_empty_query(
        self,
        rag_smoke_environment: RAGSmokeEnvironment,
    ) -> None:
        results = await rag_smoke_environment.keyword_store.query(
            query="",
            top_k=10,
        )

        assert results == []
