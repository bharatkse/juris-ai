import pytest

from rag.evaluation.datasets.golden_dataset import GoldenDataset
from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator
from rag.evaluation.retrieval_runner import RetrievalEvaluationRunner
from rag.hybrid_retriever import HybridRetriever
from rag.models import Chunk, RetrievalResult


class StubEmbeddingProvider:
    class Metadata:
        model_name = "test-embedding"
        dimension = 3

    metadata = Metadata()

    async def embed_one(self, *, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class StubVectorStore:
    async def query(
        self,
        *,
        vector: list[float],
        top_k: int,
        embedding_model: str,
        allowed_source_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                chunk=Chunk(
                    id="chunk-1",
                    source_id="contract-law",
                    text="Consideration is something of value exchanged between parties.",
                ),
                score=0.9,
            ),
            RetrievalResult(
                chunk=Chunk(
                    id="chunk-2",
                    source_id="other-law",
                    text="Unrelated legal material.",
                ),
                score=0.8,
            ),
        ][:top_k]


class StubKeywordStore:
    async def query(
        self,
        *,
        query: str,
        top_k: int,
        allowed_source_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                chunk=Chunk(
                    id="chunk-1",
                    source_id="contract-law",
                    text="Consideration is something of value exchanged between parties.",
                ),
                score=0.95,
            ),
            RetrievalResult(
                chunk=Chunk(
                    id="chunk-3",
                    source_id="other-law",
                    text="Another unrelated legal provision.",
                ),
                score=0.7,
            ),
        ][:top_k]


class StubReranker:
    async def rerank(
        self,
        *,
        query: str,
        candidates: list[RetrievalResult],
        top_k: int,
    ) -> list[RetrievalResult]:
        return candidates[:top_k]


@pytest.mark.asyncio
async def test_hybrid_retriever_works_with_retrieval_evaluation_runner() -> None:
    retriever = HybridRetriever(
        embedding_provider=StubEmbeddingProvider(),
        vector_store=StubVectorStore(),
        keyword_store=StubKeywordStore(),
        reranker=StubReranker(),
    )

    evaluator = RetrievalEvaluator(
        metrics=[
            RecallAtK(k=2, pass_threshold=0.5),
            PrecisionAtK(k=2, pass_threshold=0.5),
            MeanReciprocalRank(),
        ]
    )

    runner = RetrievalEvaluationRunner(
        retriever=retriever,
        evaluator=evaluator,
        top_k=2,
    )

    dataset = GoldenDataset(
        name="legal-retrieval",
        cases=[
            EvaluationCase(
                query="What is consideration?",
                answer="Something of value exchanged between parties.",
                expected_sources=["contract-law"],
                expected_evidence=["something of value exchanged between parties"],
            )
        ],
    )

    report = await runner.evaluate(dataset=dataset)

    assert isinstance(report, RetrievalEvaluationReport)
    assert report.case_count == 1

    assert report.mean_scores["recall@2"] == 1.0
    assert report.mean_scores["precision@2"] == 0.5
    assert report.mean_scores["mrr"] == 1.0


@pytest.mark.asyncio
async def test_evaluation_runner_does_not_filter_hybrid_retrieval_by_ground_truth() -> None:
    class RecordingVectorStore(StubVectorStore):
        def __init__(self) -> None:
            self.allowed_source_ids: set[str] | None = None

        async def query(
            self,
            *,
            vector: list[float],
            top_k: int,
            embedding_model: str,
            allowed_source_ids: set[str] | None = None,
        ) -> list[RetrievalResult]:
            self.allowed_source_ids = allowed_source_ids
            return await super().query(
                vector=vector,
                top_k=top_k,
                embedding_model=embedding_model,
                allowed_source_ids=allowed_source_ids,
            )

    class RecordingKeywordStore(StubKeywordStore):
        def __init__(self) -> None:
            self.allowed_source_ids: set[str] | None = None

        async def query(
            self,
            *,
            query: str,
            top_k: int,
            allowed_source_ids: set[str] | None = None,
        ) -> list[RetrievalResult]:
            self.allowed_source_ids = allowed_source_ids
            return await super().query(
                query=query,
                top_k=top_k,
                allowed_source_ids=allowed_source_ids,
            )

    vector_store = RecordingVectorStore()
    keyword_store = RecordingKeywordStore()

    retriever = HybridRetriever(
        embedding_provider=StubEmbeddingProvider(),
        vector_store=vector_store,
        keyword_store=keyword_store,
        reranker=StubReranker(),
    )

    evaluator = RetrievalEvaluator(
        metrics=[
            RecallAtK(k=2),
        ]
    )

    runner = RetrievalEvaluationRunner(
        retriever=retriever,
        evaluator=evaluator,
        top_k=2,
    )

    dataset = GoldenDataset(
        name="legal-retrieval",
        cases=[
            EvaluationCase(
                query="What is consideration?",
                answer="Something of value.",
                expected_sources=["contract-law"],
            )
        ],
    )

    await runner.evaluate(dataset=dataset)

    assert vector_store.allowed_source_ids is None
    assert keyword_store.allowed_source_ids is None
