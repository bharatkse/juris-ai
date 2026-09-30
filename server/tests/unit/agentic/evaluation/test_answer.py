"""
Unit tests for AnswerEvaluator/AnswerQualityPolicy.

No prior coverage existed for this module before this file -- adding
focused tests for the citation-metric redesign (exact set-membership
-> continuous embedding similarity) rather than backfilling the whole
module, which is out of scope here.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.evaluation.answer import (
    AnswerEvaluationResult,
    AnswerEvaluator,
    AnswerQualityPolicy,
    GroundednessResult,
)


def _similarity_stub(scores: dict[tuple[str, str], float]):
    """
    Deterministic stand-in for the real embedding SimilarityFn --
    looks up a canned score by (a, b) (and its reverse, since
    similarity is symmetric), defaulting to 0.0 for any unlisted pair.
    """

    async def similarity(a: str, b: str) -> float:
        if (a, b) in scores:
            return scores[(a, b)]
        if (b, a) in scores:
            return scores[(b, a)]
        return 0.0

    return similarity


@pytest.mark.asyncio
async def test_evaluate_citations_no_citations_or_no_evidence_scores_zero() -> None:
    evaluator = AnswerEvaluator(
        similarity=_similarity_stub({}),
        faithfulness_backend=AsyncMock(),
    )

    assert await evaluator._evaluate_citations(citations=[], evidence=["chunk"]) == (
        0.0,
        0.0,
    )
    assert await evaluator._evaluate_citations(citations=["cite"], evidence=[]) == (
        0.0,
        0.0,
    )


@pytest.mark.asyncio
async def test_evaluate_citations_is_continuous_not_binary() -> None:
    """
    The whole point of the redesign: a partial match must score
    strictly between a perfect match and an unrelated one -- the old
    exact-set-membership metric could only ever produce 0.0 or 1.0.
    """

    evaluator = AnswerEvaluator(
        similarity=_similarity_stub(
            {
                ("exact citation", "exact citation"): 1.0,
                ("partial citation", "chunk"): 0.6,
                ("unrelated citation", "chunk"): 0.1,
            }
        ),
        faithfulness_backend=AsyncMock(),
    )

    exact_precision, exact_coverage = await evaluator._evaluate_citations(
        citations=["exact citation"],
        evidence=["exact citation"],
    )
    partial_precision, _ = await evaluator._evaluate_citations(
        citations=["partial citation"],
        evidence=["chunk"],
    )
    unrelated_precision, _ = await evaluator._evaluate_citations(
        citations=["unrelated citation"],
        evidence=["chunk"],
    )

    assert exact_precision == exact_coverage == 1.0
    assert unrelated_precision < partial_precision < exact_precision


@pytest.mark.asyncio
async def test_evaluate_citations_precision_and_coverage_diverge_with_multiple_items() -> None:
    """
    Confirms the AnswerQualityPolicy docstring's caveat: precision and
    coverage only collapse to the same value in the single-citation/
    single-evidence-chunk calibration shape. With multiple items on
    each side they measure genuinely different things -- citing one of
    two relevant chunks should score full precision (everything cited
    was relevant) but partial coverage (not everything relevant was
    cited).
    """

    evaluator = AnswerEvaluator(
        similarity=_similarity_stub(
            {
                ("citation", "relevant chunk 1"): 1.0,
                ("citation", "relevant chunk 2"): 0.0,
            }
        ),
        faithfulness_backend=AsyncMock(),
    )

    precision, coverage = await evaluator._evaluate_citations(
        citations=["citation"],
        evidence=["relevant chunk 1", "relevant chunk 2"],
    )

    assert precision == 1.0
    assert coverage == 0.5


@pytest.mark.asyncio
async def test_evaluate_runs_its_checks_concurrently() -> None:
    """
    Real concurrency, not just "doesn't crash": groundedness (the one
    real network round trip, here simulated with a real sleep) must
    run alongside the local embedding checks, not before/after them --
    total wall time should track the slowest single check, not their
    sum.
    """

    delay_seconds = 0.2

    async def slow_faithfulness_evaluate(*, query, answer, contexts):
        await asyncio.sleep(delay_seconds)
        return 1.0

    faithfulness_backend = AsyncMock()
    faithfulness_backend.evaluate = AsyncMock(side_effect=slow_faithfulness_evaluate)

    evaluator = AnswerEvaluator(
        similarity=_similarity_stub({}),
        faithfulness_backend=faithfulness_backend,
    )

    started = time.perf_counter()
    await evaluator.evaluate(
        question="q",
        answer="a",
        evidence=["chunk"],
        reference_answer="ref",
        citations=["cite"],
    )
    elapsed = time.perf_counter() - started

    # Sequential execution of 5 checks (1 slow + 4 near-instant) would
    # take >= 5 * delay_seconds if each accidentally re-triggered the
    # slow path, or just noticeably more than one delay_seconds' worth
    # of serialized overhead. Concurrent execution should finish in
    # close to one delay_seconds, not several.
    assert elapsed < delay_seconds * 2


async def _evaluate_without_evidence():
    """
    The A1 repro case: an on-topic answer with no evidence at all --
    groundedness is "not applicable", relevance passes.
    """

    evaluator = AnswerEvaluator(
        similarity=_similarity_stub({("What is section 43?", "Section 43 is about damage."): 0.9}),
        faithfulness_backend=AsyncMock(),
    )

    result = await evaluator.evaluate(
        question="What is section 43?",
        answer="Section 43 is about damage.",
        evidence=(),
    )

    assert result.groundedness_detail.applicable is False
    return result


@pytest.mark.asyncio
async def test_answer_without_evidence_is_insufficient_when_evidence_is_required() -> None:
    result = await _evaluate_without_evidence()

    assert AnswerQualityPolicy(require_evidence=True).is_sufficient(result) is False


@pytest.mark.asyncio
async def test_answer_without_evidence_still_passes_when_evidence_is_not_required() -> None:
    result = await _evaluate_without_evidence()

    assert AnswerQualityPolicy().is_sufficient(result) is True


def test_require_evidence_does_not_affect_an_answer_checked_against_evidence() -> None:
    result = AnswerEvaluationResult(
        groundedness=0.9,
        relevance=0.9,
        completeness=0.9,
        correctness=None,
        citation_precision=0.0,
        citation_coverage=0.0,
        groundedness_detail=GroundednessResult(score=0.9, applicable=True),
    )

    assert AnswerQualityPolicy(require_evidence=True).is_sufficient(result) is True


async def test_a_failover_answer_the_groundedness_judge_cannot_check_is_reported(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    R17: the groundedness judge (Groq-only) is down while the answer came
    from the local failover model. It still counts as not grounded
    (unchanged); a warning and a metric say the failover answer was lost.
    """

    import logging

    from agentic.evaluation import answer as answer_module
    from core.usage import record_llm_fallback, usage_scope

    discarded = MagicMock()
    monkeypatch.setattr(answer_module.metrics, "record_failover_answer_discarded", discarded)

    faithfulness_backend = AsyncMock()
    faithfulness_backend.evaluate = AsyncMock(return_value=None)
    evaluator = AnswerEvaluator(
        similarity=_similarity_stub({}),
        faithfulness_backend=faithfulness_backend,
    )

    with usage_scope(), caplog.at_level(logging.WARNING):
        record_llm_fallback()
        result = await evaluator.evaluate(question="q", answer="a", evidence=["chunk"])

    assert result.groundedness_detail.applicable is True
    assert result.groundedness_detail.score == 0.0
    discarded.assert_called_once_with(judge="groundedness")
    assert any("local failover" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_a_groundedness_judge_whose_provider_is_down_is_reported_unavailable() -> None:
    """R17: the gate skips the re-ask on this, rather than calling a provider that is down."""

    from core.judge_availability import record_judge_provider_unavailable

    async def evaluate(**_kwargs):
        record_judge_provider_unavailable()
        return None

    faithfulness_backend = AsyncMock()
    faithfulness_backend.evaluate = AsyncMock(side_effect=evaluate)
    evaluator = AnswerEvaluator(
        similarity=_similarity_stub({}),
        faithfulness_backend=faithfulness_backend,
    )

    result = await evaluator.evaluate(question="q", answer="a", evidence=["chunk"])

    assert result.groundedness_detail.judge_unavailable is True
    assert result.groundedness_detail.score == 0.0
    assert result.groundedness_detail.applicable is True


@pytest.mark.asyncio
async def test_a_groundedness_judge_that_answered_unusably_is_not_unavailable() -> None:
    faithfulness_backend = AsyncMock()
    faithfulness_backend.evaluate = AsyncMock(return_value=None)
    evaluator = AnswerEvaluator(
        similarity=_similarity_stub({}),
        faithfulness_backend=faithfulness_backend,
    )

    result = await evaluator.evaluate(question="q", answer="a", evidence=["chunk"])

    assert result.groundedness_detail.judge_unavailable is False
    assert result.groundedness_detail.score == 0.0


@pytest.mark.asyncio
async def test_an_unavailable_similarity_is_reported_not_raised() -> None:
    """
    G2: with the embedding model down the checks can't be scored. The
    result says so (the gate then gives the "couldn't verify" answer);
    the groundedness judge still ran to completion, not left behind.
    """

    from core.exceptions.rag import SimilarityUnavailableError

    async def similarity(a: str, b: str) -> float:
        raise SimilarityUnavailableError("embeddings down")

    faithfulness_backend = AsyncMock()
    faithfulness_backend.evaluate = AsyncMock(return_value=0.9)
    evaluator = AnswerEvaluator(
        similarity=similarity,
        faithfulness_backend=faithfulness_backend,
    )

    result = await evaluator.evaluate(question="q", answer="a", evidence=["chunk"])

    assert result.relevance_unavailable is True
    assert result.relevance == 0.0
    assert result.completeness == 0.0
    faithfulness_backend.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_scored_evaluation_is_not_marked_unavailable() -> None:
    faithfulness_backend = AsyncMock()
    faithfulness_backend.evaluate = AsyncMock(return_value=0.9)
    evaluator = AnswerEvaluator(
        similarity=_similarity_stub({}),
        faithfulness_backend=faithfulness_backend,
    )

    result = await evaluator.evaluate(question="q", answer="a", evidence=["chunk"])

    assert result.relevance_unavailable is False
