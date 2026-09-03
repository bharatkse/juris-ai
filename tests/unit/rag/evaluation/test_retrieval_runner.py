import pytest

from rag.evaluation.datasets.golden_dataset import GoldenDataset
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.evaluation_result import EvaluationResult
from rag.evaluation.models.metric_result import MetricResult
from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport
from rag.evaluation.retrieval_runner import RetrievalEvaluationRunner
from rag.models import Chunk, RetrievalResult


class StubRetriever:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def retrieve(
        self,
        *,
        query: str,
        top_k: int,
        allowed_source_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "allowed_source_ids": allowed_source_ids,
            }
        )

        return [
            RetrievalResult(
                chunk=Chunk(
                    id="chunk-1",
                    source_id="source-1",
                    text=f"Retrieved evidence for: {query}",
                ),
                score=1.0,
            )
        ]


class StubEvaluator:
    def __init__(self) -> None:
        self.cases: list[EvaluationCase] = []

    async def evaluate(self, *, case: EvaluationCase) -> EvaluationResult:
        self.cases.append(case)

        return EvaluationResult(
            metrics=[
                MetricResult(
                    metric="recall@5",
                    score=1.0,
                    passed=True,
                    metadata={},
                )
            ],
            passed=True,
        )


@pytest.mark.asyncio
async def test_runner_retrieves_and_evaluates_each_case() -> None:
    retriever = StubRetriever()
    evaluator = StubEvaluator()

    runner = RetrievalEvaluationRunner(
        retriever=retriever,
        evaluator=evaluator,
        top_k=5,
    )

    dataset = GoldenDataset(
        name="legal-retrieval",
        cases=[
            EvaluationCase(
                query="What is consideration?",
                answer="Consideration is something of value exchanged between parties.",
                expected_sources=["source-1"],
            ),
            EvaluationCase(
                query="What is breach of contract?",
                answer="A breach occurs when a party fails to perform a contractual obligation.",
                expected_sources=["source-1"],
            ),
        ],
    )

    report = await runner.evaluate(dataset=dataset)

    assert isinstance(report, RetrievalEvaluationReport)
    assert report.case_count == 2
    assert report.passed_cases == 2

    assert len(retriever.calls) == 2
    assert retriever.calls[0]["query"] == "What is consideration?"
    assert retriever.calls[0]["top_k"] == 5
    assert retriever.calls[0]["allowed_source_ids"] is None

    assert retriever.calls[1]["query"] == "What is breach of contract?"
    assert retriever.calls[1]["top_k"] == 5

    assert len(evaluator.cases) == 2


@pytest.mark.asyncio
async def test_runner_injects_retrieval_results_into_evaluation_case() -> None:
    retriever = StubRetriever()
    evaluator = StubEvaluator()

    runner = RetrievalEvaluationRunner(
        retriever=retriever,
        evaluator=evaluator,
        top_k=3,
    )

    original_case = EvaluationCase(
        query="What is consideration?",
        answer="Consideration is something of value.",
        expected_sources=["source-1"],
        expected_evidence=["something of value"],
    )

    dataset = GoldenDataset(
        name="legal-retrieval",
        cases=[original_case],
    )

    await runner.evaluate(dataset=dataset)

    evaluated_case = evaluator.cases[0]

    assert evaluated_case is not original_case
    assert evaluated_case.query == original_case.query
    assert evaluated_case.answer == original_case.answer
    assert evaluated_case.expected_sources == original_case.expected_sources
    assert evaluated_case.expected_evidence == original_case.expected_evidence

    assert len(evaluated_case.retrieval_results) == 1
    assert evaluated_case.retrieval_results[0].chunk.id == "chunk-1"


def test_runner_rejects_invalid_top_k() -> None:
    retriever = StubRetriever()
    evaluator = StubEvaluator()

    with pytest.raises(ValueError, match="top_k must be greater than zero"):
        RetrievalEvaluationRunner(
            retriever=retriever,
            evaluator=evaluator,
            top_k=0,
        )
