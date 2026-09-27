import pytest

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


class _FakeBackend:
    """
    Minimal FaithfulnessBackend fake. FaithfulnessMetric only depends
    on the FaithfulnessBackend protocol (see faithfulness_backend.py),
    not on any concrete implementation -- these tests exercise that
    boundary directly rather than through a real ragas or legacy
    judge call.
    """

    def __init__(self, *, score: float | None, should_be_called: bool = True) -> None:
        self._score = score
        self._should_be_called = should_be_called
        self.called = False

    async def evaluate(self, *, query: str, answer: str, contexts: list[str]) -> float | None:
        if not self._should_be_called:
            raise AssertionError("backend should not be called for this case")

        self.called = True
        return self._score


@pytest.mark.asyncio
async def test_faithfulness_passes_when_backend_score_meets_threshold() -> None:
    backend = _FakeBackend(score=0.9)

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[
            _result(chunk_id="1", text="The limitation period is three years."),
        ],
    )

    result = await FaithfulnessMetric(backend=backend).evaluate(case=case)

    assert result.metric == "faithfulness"
    assert result.score == 0.9
    assert result.passed is True
    assert result.metadata["retrieved_results"] == "1"
    assert backend.called is True


@pytest.mark.asyncio
async def test_faithfulness_fails_when_backend_score_below_threshold() -> None:
    backend = _FakeBackend(score=0.2)

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[
            _result(chunk_id="1", text="Unrelated provision."),
        ],
    )

    result = await FaithfulnessMetric(backend=backend).evaluate(case=case)

    assert result.score == 0.2
    assert result.passed is False


@pytest.mark.asyncio
async def test_faithfulness_reports_no_retrieved_context() -> None:
    backend = _FakeBackend(score=1.0, should_be_called=False)

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[],
    )

    result = await FaithfulnessMetric(backend=backend).evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["reason"] == "no retrieved context"


@pytest.mark.asyncio
async def test_faithfulness_reports_no_generated_answer() -> None:
    backend = _FakeBackend(score=1.0, should_be_called=False)

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="",
        retrieval_results=[
            _result(chunk_id="1", text="The limitation period is three years."),
        ],
    )

    result = await FaithfulnessMetric(backend=backend).evaluate(case=case)

    # Not applicable, not a failure -- see the passed=True rationale in
    # faithfulness.py. A case with no generated answer must not drag
    # down the case's overall pass/fail status.
    assert result.score == 0.0
    assert result.passed is True
    assert result.metadata["reason"] == "no generated answer"


@pytest.mark.asyncio
async def test_faithfulness_reports_judge_unavailable_when_backend_returns_none() -> None:
    backend = _FakeBackend(score=None)

    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[
            _result(chunk_id="1", text="The limitation period is three years."),
        ],
    )

    result = await FaithfulnessMetric(backend=backend).evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["reason"] == "judge evaluation unavailable"


@pytest.mark.asyncio
async def test_faithfulness_rejects_out_of_range_pass_threshold() -> None:
    backend = _FakeBackend(score=0.5, should_be_called=False)

    with pytest.raises(ValueError):
        FaithfulnessMetric(backend=backend, pass_threshold=1.5)
