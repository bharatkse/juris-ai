import pytest

from rag.evaluation.evaluator import RAGEvaluator
from rag.evaluation.metrics.faithfulness import FaithfulnessMetric
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.models import Chunk, RetrievalResult


def _result(
    *,
    chunk_id: str,
    text: str,
) -> RetrievalResult:
    return RetrievalResult(
        chunk=Chunk(
            id=chunk_id,
            text=text,
        ),
        score=1.0,
    )


@pytest.mark.asyncio
async def test_faithfulness_passes_when_judge_score_meets_threshold() -> None:
    async def judge(prompt: str) -> str:
        return '{"score": 0.9, "unsupported_claims": []}'

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[
            _result(chunk_id="1", text="The limitation period is three years."),
        ],
    )

    result = await FaithfulnessMetric(evaluator=RAGEvaluator(judge=judge)).evaluate(case=case)

    assert result.metric == "faithfulness"
    assert result.score == 0.9
    assert result.passed is True
    assert result.metadata["retrieved_results"] == "1"


@pytest.mark.asyncio
async def test_faithfulness_fails_when_judge_score_below_threshold() -> None:
    async def judge(prompt: str) -> str:
        return '{"score": 0.2, "unsupported_claims": ["three years"]}'

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[
            _result(chunk_id="1", text="Unrelated provision."),
        ],
    )

    result = await FaithfulnessMetric(evaluator=RAGEvaluator(judge=judge)).evaluate(case=case)

    assert result.score == 0.2
    assert result.passed is False


@pytest.mark.asyncio
async def test_faithfulness_reports_no_retrieved_context() -> None:
    async def judge(prompt: str) -> str:
        raise AssertionError("judge should not be called without retrieved context")

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[],
    )

    result = await FaithfulnessMetric(evaluator=RAGEvaluator(judge=judge)).evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["reason"] == "no retrieved context"


@pytest.mark.asyncio
async def test_faithfulness_reports_no_generated_answer() -> None:
    async def judge(prompt: str) -> str:
        raise AssertionError("judge should not be called without a generated answer")

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="",
        retrieval_results=[
            _result(chunk_id="1", text="The limitation period is three years."),
        ],
    )

    result = await FaithfulnessMetric(evaluator=RAGEvaluator(judge=judge)).evaluate(case=case)

    # Not applicable, not a failure -- see the passed=True rationale in
    # faithfulness.py. A case with no generated answer must not drag
    # down the case's overall pass/fail status.
    assert result.score == 0.0
    assert result.passed is True
    assert result.metadata["reason"] == "no generated answer"


@pytest.mark.asyncio
async def test_faithfulness_reports_judge_unavailable_on_invalid_score() -> None:
    async def judge(prompt: str) -> str:
        return "not a JSON response at all"

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[
            _result(chunk_id="1", text="The limitation period is three years."),
        ],
    )

    result = await FaithfulnessMetric(evaluator=RAGEvaluator(judge=judge)).evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["reason"] == "judge evaluation unavailable"


@pytest.mark.asyncio
async def test_faithfulness_rejects_out_of_range_pass_threshold() -> None:
    async def judge(prompt: str) -> str:
        return '{"score": 0.5}'

    with pytest.raises(ValueError):
        FaithfulnessMetric(evaluator=RAGEvaluator(judge=judge), pass_threshold=1.5)
