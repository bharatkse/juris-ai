"""
RAG evaluation metrics — LLM-as-judge implementation.

Evaluates RAG responses using an injected judge capability.

The evaluator is provider-independent. It does not know about:

    - concrete LLM providers
    - LLM provider enums
    - LLM client implementations
    - provider resolution
    - persistence
    - retrieval implementations
    - RAGAS

The composition/application layer is responsible for adapting the
configured LLM client into the judge callable expected here.

Metrics:

    - Faithfulness
    - Answer Relevancy
    - Context Precision
    - Context Recall

Context recall requires a ground-truth answer and is normally used
only for offline evaluation against a labeled evaluation dataset.

Production evaluation can run the other metrics without ground truth.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any

from adapters.observability.logger import get_logger
from rag.evaluation.models import RAGEvalResult

log = get_logger(__name__)

_JSON_BLOCK_REGEX = re.compile(
    r"\{.*\}",
    re.DOTALL,
)

Judge = Callable[
    [str],
    Awaitable[str],
]


_FAITHFULNESS_PROMPT = """Given the context and the answer, determine what fraction
of claims in the answer are directly supported by the context.

Context:
{context}

Answer:
{answer}

Respond with only a JSON object:
{{"score": <float 0.0-1.0>, "unsupported_claims": [<string>, ...]}}
"""


_ANSWER_RELEVANCY_PROMPT = """Given the question and the answer, score how directly
the answer addresses the question. Ignore whether it is factually correct;
that is a separate concern.

Question:
{question}

Answer:
{answer}

Respond with only a JSON object:
{{"score": <float 0.0-1.0>}}
"""


_CONTEXT_PRECISION_PROMPT = """Given the question and a retrieved context chunk,
determine whether the chunk is relevant to answering the question.

Question:
{question}

Chunk:
{chunk}

Respond with only a JSON object:
{{"relevant": <true/false>}}
"""


_CONTEXT_RECALL_PROMPT = """Given the ground-truth answer and the retrieved context,
determine what fraction of the information in the ground truth is present
somewhere in the context.

Ground truth:
{ground_truth}

Context:
{context}

Respond with only a JSON object:
{{"score": <float 0.0-1.0>}}
"""


class RAGEvaluator:
    """
    Provider-independent RAG evaluation using an injected judge.

    The evaluator only knows how to submit evaluation prompts to the
    injected judge and interpret the returned JSON.

    It does not:

        - select an LLM provider
        - resolve an LLM provider
        - know provider enums
        - instantiate an LLM client
        - perform retrieval
        - generate the application answer
        - access persistence
    """

    def __init__(
        self,
        *,
        judge: Judge,
    ) -> None:
        """
        Initialize the RAG evaluator.

        Args:
            judge:
                Injected evaluation-judge capability.

                Provider/client selection and adaptation happen outside
                the RAG evaluation module.
        """

        self._judge = judge

    @staticmethod
    def _validate_score(
        value: object,
    ) -> float | None:
        """
        Validate and normalize an LLM-produced metric score.

        Invalid values return None so evaluation failure does not fail
        the RAG request.
        """

        if value is None:
            return None

        try:
            score = float(value)  # type: ignore[arg-type]
        except (ValueError, TypeError):
            return None

        return max(
            0.0,
            min(1.0, score),
        )

    async def _evaluate_prompt(
        self,
        *,
        prompt: str,
    ) -> dict[str, Any]:
        """
        Execute one judge request and parse its JSON response.

        Evaluation failures are isolated from the RAG request.
        """

        try:
            response = await self._judge(prompt)

            cleaned = response.strip()

            match = _JSON_BLOCK_REGEX.search(cleaned)

            json_str = match.group(0) if match else cleaned

            result = json.loads(json_str)

            if not isinstance(result, dict):
                log.warning(
                    "RAG evaluator judge returned non-object JSON.",
                )
                return {}

            return result

        except Exception:
            log.exception(
                "RAG evaluator judge call failed or returned invalid JSON.",
            )
            return {}

    async def faithfulness(
        self,
        *,
        context: str,
        answer: str,
    ) -> float | None:
        """
        Evaluate whether answer claims are supported by the context.
        """

        result = await self._evaluate_prompt(
            prompt=_FAITHFULNESS_PROMPT.format(
                context=context,
                answer=answer,
            ),
        )

        return self._validate_score(
            result.get("score"),
        )

    async def answer_relevancy(
        self,
        *,
        question: str,
        answer: str,
    ) -> float | None:
        """
        Evaluate whether the answer directly addresses the question.
        """

        result = await self._evaluate_prompt(
            prompt=_ANSWER_RELEVANCY_PROMPT.format(
                question=question,
                answer=answer,
            ),
        )

        return self._validate_score(
            result.get("score"),
        )

    async def context_precision(
        self,
        *,
        question: str,
        chunks: list[str],
    ) -> float | None:
        """
        Evaluate the relevance of retrieved chunks to the question.

        Each retrieved chunk is independently judged.
        """

        if not chunks:
            return None

        results = await asyncio.gather(
            *(
                self._evaluate_prompt(
                    prompt=_CONTEXT_PRECISION_PROMPT.format(
                        question=question,
                        chunk=chunk,
                    ),
                )
                for chunk in chunks
            ),
        )

        valid_evals = [result for result in results if isinstance(result.get("relevant"), bool)]

        if not valid_evals:
            return None

        relevant_count = sum(1 for result in valid_evals if result["relevant"] is True)

        return relevant_count / len(valid_evals)

    async def context_recall(
        self,
        *,
        ground_truth: str,
        context: str,
    ) -> float | None:
        """
        Evaluate how much ground-truth information is present in the
        retrieved context.

        This metric requires a ground-truth answer.
        """

        result = await self._evaluate_prompt(
            prompt=_CONTEXT_RECALL_PROMPT.format(
                ground_truth=ground_truth,
                context=context,
            ),
        )

        return self._validate_score(
            result.get("score"),
        )

    async def evaluate(
        self,
        *,
        question: str,
        answer: str,
        retrieved_chunks: list[str],
        ground_truth: str | None = None,
    ) -> RAGEvalResult:
        """
        Run all applicable RAG evaluation metrics.

        Context recall is evaluated only when ground truth is provided.

        Evaluation failures produce unavailable metrics rather than
        propagating an exception into the RAG request.
        """

        context = "\n\n".join(retrieved_chunks)

        recall_task: Awaitable[float | None]

        if ground_truth:
            recall_task = self.context_recall(
                ground_truth=ground_truth,
                context=context,
            )
        else:
            recall_task = asyncio.sleep(
                0,
                result=None,
            )

        (
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall,
        ) = await asyncio.gather(
            self.faithfulness(
                context=context,
                answer=answer,
            ),
            self.answer_relevancy(
                question=question,
                answer=answer,
            ),
            self.context_precision(
                question=question,
                chunks=retrieved_chunks,
            ),
            recall_task,
        )

        return RAGEvalResult(
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            context_precision=context_precision,
            context_recall=context_recall,
        )
