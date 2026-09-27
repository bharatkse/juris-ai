import pytest

from rag.evaluation.metrics.base import RAGMetric
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.metric_result import MetricResult
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator


class StubMetric(RAGMetric):
    def __init__(
        self,
        *,
        name: str,
        score: float,
        passed: bool,
    ) -> None:
        self._name = name
        self._score = score
        self._passed = passed

    @property
    def name(self) -> str:
        return self._name

    async def evaluate(self, *, case: EvaluationCase) -> MetricResult:
        return MetricResult(
            metric=self._name,
            score=self._score,
            passed=self._passed,
            metadata={"query": case.query},
        )


@pytest.mark.asyncio
async def test_retrieval_evaluator_runs_all_metrics() -> None:
    evaluator = RetrievalEvaluator(
        metrics=[
            StubMetric(name="recall@5", score=0.8, passed=True),
            StubMetric(name="precision@5", score=0.7, passed=True),
            StubMetric(name="mrr", score=1.0, passed=True),
        ]
    )

    case = EvaluationCase(
        query="What is a contract?",
        answer="",
    )

    result = await evaluator.evaluate(case=case)

    assert len(result.metrics) == 3
    assert result.scores == {
        "recall@5": 0.8,
        "precision@5": 0.7,
        "mrr": 1.0,
    }
    assert result.passed is True


@pytest.mark.asyncio
async def test_retrieval_evaluator_fails_when_any_metric_fails() -> None:
    evaluator = RetrievalEvaluator(
        metrics=[
            StubMetric(name="recall@5", score=0.8, passed=True),
            StubMetric(name="precision@5", score=0.4, passed=False),
            StubMetric(name="mrr", score=1.0, passed=True),
        ]
    )

    case = EvaluationCase(
        query="What is consideration?",
        answer="",
    )

    result = await evaluator.evaluate(case=case)

    assert len(result.metrics) == 3
    assert result.passed is False
    assert result.scores["precision@5"] == 0.4


@pytest.mark.asyncio
async def test_retrieval_evaluator_preserves_metric_metadata() -> None:
    evaluator = RetrievalEvaluator(
        metrics=[
            StubMetric(name="recall@5", score=0.8, passed=True),
        ]
    )

    case = EvaluationCase(
        query="What is consideration?",
        answer="",
    )

    result = await evaluator.evaluate(case=case)

    assert result.metrics[0].metadata["query"] == "What is consideration?"
