import json

import pytest

from core.exceptions.rag import RAGError
from rag.evaluation.datasets.golden_dataset import GoldenDataset
from rag.evaluation.datasets.loader import GoldenDatasetLoader
from rag.evaluation.models.evaluation_case import EvaluationCase


def test_golden_dataset_reports_size() -> None:
    dataset = GoldenDataset(
        name="legal-retrieval",
        cases=[
            EvaluationCase(
                query="What is consideration?",
                answer="Something of value exchanged between parties.",
            ),
            EvaluationCase(
                query="What is breach of contract?",
                answer="Failure to perform a contractual obligation.",
            ),
        ],
    )

    assert dataset.size == 2


def test_golden_dataset_defaults_to_empty_cases() -> None:
    dataset = GoldenDataset(name="empty")

    assert dataset.size == 0
    assert dataset.cases == []


def test_loader_reads_golden_dataset(tmp_path) -> None:
    dataset_path = tmp_path / "golden.json"

    dataset_path.write_text(
        json.dumps(
            {
                "name": "legal-retrieval",
                "metadata": {
                    "domain": "contract-law",
                },
                "cases": [
                    {
                        "query": "What is consideration?",
                        "answer": "Something of value exchanged between parties.",
                        "expected_sources": ["contract-law"],
                        "expected_evidence": ["something of value exchanged between parties"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    dataset = GoldenDatasetLoader().load(path=dataset_path)

    assert dataset.name == "legal-retrieval"
    assert dataset.size == 1
    assert dataset.metadata["domain"] == "contract-law"

    case = dataset.cases[0]
    assert case.query == "What is consideration?"
    assert case.answer == "Something of value exchanged between parties."
    assert case.expected_sources == ["contract-law"]
    assert case.expected_evidence == ["something of value exchanged between parties"]


def test_loader_preserves_reference_fields(tmp_path) -> None:
    dataset_path = tmp_path / "golden.json"

    dataset_path.write_text(
        json.dumps(
            {
                "name": "legal-retrieval",
                "cases": [
                    {
                        "query": "What is consideration?",
                        "answer": "Consideration is required for a valid contract.",
                        "reference_answer": (
                            "Consideration is something of value exchanged "
                            "between contracting parties."
                        ),
                        "reference_contexts": ["Consideration must have legal value."],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    dataset = GoldenDatasetLoader().load(path=dataset_path)

    case = dataset.cases[0]

    assert case.reference_answer == (
        "Consideration is something of value exchanged " "between contracting parties."
    )
    assert case.reference_contexts == ["Consideration must have legal value."]


def test_loader_raises_for_missing_file(tmp_path) -> None:
    missing_path = tmp_path / "missing.json"

    with pytest.raises(RAGError, match="Failed to load golden dataset"):
        GoldenDatasetLoader().load(path=missing_path)
