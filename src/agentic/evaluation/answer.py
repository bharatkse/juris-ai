"""Answer-quality evaluation for proposed agent answers.

Architectural boundary:
    agentic.decisions -> what the LLM proposes
    agentic.evaluation -> how good/supported the proposed answer is
    agentic.policy -> whether the evaluation is sufficient
    agentic.lifecycle -> accept FINAL or continue execution

This module intentionally does NOT decide FINAL/CONTINUE.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

SimilarityFn = Callable[[str, str], float]


@dataclass(frozen=True, slots=True)
class AnswerQualityPolicy:
    """Deterministic thresholds applied after answer evaluation."""

    min_groundedness: float = 0.70
    min_relevance: float = 0.70
    min_completeness: float = 0.70
    min_citation_precision: float = 0.70
    min_citation_coverage: float = 0.70
    enforce_citations: bool = False

    def is_sufficient(self, result: AnswerEvaluationResult) -> bool:
        """Return whether the evaluated answer satisfies the quality policy.

        Correctness is evaluated only when a reference answer is supplied;
        no correctness threshold is imposed when correctness is unavailable.
        """

        if not (
            result.groundedness >= self.min_groundedness
            and result.relevance >= self.min_relevance
            and result.completeness >= self.min_completeness
        ):
            return False

        if not self.enforce_citations:
            return True

        return (
            result.citation_precision >= self.min_citation_precision
            and result.citation_coverage >= self.min_citation_coverage
        )


@dataclass(frozen=True, slots=True)
class GroundednessResult:
    """Groundedness signal for an answer against supplied evidence."""

    score: float
    supported_claims: int
    total_claims: int


@dataclass(frozen=True, slots=True)
class AnswerEvaluationResult:
    """Quality signals produced by evaluating a proposed answer.

    ``correctness`` is ``None`` when no reference/ground truth is available.
    The result contains quality signals only; it does not encode FINAL/CONTINUE.
    """

    groundedness: float
    relevance: float
    completeness: float
    correctness: float | None
    citation_precision: float
    citation_coverage: float
    groundedness_detail: GroundednessResult


class AnswerEvaluator:
    """Deterministically evaluates a proposed answer using semantic similarity.

    The similarity function is injected so the evaluator is independent of a
    specific embedding implementation. Runtime callers can provide the
    platform's existing embedding provider.

    This evaluator produces quality signals; a separate policy decides whether
    those signals are sufficient to accept a proposed FINAL decision.
    """

    def __init__(self, *, similarity: SimilarityFn) -> None:
        self._similarity = similarity

    def evaluate(
        self,
        *,
        question: str,
        answer: str,
        evidence: Sequence[str] = (),
        reference_answer: str | None = None,
        citations: Sequence[str] = (),
        citation_sources: Sequence[str] = (),
    ) -> AnswerEvaluationResult:
        groundedness_detail = self._evaluate_groundedness(
            answer=answer,
            evidence=evidence,
        )

        relevance = self._evaluate_relevance(
            question=question,
            answer=answer,
        )

        completeness = self._evaluate_completeness(
            question=question,
            answer=answer,
            evidence=evidence,
        )

        correctness = (
            self._similarity(answer, reference_answer) if reference_answer is not None else None
        )

        citation_precision, citation_coverage = self._evaluate_citations(
            citations=citations,
            citation_sources=citation_sources,
            evidence=evidence,
        )

        return AnswerEvaluationResult(
            groundedness=groundedness_detail.score,
            relevance=relevance,
            completeness=completeness,
            correctness=correctness,
            citation_precision=citation_precision,
            citation_coverage=citation_coverage,
            groundedness_detail=groundedness_detail,
        )

    def _evaluate_groundedness(
        self,
        *,
        answer: str,
        evidence: Sequence[str],
    ) -> GroundednessResult:
        claims = _claims(answer)

        if not claims:
            return GroundednessResult(0.0, 0, 0)

        if not evidence:
            return GroundednessResult(0.0, 0, len(claims))

        supported = sum(
            max(self._similarity(claim, item) for item in evidence) >= 0.70 for claim in claims
        )
        return GroundednessResult(
            score=supported / len(claims),
            supported_claims=supported,
            total_claims=len(claims),
        )

    def _evaluate_relevance(self, *, question: str, answer: str) -> float:
        if not question.strip() or not answer.strip():
            return 0.0
        return self._similarity(question, answer)

    def _evaluate_completeness(
        self,
        *,
        question: str,
        answer: str,
        evidence: Sequence[str],
    ) -> float:
        if not question.strip() or not answer.strip():
            return 0.0

        # If evidence exists, measure whether the answer covers the available
        # evidence concepts. Otherwise use question-to-answer relevance as the
        # available deterministic signal.
        if evidence:
            scores = [self._similarity(item, answer) for item in evidence]
            return sum(scores) / len(scores)

        return self._similarity(question, answer)

    def _evaluate_citations(
        self,
        *,
        citations: Sequence[str],
        citation_sources: Sequence[str],
        evidence: Sequence[str],
    ) -> tuple[float, float]:
        if not evidence:
            # No evidence means citation quality is not demonstrable.
            return (0.0, 0.0)

        if not citations:
            return (0.0, 0.0)

        source_set = {source for source in citation_sources if source}

        if not source_set:
            # Citation identifiers without source mapping cannot establish
            # citation precision/coverage.
            return (0.0, 0.0)

        valid = sum(citation in source_set for citation in citations)
        precision = valid / len(citations)

        cited_evidence = {source for source in citations if source in source_set}
        coverage = len(cited_evidence) / len(source_set)

        return precision, coverage


def _claims(answer: str) -> list[str]:
    """Split an answer into simple claim-sized units.

    This is intentionally conservative and deterministic. It is not intended
    to replace an LLM judge in offline evaluation.
    """

    return [claim.strip() for claim in answer.replace("\n", " ").split(".") if claim.strip()]
