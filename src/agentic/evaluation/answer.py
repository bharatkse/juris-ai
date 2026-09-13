"""Answer-quality evaluation for proposed agent answers.

Architectural boundary:
    agentic.decisions -> what the LLM proposes
    agentic.evaluation -> how good/supported the proposed answer is
    agentic.policy -> whether the evaluation is sufficient
    agentic.lifecycle -> accept FINAL or continue execution

This module intentionally does NOT decide FINAL/CONTINUE.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass

from adapters.observability.logger import get_logger
from rag.evaluation.faithfulness_backend import FaithfulnessBackend

logger = get_logger(__name__)

SimilarityFn = Callable[[str, str], Awaitable[float]]


@dataclass(frozen=True, slots=True)
class AnswerQualityPolicy:
    """
    Deterministic thresholds applied after answer evaluation.

    min_groundedness and min_relevance were empirically calibrated
    (2026-09-13) against a small labeled set built from the RAG golden
    dataset (tests/datasets/rag/evaluation/legal_retrieval_gold_v1.json,
    29 cases) -- the same "calibrated to the dataset's real achievable
    ceiling" approach already used for rag.evaluation.metrics'
    PrecisionAtK, applied here for the first time. Re-run via
    scripts/python/calibrate_answer_quality_thresholds.py.

    Method: 29 positives (query + that case's own expected_evidence,
    formatted as an answer) and 29 negatives (the same query paired
    with a DIFFERENT case's expected_evidence -- an answer unsupported
    by what's actually retrieved for that question), scored with the
    real AnswerEvaluator (real embeddings, real Groq-backed
    FaithfulnessBackend, not mocked).

    Results:
      groundedness -- perfectly separated: every positive scored >= 0.5
        (median 0.5, two scored 1.0), every negative scored exactly
        0.0. Any threshold in (0, 0.5] gives 100% accuracy on this set;
        0.70 (the prior unexamined default) would have rejected 27/29
        genuinely grounded answers. Set to 0.50, the top of the
        positive cluster.
      relevance -- positives 0.453-0.835 (mean 0.686), negatives
        0.439-0.679 (mean 0.530); overlapping, not cleanly separable.
        A sweep over candidate thresholds found 0.60 maximizes accuracy
        (86.2%: 22/29 positives correctly pass, 28/29 negatives
        correctly fail). 0.70 only reached 75.9% (rejecting over half
        of genuinely relevant answers). Set to 0.60.

    Caveats, stated rather than hidden: n=29 per group, single legal
    corpus (IT Act 2000), one negative-construction strategy
    (evidence-swap, not model-generated hallucinations), and
    single-sentence synthetic positives -- some scored only 0.5 on
    groundedness because appending "(Section X)" made the answer a
    second, unverifiable claim rather than because the underlying fact
    was ungrounded (see the calibration script's positive-construction
    comment). This is a real calibration against real signals, not a
    guess, but it is a first pass on a small, narrow set -- revisit as
    real production traffic accumulates.

    min_correctness was empirically calibrated (2026-09-13, same script
    and dataset as above, extended). Positives: candidate answer scored
    against THIS case's own gold reference (the bare expected_evidence
    text). Negatives: the same case's query/evidence, but scored
    against the WRONG case's answer -- a mismatched response judged
    against the right question's gold reference. Positives 0.876-0.973
    (mean 0.931), negatives 0.400-0.724 (mean 0.524) -- cleanly
    separated, no overlap. A sweep found 0.75 gives perfect accuracy
    (100%: 29/29 positives correctly pass, 29/29 negatives correctly
    fail; 0.80 ties it, 0.70 already drops one negative). Set to 0.75.

    Caveat specific to correctness: it's still never exercised in the
    live path today (_gate_final never supplies a reference_answer, so
    result.correctness is always None there -- see is_sufficient) --
    this calibration is ready for whenever that changes, not yet load-
    bearing. And like the calibration above, this is one negative-
    construction strategy (evidence-swap) on n=29 from a single corpus
    -- a real signal, not a guess, but not a substitute for recalibrating
    against production data once available.

    min_citation_precision/min_citation_coverage have NO empirical
    calibration, and -- unlike groundedness/relevance/correctness --
    none is possible from this dataset: _evaluate_citations is exact
    set-membership (a cited source either is or isn't in the retrieved
    set), producing only the extremes 0.0 or 1.0 per case, not a
    continuous score with an overlapping distribution to sweep a
    threshold over. Confirmed via calibrate_answer_quality_thresholds.py:
    a correct citation scores (precision=1.0, coverage=1.0), a wrong one
    scores (0.0, 0.0) -- exactly as expected, but this is a sanity check
    of the metric, not a calibration of the threshold. 0.70 remains a
    policy choice (how much imperfect citing to tolerate), stated as
    such rather than dressed up as empirically derived.

    min_completeness is advisory only -- see is_sufficient's docstring.
    Kept as a named threshold (rather than deleted) so the "is this
    complete enough" question stays answerable/loggable even though it
    no longer gates. Not recalibrated: an advisory number doesn't need
    the same rigor as a blocking one, and the prior audit already
    showed embedding-similarity-based completeness scores are
    structurally noisy against verbose evidence regardless of where
    the line is drawn.
    """

    min_groundedness: float = 0.50
    min_relevance: float = 0.60
    min_completeness: float = 0.70
    min_correctness: float = 0.75
    min_citation_precision: float = 0.70
    min_citation_coverage: float = 0.70
    enforce_citations: bool = False

    def is_sufficient(self, result: AnswerEvaluationResult) -> bool:
        """Return whether the evaluated answer satisfies the quality policy.

        Groundedness is skipped, not failed, when no evidence was available
        to check the answer against (result.groundedness_detail.applicable
        is False) -- absence of evidence must not, by itself, force another
        reasoning turn.

        Groundedness and relevance are hard requirements: an ungrounded
        (hallucinated) or irrelevant (off-topic) answer must never pass,
        regardless of anything else.

        Completeness is advisory, not blocking (logged when below
        min_completeness, but does not affect the return value). Unlike
        groundedness/relevance, completeness is a thoroughness/style
        property, not a safety property -- a short, fully grounded,
        fully relevant answer measured against verbose evidence can
        legitimately score low on embedding-similarity-based
        completeness without being a bad answer (confirmed empirically
        with real embeddings during the answer.py audit). Gating on it
        with the same hard AND-threshold as groundedness/relevance
        forces the agent into unproductive extra reasoning loops on
        answers that are already good -- a known failure mode of
        strict-AND multi-dimension quality gates. There is no existing
        calibration data to derive a principled alternative (e.g.
        weighted) threshold from, so rather than invent one,
        completeness is demoted to an observed-and-logged signal until
        real calibration data exists to justify a specific number.

        Correctness is checked only when a reference answer was actually
        supplied (result.correctness is not None); it plays no role in
        sufficiency otherwise.
        """

        groundedness_ok = (
            not result.groundedness_detail.applicable
            or result.groundedness >= self.min_groundedness
        )

        if result.completeness < self.min_completeness:
            logger.info(
                "Answer completeness below advisory threshold "
                "(completeness=%.2f, min_completeness=%.2f); not blocking.",
                result.completeness,
                self.min_completeness,
            )

        if not (groundedness_ok and result.relevance >= self.min_relevance):
            return False

        if result.correctness is not None and result.correctness < self.min_correctness:
            return False

        if not self.enforce_citations:
            return True

        return (
            result.citation_precision >= self.min_citation_precision
            and result.citation_coverage >= self.min_citation_coverage
        )


@dataclass(frozen=True, slots=True)
class GroundednessResult:
    """
    Groundedness signal for an answer against supplied evidence.

    ``applicable`` is False when there was no evidence to check the answer
    against. That is a missing basis for judgment, not a failed check --
    see AnswerQualityPolicy.is_sufficient.
    """

    score: float
    applicable: bool


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
    """Evaluates a proposed answer's quality signals.

    Relevance, completeness, and correctness are embedding-similarity
    based (via the injected SimilarityFn) -- those are genuinely just
    "how close are these two texts", which similarity measures reasonably.

    Groundedness is judged by an injected FaithfulnessBackend instead of
    similarity: cosine similarity between a claim and a context sentence
    tracks topical overlap, not factual entailment, so it cannot catch a
    confidently wrong number or a fabricated requirement sitting in an
    otherwise on-topic sentence. FaithfulnessBackend is the same
    legacy/ragas switch point RAG evaluation uses (see
    rag.evaluation.faithfulness_backend and
    wiring.factories.evaluation.build_faithfulness_backend) -- this class
    does not know or care which concrete backend it was given.

    This evaluator produces quality signals; a separate policy decides whether
    those signals are sufficient to accept a proposed FINAL decision.
    """

    def __init__(
        self,
        *,
        similarity: SimilarityFn,
        faithfulness_backend: FaithfulnessBackend,
    ) -> None:
        self._similarity = similarity
        self._faithfulness_backend = faithfulness_backend

    async def evaluate(
        self,
        *,
        question: str,
        answer: str,
        evidence: Sequence[str] = (),
        reference_answer: str | None = None,
        citations: Sequence[str] = (),
        citation_sources: Sequence[str] = (),
    ) -> AnswerEvaluationResult:
        groundedness_detail = await self._evaluate_groundedness(
            question=question,
            answer=answer,
            evidence=evidence,
        )

        relevance = await self._evaluate_relevance(
            question=question,
            answer=answer,
        )

        completeness = await self._evaluate_completeness(
            question=question,
            answer=answer,
            evidence=evidence,
        )

        correctness = (
            await self._similarity(answer, reference_answer)
            if reference_answer is not None
            else None
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

    async def _evaluate_groundedness(
        self,
        *,
        question: str,
        answer: str,
        evidence: Sequence[str],
    ) -> GroundednessResult:
        if not answer.strip():
            return GroundednessResult(score=0.0, applicable=True)

        if not evidence:
            # Not applicable, not a failure: there is nothing to check the
            # answer against. AnswerQualityPolicy.is_sufficient skips this
            # signal rather than treating it as a failed check.
            return GroundednessResult(score=0.0, applicable=False)

        score = await self._faithfulness_backend.evaluate(
            query=question,
            answer=answer,
            contexts=list(evidence),
        )

        if score is None:
            # Judge evaluation unavailable is a real failure to establish
            # groundedness, unlike "no evidence" above -- it counts against
            # the answer rather than being skipped.
            return GroundednessResult(score=0.0, applicable=True)

        return GroundednessResult(score=score, applicable=True)

    async def _evaluate_relevance(self, *, question: str, answer: str) -> float:
        if not question.strip() or not answer.strip():
            return 0.0
        return await self._similarity(question, answer)

    async def _evaluate_completeness(
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
            scores = await asyncio.gather(
                *(self._similarity(item, answer) for item in evidence),
            )
            return sum(scores) / len(scores)

        return await self._similarity(question, answer)

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
