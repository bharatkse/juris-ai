"""
RAG evaluation metrics — LLM-as-judge implementations.

Four standard RAG metrics (RAGAS terminology, industry standard for
RAG evaluation):

- Faithfulness: does the generated answer only state claims
  supported by the retrieved context? (catches hallucination)
- Answer Relevancy: does the answer actually address the question
  asked? (catches on-topic-but-non-answering responses)
- Context Precision: of the retrieved chunks, how many were actually
  relevant/used? (measures retrieval noise)
- Context Recall: of the information needed to answer, how much was
  present in the retrieved context? (measures retrieval completeness
  — requires a ground-truth answer, so only computable offline
  against a labeled eval set, not in production)

These implementations use the LOCAL LLM as judge — evaluation is
exactly the "low-priority, non-authorization" task category already
routed to local inference elsewhere in this project (planner routing,
search classification). Cheap enough to sample in production; for
rigorous offline regression testing against a golden dataset, use
rag/evaluation/ragas_offline.py instead, which uses the `ragas`
library's more thoroughly validated metric implementations and can
afford the paid model's accuracy since it's not per-request.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

from src.clients.resolver import LLMResolver
from src.core.enums import LLMProviderEnum
from src.core.logger import get_logger

log = get_logger(__name__)

_JSON_BLOCK_REGEX = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True, slots=True)
class RAGEvalResult:
    faithfulness: float | None
    answer_relevancy: float | None
    context_precision: float | None
    context_recall: float | None  # None unless ground_truth is provided

    def has_quality_concern(self, *, threshold: float = 0.6) -> bool:
        """
        Convenience check for alerting: True if any computed metric
        fell below threshold.
        """

        scores = [
            s
            for s in (self.faithfulness, self.answer_relevancy, self.context_precision)
            if s is not None
        ]

        return any(s < threshold for s in scores)


_FAITHFULNESS_PROMPT = """Given the context and the answer, determine what fraction \
of claims in the answer are directly supported by the context.

Context:
{context}

Answer:
{answer}

Respond with only a JSON object: {{"score": <float 0.0-1.0>, "unsupported_claims": [<string>, ...]}}"""

_ANSWER_RELEVANCY_PROMPT = """Given the question and the answer, score how directly \
the answer addresses the question (ignore whether it's factually correct — that's a
separate concern).

Question:
{question}

Answer:
{answer}

Respond with only a JSON object: {{"score": <float 0.0-1.0>}}"""

_CONTEXT_PRECISION_PROMPT = """Given the question and a retrieved context chunk, \
determine whether the chunk is relevant to answering the question.

Question:
{question}

Chunk:
{chunk}

Respond with only a JSON object: {{"relevant": <true/false>}}"""

_CONTEXT_RECALL_PROMPT = """Given the ground-truth answer and the retrieved context, \
determine what fraction of the information in the ground truth is present somewhere
in the context.

Ground truth:
{ground_truth}

Context:
{context}

Respond with only a JSON object: {{"score": <float 0.0-1.0>}}"""


class RAGEvaluator:
    """
    LLM-as-judge RAG evaluator, using the local model.
    """

    def __init__(self, *, llm_resolver: LLMResolver) -> None:
        self._llm_resolver = llm_resolver

    @staticmethod
    def _validate_score(val: object) -> float | None:
        if val is None:
            return None
        try:
            score = float(val)  # type: ignore[arg-type]
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError):
            return None

    async def _judge(self, *, prompt: str) -> dict:
        client = self._llm_resolver.get(LLMProviderEnum.LOCAL)
        try:
            response = await client.complete(prompt=prompt, max_tokens=200)
            cleaned = response.strip()
            match = _JSON_BLOCK_REGEX.search(cleaned)
            json_str = match.group(0) if match else cleaned
            return json.loads(json_str)
        except Exception:
            log.exception("RAG evaluator judge call failed or returned invalid JSON.")
            return {}

    async def faithfulness(self, *, context: str, answer: str) -> float | None:
        result = await self._judge(
            prompt=_FAITHFULNESS_PROMPT.format(context=context, answer=answer)
        )
        return self._validate_score(result.get("score"))

    async def answer_relevancy(self, *, question: str, answer: str) -> float | None:
        result = await self._judge(
            prompt=_ANSWER_RELEVANCY_PROMPT.format(question=question, answer=answer)
        )
        return self._validate_score(result.get("score"))

    async def context_precision(self, *, question: str, chunks: list[str]) -> float | None:
        if not chunks:
            return None

        tasks = [
            self._judge(prompt=_CONTEXT_PRECISION_PROMPT.format(question=question, chunk=chunk))
            for chunk in chunks
        ]
        results = await asyncio.gather(*tasks)

        valid_evals = [r for r in results if "relevant" in r]
        if not valid_evals:
            return None

        relevant_count = sum(1 for r in valid_evals if r.get("relevant") is True)
        return relevant_count / len(valid_evals)

    async def context_recall(self, *, ground_truth: str, context: str) -> float | None:
        result = await self._judge(
            prompt=_CONTEXT_RECALL_PROMPT.format(ground_truth=ground_truth, context=context)
        )
        return self._validate_score(result.get("score"))

    async def evaluate(
        self,
        *,
        question: str,
        answer: str,
        retrieved_chunks: list[str],
        ground_truth: str | None = None,
    ) -> RAGEvalResult:
        """
        Runs all applicable metrics. context_recall only runs if
        ground_truth is supplied (production requests won't have
        one; offline eval-set runs will).
        """

        context = "\n\n".join(retrieved_chunks)

        recall_task = (
            self.context_recall(ground_truth=ground_truth, context=context)
            if ground_truth
            else asyncio.sleep(0, result=None)
        )

        faithfulness, relevancy, precision, recall = await asyncio.gather(
            self.faithfulness(context=context, answer=answer),
            self.answer_relevancy(question=question, answer=answer),
            self.context_precision(question=question, chunks=retrieved_chunks),
            recall_task,
        )

        return RAGEvalResult(
            faithfulness=faithfulness,
            answer_relevancy=relevancy,
            context_precision=precision,
            context_recall=recall,
        )
