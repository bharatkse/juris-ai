"""
Golden dataset loader for RAG evaluation.

Loads evaluation cases from a persisted dataset representation and
converts them into the RAG evaluation domain model.

The loader does not:

    - execute evaluations
    - calculate metrics
    - call an LLM
    - depend on Ragas
    - perform retrieval
    - generate embeddings
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.exceptions.rag import RAGError
from rag.evaluation.datasets.golden_dataset import GoldenDataset
from rag.evaluation.models.evaluation_case import EvaluationCase


class GoldenDatasetLoader:
    """
    Load golden RAG evaluation datasets from JSON files.
    """

    def load(
        self,
        *,
        path: str | Path,
    ) -> GoldenDataset:
        """
        Load a golden dataset from a JSON file.

        Expected structure:

            {
                "name": "legal-rag-v1",
                "metadata": {
                    "version": "1"
                },
                "cases": [
                    {
                        "query": "...",
                        "answer": "...",
                        "expected_sources": [
                            "it_act_2000.pdf"
                        ],
                        "expected_evidence": [
                            "..."
                        ],
                        "reference_answer": "...",
                        "reference_contexts": [
                            "..."
                        ]
                    }
                ]
            }

        Returns:
            Parsed GoldenDataset.

        Raises:
            RAGError:
                If the dataset cannot be loaded or contains invalid
                evaluation data.
        """

        dataset_path = Path(path)

        try:
            with dataset_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                payload: Any = json.load(file)

        except (OSError, json.JSONDecodeError) as exc:
            raise RAGError(
                message=f"Failed to load golden dataset '{dataset_path}'.",
            ) from exc

        try:
            if not isinstance(payload, dict):
                raise ValueError("Dataset payload must be an object.")

            name = payload["name"]
            cases_payload = payload["cases"]

            if not isinstance(name, str) or not name.strip():
                raise ValueError(
                    "Dataset name must be a non-empty string.",
                )

            if not isinstance(cases_payload, list):
                raise ValueError(
                    "Dataset cases must be a list.",
                )

            cases: list[EvaluationCase] = []

            for case in cases_payload:
                if not isinstance(case, dict):
                    raise ValueError(
                        "Each evaluation case must be an object.",
                    )

                query = case["query"]
                answer = case.get("answer", "")

                expected_sources = case.get(
                    "expected_sources",
                    [],
                )

                expected_evidence = case.get(
                    "expected_evidence",
                    [],
                )

                reference_answer = case.get(
                    "reference_answer",
                )

                reference_contexts = case.get(
                    "reference_contexts",
                )

                if not isinstance(query, str) or not query.strip():
                    raise ValueError(
                        "Evaluation case query must be a non-empty string.",
                    )

                if not isinstance(answer, str):
                    raise ValueError(
                        "Evaluation case answer must be a string.",
                    )

                if not isinstance(expected_sources, list):
                    raise ValueError(
                        "Evaluation case expected_sources must be a list.",
                    )

                if not isinstance(expected_evidence, list):
                    raise ValueError(
                        "Evaluation case expected_evidence must be a list.",
                    )

                if reference_answer is not None and not isinstance(
                    reference_answer,
                    str,
                ):
                    raise ValueError(
                        "Evaluation case reference_answer must be a string.",
                    )

                if reference_contexts is not None and not isinstance(
                    reference_contexts,
                    list,
                ):
                    raise ValueError(
                        "Evaluation case reference_contexts must be a list.",
                    )

                cases.append(
                    EvaluationCase(
                        query=query,
                        answer=answer,
                        expected_sources=[str(source) for source in expected_sources],
                        expected_evidence=[str(evidence) for evidence in expected_evidence],
                        reference_answer=reference_answer,
                        reference_contexts=reference_contexts,
                    ),
                )

            metadata = payload.get(
                "metadata",
                {},
            )

            if not isinstance(metadata, dict):
                raise ValueError(
                    "Dataset metadata must be an object.",
                )

        except (KeyError, TypeError, ValueError) as exc:
            raise RAGError(
                message=f"Invalid golden dataset '{dataset_path}'.",
            ) from exc

        return GoldenDataset(
            name=name,
            cases=cases,
            metadata={str(key): str(value) for key, value in metadata.items()},
        )
