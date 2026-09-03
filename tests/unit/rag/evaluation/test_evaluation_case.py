from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.models import Chunk, RetrievalResult


def _result(
    *,
    chunk_id: str,
    text: str,
    source_id: str | None = None,
) -> RetrievalResult:
    return RetrievalResult(
        chunk=Chunk(
            id=chunk_id,
            source_id=source_id,
            text=text,
        ),
        score=1.0,
    )


def test_evaluation_case_defaults() -> None:
    case = EvaluationCase(
        query="What is consideration?",
        answer="Something of value exchanged between parties.",
    )

    assert case.retrieval_results == []
    assert case.reference_answer is None
    assert case.reference_contexts is None
    assert case.expected_sources == []
    assert case.expected_evidence == []


def test_contexts_returns_retrieved_chunk_text() -> None:
    case = EvaluationCase(
        query="What is consideration?",
        answer="Something of value.",
        retrieval_results=[
            _result(
                chunk_id="chunk-1",
                text="Consideration is something of value.",
                source_id="contract-law",
            ),
            _result(
                chunk_id="chunk-2",
                text="Consideration must have legal value.",
                source_id="contract-law",
            ),
        ],
    )

    assert case.contexts == [
        "Consideration is something of value.",
        "Consideration must have legal value.",
    ]


def test_contexts_is_empty_when_no_retrieval_results() -> None:
    case = EvaluationCase(
        query="What is consideration?",
        answer="Something of value.",
    )

    assert case.contexts == []


def test_evaluation_case_preserves_retrieval_results() -> None:
    retrieval_results = [
        _result(
            chunk_id="chunk-1",
            text="Relevant legal evidence.",
            source_id="act-1",
        )
    ]

    case = EvaluationCase(
        query="What is consideration?",
        answer="Something of value.",
        retrieval_results=retrieval_results,
        expected_sources=["act-1"],
        expected_evidence=["Relevant legal evidence."],
    )

    assert case.retrieval_results == retrieval_results
    assert case.expected_sources == ["act-1"]
    assert case.expected_evidence == ["Relevant legal evidence."]
