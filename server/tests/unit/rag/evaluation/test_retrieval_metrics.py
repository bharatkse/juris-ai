import pytest

from rag.evaluation.metrics.mrr import MeanReciprocalRank
from rag.evaluation.metrics.precision import PrecisionAtK
from rag.evaluation.metrics.recall import RecallAtK
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.models import Chunk, RetrievalResult


def _result(
    *,
    chunk_id: str,
    text: str,
    source: str | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk=Chunk(
            id=chunk_id,
            source=source,
            text=text,
        ),
        score=1.0,
    )


@pytest.mark.asyncio
async def test_recall_at_k_uses_evidence() -> None:
    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[
            _result(chunk_id="1", text="The limitation period is three years."),
            _result(chunk_id="2", text="Unrelated provision."),
        ],
        expected_evidence=["limitation period is three years"],
    )

    result = await RecallAtK(k=2).evaluate(case=case)

    assert result.metric == "recall@2"
    assert result.score == 1.0
    assert result.passed is True
    assert result.metadata["evaluation_basis"] == "evidence"


@pytest.mark.asyncio
async def test_recall_at_k_only_considers_top_k() -> None:
    case = EvaluationCase(
        query="What is the limitation period?",
        answer="Three years.",
        retrieval_results=[
            _result(chunk_id="1", text="Unrelated provision."),
            _result(chunk_id="2", text="The limitation period is three years."),
        ],
        expected_evidence=["limitation period is three years"],
    )

    result = await RecallAtK(k=1).evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False


@pytest.mark.asyncio
async def test_recall_at_k_falls_back_to_sources() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(
                chunk_id="1",
                text="Relevant content",
                source="act-1",
            ),
            _result(
                chunk_id="2",
                text="Other content",
                source="act-2",
            ),
        ],
        expected_sources=["act-1"],
    )

    result = await RecallAtK(k=2).evaluate(case=case)

    assert result.score == 1.0
    assert result.metadata["evaluation_basis"] == "source"


@pytest.mark.asyncio
async def test_recall_at_k_fails_without_ground_truth() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(chunk_id="1", text="Content"),
        ],
    )

    result = await RecallAtK(k=1).evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["reason"] == "missing retrieval ground truth"


@pytest.mark.asyncio
async def test_precision_at_k_uses_evidence() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(chunk_id="1", text="Relevant legal provision."),
            _result(chunk_id="2", text="Unrelated provision."),
        ],
        expected_evidence=["relevant legal provision"],
    )

    result = await PrecisionAtK(k=2).evaluate(case=case)

    assert result.metric == "precision@2"
    assert result.score == 0.5
    # Passes: with 1 expected_evidence item and k=2, 0.5 is the
    # achievable ceiling (1 relevant slot out of 2), not a shortfall
    # against the full 0.6 pass_threshold.
    assert result.passed is True
    assert result.metadata["evaluation_basis"] == "evidence"
    assert result.metadata["effective_pass_threshold"] == "0.5000"


@pytest.mark.asyncio
async def test_precision_at_k_passes_at_achievable_ceiling_for_single_evidence_item() -> None:
    """
    Real-world dataset shape: 1 expected_evidence item, k=5. Even a
    perfect retrieval (the one relevant chunk found, ranked first)
    scores exactly 0.2 -- the other 4 slots have nothing left to be
    relevant to. This must pass, not fail against the full 0.6.
    """

    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(chunk_id="1", text="The relevant legal provision."),
            _result(chunk_id="2", text="Unrelated."),
            _result(chunk_id="3", text="Unrelated."),
            _result(chunk_id="4", text="Unrelated."),
            _result(chunk_id="5", text="Unrelated."),
        ],
        expected_evidence=["relevant legal provision"],
    )

    result = await PrecisionAtK(k=5).evaluate(case=case)

    assert result.score == 0.2
    assert result.passed is True
    assert result.metadata["effective_pass_threshold"] == "0.2000"


@pytest.mark.asyncio
async def test_precision_at_k_still_requires_full_threshold_when_achievable() -> None:
    """
    Enough expected_evidence items exist (3) relative to k (5) that the
    configured 0.6 pass_threshold is genuinely achievable (ceiling =
    3/5 = 0.6) -- the relaxation must not kick in here.
    """

    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(chunk_id="1", text="Unrelated."),
            _result(chunk_id="2", text="Unrelated."),
            _result(chunk_id="3", text="Unrelated."),
            _result(chunk_id="4", text="Unrelated."),
            _result(chunk_id="5", text="Unrelated."),
        ],
        expected_evidence=["one", "two", "three"],
    )

    result = await PrecisionAtK(k=5).evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["effective_pass_threshold"] == "0.6000"


@pytest.mark.asyncio
async def test_precision_at_k_falls_back_to_sources() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(
                chunk_id="1",
                text="Relevant",
                source="act-1",
            ),
            _result(
                chunk_id="2",
                text="Irrelevant",
                source="act-2",
            ),
        ],
        expected_sources=["act-1"],
    )

    result = await PrecisionAtK(k=2).evaluate(case=case)

    assert result.score == 0.5
    assert result.metadata["evaluation_basis"] == "source"


@pytest.mark.asyncio
async def test_precision_at_k_returns_zero_without_results() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        expected_sources=["act-1"],
    )

    result = await PrecisionAtK(k=5).evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["reason"] == "no retrieval results"


@pytest.mark.asyncio
async def test_mrr_returns_first_relevant_rank() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(chunk_id="1", text="Unrelated"),
            _result(chunk_id="2", text="The relevant evidence."),
            _result(chunk_id="3", text="Also relevant."),
        ],
        expected_evidence=["relevant evidence"],
    )

    result = await MeanReciprocalRank().evaluate(case=case)

    assert result.metric == "mrr"
    assert result.score == 0.5
    assert result.passed is True
    assert result.metadata["first_relevant_rank"] == "2"


@pytest.mark.asyncio
async def test_mrr_returns_one_for_first_result() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(chunk_id="1", text="The relevant evidence."),
        ],
        expected_evidence=["relevant evidence"],
    )

    result = await MeanReciprocalRank().evaluate(case=case)

    assert result.score == 1.0
    assert result.metadata["first_relevant_rank"] == "1"


@pytest.mark.asyncio
async def test_mrr_returns_zero_when_relevant_result_is_missing() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(chunk_id="1", text="Unrelated"),
        ],
        expected_evidence=["missing evidence"],
    )

    result = await MeanReciprocalRank().evaluate(case=case)

    assert result.score == 0.0
    assert result.passed is False
    assert result.metadata["first_relevant_rank"] == "not_found"


@pytest.mark.asyncio
async def test_mrr_falls_back_to_sources() -> None:
    case = EvaluationCase(
        query="Question",
        answer="Answer",
        retrieval_results=[
            _result(
                chunk_id="1",
                text="Unrelated",
                source="act-2",
            ),
            _result(
                chunk_id="2",
                text="Relevant",
                source="act-1",
            ),
        ],
        expected_sources=["act-1"],
    )

    result = await MeanReciprocalRank().evaluate(case=case)

    assert result.score == 0.5
    assert result.metadata["evaluation_basis"] == "source"
