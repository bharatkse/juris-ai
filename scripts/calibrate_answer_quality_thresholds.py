"""
Empirical calibration for AnswerQualityPolicy's groundedness/relevance
thresholds -- the same "calibrate against the dataset's real achievable
signal" approach already used for rag.evaluation.metrics.PrecisionAtK.

Builds a small labeled set from the RAG golden dataset:
    positives -- query + that case's OWN expected_evidence, formatted
        as an answer (a genuinely grounded, relevant answer).
    negatives -- the SAME query paired with a DIFFERENT case's
        expected_evidence (an answer unsupported by what's actually
        retrieved for that question -- simulates a hallucinated/
        mismatched answer without needing a model to generate one).

Scores both groups with the real AnswerEvaluator (real embeddings,
real configured FaithfulnessBackend -- this makes a live LLM call per
groundedness check, so this script has real latency/cost; it is not
part of the test suite and is not run in CI).

Run: PYTHONPATH=src python scripts/calibrate_answer_quality_thresholds.py
"""

from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from agentic.evaluation.answer import AnswerEvaluator
from config.settings import get_settings
from wiring.factories.evaluation import build_faithfulness_backend

DATASET_PATH = Path("tests/datasets/rag/evaluation/legal_retrieval_gold_v1.json")
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RANDOM_SEED = 42

CANDIDATE_THRESHOLDS = [round(x * 0.05, 2) for x in range(2, 20)]


def _build_similarity(model: SentenceTransformer):
    async def similarity(a: str, b: str) -> float:
        vector_a, vector_b = model.encode([a, b], normalize_embeddings=True)
        return float(np.dot(vector_a, vector_b))

    return similarity


def _build_examples(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    rng = random.Random(RANDOM_SEED)
    positives = []
    negatives = []

    for case in cases:
        query = case["query"]
        evidence_text = case["expected_evidence"][0]
        section = case.get("section", "")

        # Positive: answer built from the case's OWN evidence. NOTE:
        # appending "(Section X)" makes this a two-claim answer for
        # groundedness purposes -- the section citation itself often
        # isn't independently verifiable against the bare evidence
        # snippet, which is why positives cluster at ~0.5 rather than
        # ~1.0 below. That's an artifact of this construction, not
        # evidence the underlying fact is ungrounded.
        answer = f"{evidence_text} (Section {section})." if section else f"{evidence_text}."
        positives.append(
            {
                "id": case["id"],
                "query": query,
                "answer": answer,
                "evidence": (evidence_text,),
                # "Gold reference" for correctness calibration: the bare
                # evidence text, distinct from `answer` (which adds the
                # section suffix) so comparing them is a real similarity
                # judgment, not comparing a string to itself.
                "reference_answer": evidence_text,
                "expected_source": case["expected_sources"][0],
            }
        )

        # Negative: same query, a DIFFERENT case's evidence/answer.
        other = rng.choice([c for c in cases if c["id"] != case["id"]])
        other_evidence = other["expected_evidence"][0]
        wrong_answer = f"{other_evidence} (Section {other.get('section', '')})."
        negatives.append(
            {
                "id": case["id"],
                "query": query,
                "answer": wrong_answer,
                "evidence": (evidence_text,),
                # Correctness negative: compared against THIS case's own
                # reference (not the other case's) -- a mismatched answer
                # judged against the right question's gold answer.
                "reference_answer": evidence_text,
                "expected_source": case["expected_sources"][0],
                "wrong_source": other["expected_sources"][0],
            }
        )

    return positives, negatives


def _stats(name: str, values: list[float]) -> list[float]:
    values = sorted(values)
    n = len(values)
    print(
        f"{name}: n={n} min={values[0]:.3f} p25={values[n // 4]:.3f} "
        f"median={values[n // 2]:.3f} p75={values[3 * n // 4]:.3f} "
        f"max={values[-1]:.3f} mean={sum(values) / n:.3f}"
    )
    return values


def _sweep(name: str, pos_values: list[float], neg_values: list[float]) -> tuple[float, float]:
    print(f"\n--- {name} threshold sweep ---")
    best = (0.0, -1.0)

    for threshold in CANDIDATE_THRESHOLDS:
        true_positive = sum(1 for v in pos_values if v >= threshold)
        true_negative = sum(1 for v in neg_values if v < threshold)
        accuracy = (true_positive + true_negative) / (len(pos_values) + len(neg_values))

        if accuracy > best[1]:
            best = (threshold, accuracy)

        if threshold in (0.5, 0.6, 0.65, 0.7, 0.75, 0.8):
            print(
                f"  t={threshold:.2f} tp={true_positive}/{len(pos_values)} "
                f"tn={true_negative}/{len(neg_values)} acc={accuracy:.3f}"
            )

    print(f"  BEST: t={best[0]:.2f} acc={best[1]:.3f}")
    return best


async def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text())
    cases = dataset["cases"]

    settings = get_settings()
    faithfulness_backend = build_faithfulness_backend(settings=settings)

    model = SentenceTransformer(EMBEDDING_MODEL)
    evaluator = AnswerEvaluator(
        similarity=_build_similarity(model),
        faithfulness_backend=faithfulness_backend,
    )

    positives, negatives = _build_examples(cases)

    async def run(items: list[dict]) -> list:
        return [
            await evaluator.evaluate(
                question=item["query"],
                answer=item["answer"],
                evidence=item["evidence"],
                reference_answer=item["reference_answer"],
            )
            for item in items
        ]

    pos_results = await run(positives)
    neg_results = await run(negatives)

    print("=== GROUNDEDNESS ===")
    pos_groundedness = _stats("positives", [r.groundedness for r in pos_results])
    neg_groundedness = _stats("negatives", [r.groundedness for r in neg_results])

    print("\n=== RELEVANCE ===")
    pos_relevance = _stats("positives", [r.relevance for r in pos_results])
    neg_relevance = _stats("negatives", [r.relevance for r in neg_results])

    print("\n=== CORRECTNESS (candidate answer vs. this case's own gold reference) ===")
    pos_correctness = _stats("positives", [r.correctness for r in pos_results])
    neg_correctness = _stats("negatives", [r.correctness for r in neg_results])

    _sweep("groundedness", pos_groundedness, neg_groundedness)
    _sweep("relevance", pos_relevance, neg_relevance)
    _sweep("correctness", pos_correctness, neg_correctness)

    print(
        "\n=== CITATIONS (precision/coverage) -- sanity check, NOT an empirical " "calibration ==="
    )
    print(
        "_evaluate_citations is exact set-membership (a citation either is or "
        "isn't in the source set), not a continuous similarity score -- there is "
        "no overlapping distribution to sweep a separating threshold over the "
        "way groundedness/relevance/correctness have. What follows only confirms "
        "the metric produces the expected 0.0/1.0 extremes; the actual threshold "
        "stays a policy choice (how much imperfect citing to tolerate), not "
        "something this dataset can empirically discover."
    )

    correct_citation = evaluator._evaluate_citations(
        citations=[positives[0]["expected_source"]],
        citation_sources=[positives[0]["expected_source"]],
        evidence=positives[0]["evidence"],
    )
    wrong_citation = evaluator._evaluate_citations(
        citations=[negatives[0]["wrong_source"]],
        citation_sources=[negatives[0]["expected_source"]],
        evidence=negatives[0]["evidence"],
    )
    print(f"  correct citation -> precision/coverage = {correct_citation}")
    print(f"  wrong citation   -> precision/coverage = {wrong_citation}")


if __name__ == "__main__":
    asyncio.run(main())
