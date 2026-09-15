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

    min_citation_precision/min_citation_coverage ARE now empirically
    calibrated (2026-09-14, same script/dataset/evidence-swap method as
    above), following the redesign of _evaluate_citations from exact
    identifier set-membership (which only ever produced 0.0 or 1.0,
    with no overlapping distribution to sweep) to continuous embedding
    similarity between cited text and evidence chunks.

    Method: positives cite their own case's expected_evidence verbatim
    against that same evidence; negatives cite a DIFFERENT case's
    expected_evidence against this case's evidence -- the identical
    evidence-swap construction used for groundedness/correctness above.

    Results: positives are uniformly 1.000 (a citation compared to
    itself is a perfect match by construction). Negatives are NOT
    uniformly 0.0 the way the old metric's sanity check was -- they
    range 0.430-0.760 (mean 0.543), a real overlapping distribution,
    because embedding similarity between two different sections of the
    same statute is genuinely nonzero. A sweep found 0.80 gives perfect
    accuracy (100%: 29/29 positives correctly pass, 29/29 negatives
    correctly fail) -- 0.70 (the prior, unexamined default) only
    reached 96.6% (2 of 29 mismatched citations would have incorrectly
    passed). Set to 0.80.

    Caveat specific to this pair: precision and coverage are
    numerically IDENTICAL in this calibration -- an artifact of each
    case constructing exactly one citation against exactly one evidence
    chunk, where max-over-one-item collapses both formulas to the same
    value. They will diverge in production, where an answer can have
    multiple citations against multiple evidence chunks (see
    _evaluate_citations's docstring for the two formulas). This
    calibration validates the SIMILARITY SCORING is sound and the
    threshold is well-separated, not that precision and coverage behave
    identically at multi-item scale -- that would need a differently
    constructed dataset (multiple citations/evidence per case) to test
    directly. Same standing caveats as groundedness/relevance/
    correctness apply otherwise: n=29, single corpus, one
    negative-construction strategy -- a real signal, not a guess, but
    not a substitute for recalibrating against production data.

    Also still true regardless of this recalibration: enforce_citations
    defaults to False, and _gate_final (agents/runtime/continuation.py)
    never passes citations= to evaluate() in the live path today, so
    citation_precision/coverage are computed (as 0.0, 0.0 -- no
    citations supplied) but do not currently gate anything in
    production. This calibration makes the threshold meaningful for
    whenever that changes, not retroactively live today.

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
    min_citation_precision: float = 0.80
    min_citation_coverage: float = 0.80
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


@dataclass(frozen=True, slots=True)
class AnswerEvaluationSummary:
    """
    The two AnswerEvaluationResult fields the compliance log needs
    (application/services/compliance_log.py's AGENT_DECISION event),
    threaded up from AgentContinuationService._gate_final through
    AgentContinuationResult -> AgentExecutionNode -> AgentResponseMapper
    -> AgentResponseDTO.metadata.

    Deliberately narrow: not a general "expose all evaluation
    internals" carrier, just groundedness/relevance, and only ever
    populated at the one point _gate_final actually accepts a FINAL
    answer (is_sufficient() returned True) -- every other _gate_final
    return path (no answer, budget exhausted, insufficient + retrying)
    has no accepted evaluation to report and carries None instead.
    """

    groundedness: float | None
    relevance: float | None


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
    ) -> AnswerEvaluationResult:
        # All five checks are independent given the same inputs -- none
        # reads another's result -- so they run concurrently rather
        # than one after another. This matters most for groundedness,
        # the one real network round trip (an LLM judge call);
        # relevance/completeness/correctness/citations are local
        # embedding math and would otherwise sit idle waiting for it.
        # Gathering all five means groundedness's latency is hidden
        # behind the others instead of adding to them.
        (
            groundedness_detail,
            relevance,
            completeness,
            correctness,
            (citation_precision, citation_coverage),
        ) = await asyncio.gather(
            self._evaluate_groundedness(
                question=question,
                answer=answer,
                evidence=evidence,
            ),
            self._evaluate_relevance(
                question=question,
                answer=answer,
            ),
            self._evaluate_completeness(
                question=question,
                answer=answer,
                evidence=evidence,
            ),
            self._maybe_correctness(
                answer=answer,
                reference_answer=reference_answer,
            ),
            self._evaluate_citations(
                citations=citations,
                evidence=evidence,
            ),
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

    async def _maybe_correctness(
        self,
        *,
        answer: str,
        reference_answer: str | None,
    ) -> float | None:
        """
        Wraps the reference_answer is not None conditional in an
        always-awaitable so it can sit alongside the other four checks
        in evaluate()'s asyncio.gather() -- gather needs a real
        coroutine for every position, not a plain None.
        """

        if reference_answer is None:
            return None
        return await self._similarity(answer, reference_answer)

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

    async def _evaluate_citations(
        self,
        *,
        citations: Sequence[str],
        evidence: Sequence[str],
    ) -> tuple[float, float]:
        """
        Continuous precision/coverage over cited text vs relevant
        (evidence) chunks, via embedding similarity -- not exact
        string/identifier set-membership.

        Redesigned from the original metric, which compared opaque
        citation/source IDENTIFIER strings for exact membership,
        producing only the extremes 0.0/1.0 whenever a case cited
        exactly one source (the common shape) -- confirmed via
        calibrate_answer_quality_thresholds.py's sanity check before
        this change. That made "how good is this citation" an
        unanswerable question for anything short of a perfect or
        totally-wrong match: citing the right document but the wrong
        paragraph scored identically to fabricating a citation outright.

        precision: for each citation, its similarity to the
        BEST-matching evidence chunk, averaged across citations. A
        citation that closely echoes real evidence scores near 1.0; a
        fabricated or tangential one scores low in proportion to how
        far it drifts from anything actually retrieved, rather than a
        flat 0.0 for "not an exact match."

        coverage: for each evidence chunk, its similarity to the
        BEST-matching citation, averaged across evidence. Citing 1 of
        5 equally-relevant chunks now scores partway, not "did any
        expected source appear at all."

        citations are expected to be the actual cited TEXT (e.g.
        CitationDTO.snippet), not source identifiers -- there is
        nothing left here to compare an identifier against.
        """

        if not evidence or not citations:
            # No evidence means citation quality is not demonstrable;
            # no citations means there is nothing to score.
            return (0.0, 0.0)

        citation_scores = [
            max([await self._similarity(citation, chunk) for chunk in evidence])
            for citation in citations
        ]
        precision = sum(citation_scores) / len(citation_scores)

        evidence_scores = [
            max([await self._similarity(chunk, citation) for citation in citations])
            for chunk in evidence
        ]
        coverage = sum(evidence_scores) / len(evidence_scores)

        return precision, coverage
