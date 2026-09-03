"""
Offline retrieval evaluation runner.

Executes a golden retrieval dataset against the configured RAG
retriever and aggregates the resulting metric evaluations.

This module is evaluation orchestration only.

It does not:

    - modify the production retriever
    - implement retrieval
    - calculate retrieval metrics
    - call an LLM
    - access persistence directly
"""

from __future__ import annotations

from dataclasses import replace

from rag.evaluation.datasets.golden_dataset import GoldenDataset
from rag.evaluation.models.evaluation_case import EvaluationCase
from rag.evaluation.models.retrieval_report import RetrievalEvaluationReport
from rag.evaluation.protocols.retriever import RetrieverProtocol
from rag.evaluation.retrieval_evaluator import RetrievalEvaluator


class RetrievalEvaluationRunner:
    """
    Execute offline retrieval evaluation over a golden dataset.
    """

    def __init__(
        self,
        *,
        retriever: RetrieverProtocol,
        evaluator: RetrievalEvaluator,
        top_k: int = 5,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        self._retriever = retriever
        self._evaluator = evaluator
        self._top_k = top_k

    async def evaluate(
        self,
        *,
        dataset: GoldenDataset,
    ) -> RetrievalEvaluationReport:
        """
        Evaluate every case in the golden dataset.

        Retrieval is executed using the production retriever.
        The retrieved results are attached to a copy of the original
        evaluation case and passed to RetrievalEvaluator.
        """

        results = []

        for case in dataset.cases:
            evaluated_case = await self._evaluate_case(case)

            results.append(evaluated_case)

        return RetrievalEvaluationReport(
            results=results,
        )

    async def _evaluate_case(
        self,
        case: EvaluationCase,
    ):
        retrieval_results = await self._retriever.retrieve(
            query=case.query,
            top_k=self._top_k,
        )

        populated_case = replace(
            case,
            retrieval_results=retrieval_results,
        )

        return await self._evaluator.evaluate(
            case=populated_case,
        )
