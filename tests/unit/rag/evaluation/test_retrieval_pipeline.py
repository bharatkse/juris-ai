import pytest

from rag.evaluation.datasets.golden_dataset import GoldenDataset
from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator
from rag.evaluation.retrieval_runner import RetrievalEvaluationRunner
from rag.models import Chunk, RetrievalResult


class StubRetriever:
    async def retrieve(
        self,
        *,
        query: str,
        top_k: int,
        allowed_source_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                chunk=Chunk(
                    id="irrelevant",
                    source_id="other-source",
                    text="Unrelated legal material.",
                ),
                score=0.9,
            ),
            RetrievalResult(
                chunk=Chunk(
                    id="relevant",
                    source_id="contract-law",
                    text="Consideration is something of value exchanged between parties.",
                ),
                score=0.8,
            ),
        ][:top_k]


@pytest.mark.asyncio
async def test_runner_works_with_real_retrieval_evaluator() -> None:
    evaluator = RetrievalEvaluator(
        metrics=[
            RecallAtK(k=2, pass_threshold=0.5),
            PrecisionAtK(k=2, pass_threshold=0.5),
            MeanReciprocalRank(),
        ]
    )

    runner = RetrievalEvaluationRunner(
        retriever=StubRetriever(),
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
    assert report.passed_cases == 1
    assert report.failed_cases == 0
    assert report.passed is True

    assert report.mean_scores["recall@2"] == 1.0
    assert report.mean_scores["precision@2"] == 0.5
    assert report.mean_scores["mrr"] == 0.5


@pytest.mark.asyncio
async def test_runner_uses_evidence_as_primary_ground_truth() -> None:
    evaluator = RetrievalEvaluator(
        metrics=[
            RecallAtK(k=2),
            PrecisionAtK(k=2),
            MeanReciprocalRank(),
        ]
    )

    runner = RetrievalEvaluationRunner(
        retriever=StubRetriever(),
        evaluator=evaluator,
        top_k=2,
    )

    dataset = GoldenDataset(
        name="legal-retrieval",
        cases=[
            EvaluationCase(
                query="What is consideration?",
                answer="Something of value.",
                expected_sources=["different-source"],
                expected_evidence=["something of value exchanged between parties"],
            )
        ],
    )

    report = await runner.evaluate(dataset=dataset)

    assert report.mean_scores["recall@2"] == 1.0
    assert report.mean_scores["precision@2"] == 0.5
    assert report.mean_scores["mrr"] == 0.5


@pytest.mark.asyncio
async def test_runner_fails_quality_when_retrieval_is_not_relevant() -> None:
    class IrrelevantRetriever:
        async def retrieve(
            self,
            *,
            query: str,
            top_k: int,
            allowed_source_ids: set[str] | None = None,
        ) -> list[RetrievalResult]:
            return [
                RetrievalResult(
                    chunk=Chunk(
                        id="irrelevant",
                        source_id="other-source",
                        text="Completely unrelated material.",
                    ),
                    score=1.0,
                )
            ]

    evaluator = RetrievalEvaluator(
        metrics=[
            RecallAtK(k=1, pass_threshold=0.6),
            PrecisionAtK(k=1, pass_threshold=0.6),
            MeanReciprocalRank(),
        ]
    )

    runner = RetrievalEvaluationRunner(
        retriever=IrrelevantRetriever(),
        evaluator=evaluator,
        top_k=1,
    )

    dataset = GoldenDataset(
        name="legal-retrieval",
        cases=[
            EvaluationCase(
                query="What is consideration?",
                answer="Something of value.",
                expected_sources=["contract-law"],
                expected_evidence=["something of value"],
            )
        ],
    )

    report = await runner.evaluate(dataset=dataset)

    assert report.case_count == 1
    assert report.passed_cases == 0
    assert report.failed_cases == 1
    assert report.passed is False
