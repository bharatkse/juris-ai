from __future__ import annotations

import math

import pytest

from rag.models import (
    Chunk,
    EmbeddingRepresentation,
    RetrievalResult,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class TestRAGHybridRetrieval:
    async def test_retrieves_relevant_legal_chunks(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify hybrid retrieval returns relevant legal chunks
        from the indexed corpus.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="What is the purpose of this Act?",
            top_k=5,
        )

        assert results
        assert len(results) <= 5

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()

            # Source provenance is returned by RAG.
            assert result.chunk.metadata.get("knowledge_source_id")

            assert result.score is not None
            assert 0.0 <= result.score <= 1.0
            assert result.embeddings

    async def test_retrieval_respects_top_k(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify final retrieval never exceeds top_k."""

        top_k = 3

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation of articles for production",
            top_k=top_k,
        )

        assert len(results) <= top_k

    async def test_retrieval_with_top_k_one(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify top_k=1 returns at most one result."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation production",
            top_k=1,
        )

        assert len(results) <= 1

    async def test_top_k_zero_returns_empty(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify top_k=0 short-circuits retrieval."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=0,
        )

        assert results == []

    async def test_negative_top_k_returns_empty(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify negative top_k short-circuits retrieval."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=-1,
        )

        assert results == []

    async def test_empty_query_returns_empty(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify an empty query does not invoke retrieval."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="",
            top_k=5,
        )

        assert results == []

    async def test_whitespace_query_returns_empty(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify a whitespace-only query returns no results."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="   \t\n ",
            top_k=5,
        )

        assert results == []

    async def test_zero_fusion_candidates_returns_empty(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify fusion_candidates=0 short-circuits retrieval."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=5,
            fusion_candidates=0,
        )

        assert results == []

    async def test_negative_fusion_candidates_returns_empty(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify negative fusion_candidates short-circuits retrieval."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=5,
            fusion_candidates=-1,
        )

        assert results == []

    async def test_large_top_k_is_safe(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify requesting more results than the corpus can provide
        remains safe.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=10_000,
        )

        assert len(results) <= 10_000

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()

    async def test_hybrid_results_are_ranked_by_reranker_score(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify final results are ordered by the reranker's score.

        RRF determines candidate ordering only. The final returned
        ordering is determined by the reranker.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="handlooms reservation production",
            top_k=5,
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
        """Verify vector/keyword overlap is deduplicated."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="handlooms reservation",
            top_k=10,
        )

        assert results

        chunk_ids = [result.chunk.id for result in results]

        assert len(chunk_ids) == len(set(chunk_ids))

    async def test_results_preserve_chunk_identity(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify returned chunks retain their persisted identity."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation production",
            top_k=5,
        )

        assert results

        for result in results:
            assert result.chunk.id
            assert isinstance(result.chunk.id, str)

    async def test_results_preserve_chunk_text(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify returned chunks contain non-empty source text."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation production",
            top_k=5,
        )

        assert results

        for result in results:
            assert result.chunk.text
            assert result.chunk.text.strip()

    async def test_results_preserve_knowledge_source_provenance(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify RAG returns knowledge_source_id as output provenance.

        The source ID is metadata on the returned result; it is not
        supplied as a query-time retrieval filter.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="legal act",
            top_k=10,
        )

        assert results

        for result in results:
            knowledge_source_id = result.chunk.metadata.get(
                "knowledge_source_id",
            )

            assert knowledge_source_id
            assert isinstance(knowledge_source_id, str)

    async def test_results_have_valid_scores(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify reranker scores are finite and normalized."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation production",
            top_k=10,
        )

        assert results

        for result in results:
            assert result.score is not None
            assert math.isfinite(result.score)
            assert 0.0 <= result.score <= 1.0

    async def test_results_preserve_embedding_metadata(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify embedding metadata survives hybrid retrieval."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="articles reserved for production",
            top_k=5,
        )

        assert results

        for result in results:
            assert result.embeddings

            for embedding in result.embeddings:
                assert embedding.model_name
                assert embedding.dimension > 0

    async def test_results_contain_non_empty_embedding_vectors(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify returned embedding representations contain vectors."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation production",
            top_k=10,
        )

        assert results

        for result in results:
            assert result.embeddings

            for embedding in result.embeddings:
                assert embedding.vector
                assert len(embedding.vector) == embedding.dimension

    async def test_no_matching_terms_is_safe(
        self,
        rag_smoke_environment,
    ) -> None:
        """
        Verify an unknown query is handled safely.

        Vector retrieval is semantic, so results may still be returned.
        """

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="xyzzy_nonexistent_legal_term_987654",
            top_k=10,
        )

        assert len(results) <= 10

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()
            assert result.chunk.metadata.get("knowledge_source_id")
            assert result.score is not None

    async def test_punctuation_query_is_safe(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify punctuation-heavy queries do not fail."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="Act!!! ??? reservation,,, production...",
            top_k=5,
        )

        assert len(results) <= 5

        for result in results:
            assert result.chunk.id
            assert result.chunk.text.strip()

    async def test_repeated_terms_are_safe(
        self,
        rag_smoke_environment,
    ) -> None:
        """Verify repeated query terms are handled safely."""

        results = await rag_smoke_environment.hybrid_retriever.retrieve(
            query="reservation reservation reservation production production",
            top_k=5,
        )

        assert len(results) <= 5

        chunk_ids = [result.chunk.id for result in results]

        assert len(chunk_ids) == len(set(chunk_ids))


class TestHybridRetrieverRRF:
    """
    Focused unit tests for Reciprocal Rank Fusion.

    These tests do not require the database, embedding model,
    keyword index, or cross-encoder.
    """

    @staticmethod
    def _result(
        chunk_id: str,
        score: float,
        *,
        embeddings: list[EmbeddingRepresentation] | None = None,
    ) -> RetrievalResult:
        return RetrievalResult(
            chunk=Chunk(
                id=chunk_id,
                text=f"chunk {chunk_id}",
                metadata={
                    "knowledge_source_id": "ksrc_test",
                },
            ),
            score=score,
            embeddings=embeddings or [],
        )

    @staticmethod
    def _retriever(
        rrf_k: int = 60,
    ):
        class StubEmbeddingProvider:
            metadata = type(
                "Metadata",
                (),
                {
                    "model_name": "test-model",
                },
            )()

        class StubVectorStore:
            async def query(self, **kwargs):
                return []

        class StubKeywordStore:
            async def query(self, **kwargs):
                return []

        class StubReranker:
            async def rerank(self, **kwargs):
                return []

        from rag.hybrid_retriever import HybridRetriever

        return HybridRetriever(
            embedding_provider=StubEmbeddingProvider(),
            vector_store=StubVectorStore(),
            keyword_store=StubKeywordStore(),
            reranker=StubReranker(),
            rrf_k=rrf_k,
        )

    def test_rrf_fuses_ranked_lists(
        self,
    ) -> None:
        """Verify results from both retrieval strategies are fused."""

        retriever = self._retriever()

        vector_result = self._result("chunk-1", 0.9)
        keyword_result = self._result("chunk-2", 0.8)

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [vector_result],
                [keyword_result],
            ],
        )

        assert {result.chunk.id for result in fused} == {
            "chunk-1",
            "chunk-2",
        }

    def test_rrf_rewards_results_present_in_both_rankings(
        self,
    ) -> None:
        """
        Verify a chunk appearing in both ranked lists receives
        a combined RRF score and ranks ahead appropriately.
        """

        retriever = self._retriever()

        shared = self._result("shared", 0.5)
        vector_only = self._result("vector-only", 0.9)

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [shared, vector_only],
                [shared],
            ],
        )

        assert fused[0].chunk.id == "shared"

    def test_rrf_deduplicates_same_chunk(
        self,
    ) -> None:
        """Verify a chunk returned by both stores appears once."""

        retriever = self._retriever()

        first = self._result("chunk-1", 0.4)
        second = self._result("chunk-1", 0.9)

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [first],
                [second],
            ],
        )

        assert len(fused) == 1
        assert fused[0].chunk.id == "chunk-1"

    def test_rrf_preserves_higher_retrieval_score(
        self,
    ) -> None:
        """Verify duplicate chunks retain the higher source score."""

        retriever = self._retriever()

        first = self._result("chunk-1", 0.4)
        second = self._result("chunk-1", 0.9)

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [first],
                [second],
            ],
        )

        assert fused[0].score == 0.9

    def test_rrf_handles_empty_ranked_lists(
        self,
    ) -> None:
        """Verify empty vector/keyword result lists are safe."""

        retriever = self._retriever()

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [],
                [],
            ],
        )

        assert fused == []

    def test_rrf_handles_one_empty_ranked_list(
        self,
    ) -> None:
        """Verify fusion still works when one strategy returns nothing."""

        retriever = self._retriever()

        result = self._result("chunk-1", 0.8)

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [result],
                [],
            ],
        )

        assert len(fused) == 1
        assert fused[0].chunk.id == "chunk-1"

    def test_rrf_preserves_first_chunk(
        self,
    ) -> None:
        """
        Verify duplicate-result merging preserves the first
        RetrievalResult's chunk object.
        """

        retriever = self._retriever()

        first = self._result("chunk-1", 0.4)
        second = self._result("chunk-1", 0.9)

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [first],
                [second],
            ],
        )

        assert fused[0].chunk is first.chunk

    def test_rrf_merges_distinct_embeddings(
        self,
    ) -> None:
        """Verify embeddings from duplicate retrieval results are merged."""

        retriever = self._retriever()

        embedding_a = EmbeddingRepresentation(
            model_name="model-a",
            dimension=3,
            vector=[0.1, 0.2, 0.3],
        )

        embedding_b = EmbeddingRepresentation(
            model_name="model-b",
            dimension=3,
            vector=[0.4, 0.5, 0.6],
        )

        first = self._result(
            "chunk-1",
            0.4,
            embeddings=[embedding_a],
        )
        second = self._result(
            "chunk-1",
            0.9,
            embeddings=[embedding_b],
        )

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [first],
                [second],
            ],
        )

        assert len(fused) == 1
        assert len(fused[0].embeddings) == 2

        models = {embedding.model_name for embedding in fused[0].embeddings}

        assert models == {
            "model-a",
            "model-b",
        }

    def test_rrf_deduplicates_embedding_metadata(
        self,
    ) -> None:
        """
        Verify duplicate embeddings are deduplicated by
        model_name + dimension.
        """

        retriever = self._retriever()

        embedding_a = EmbeddingRepresentation(
            model_name="model-a",
            dimension=3,
            vector=[0.1, 0.2, 0.3],
        )

        embedding_b = EmbeddingRepresentation(
            model_name="model-a",
            dimension=3,
            vector=[0.9, 0.8, 0.7],
        )

        first = self._result(
            "chunk-1",
            0.4,
            embeddings=[embedding_a],
        )
        second = self._result(
            "chunk-1",
            0.9,
            embeddings=[embedding_b],
        )

        fused = retriever._reciprocal_rank_fusion(
            ranked_lists=[
                [first],
                [second],
            ],
        )

        assert len(fused) == 1
        assert len(fused[0].embeddings) == 1

        # First embedding is preserved when the metadata key is identical.
        assert fused[0].embeddings[0] is embedding_a

    def test_invalid_rrf_k_is_rejected(
        self,
    ) -> None:
        """Verify non-positive RRF constants are rejected."""

        with pytest.raises(ValueError, match="rrf_k"):
            self._retriever(rrf_k=0)

        with pytest.raises(ValueError, match="rrf_k"):
            self._retriever(rrf_k=-1)
