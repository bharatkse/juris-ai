"""
Unit tests: the golden retrieval datasets' shape (Phase 4, P4-RV).

v1 is the gating dataset and stays as it is. v2 holds every v1 query plus
cases worded in plain language ("paraphrase") and wider coverage, and
corrects v1 evidence strings that occur in no indexed chunk.
"""

from __future__ import annotations

import json
from pathlib import Path

from rag.evaluation.datasets.loader import GoldenDatasetLoader

DATASETS = Path(__file__).resolve().parents[3] / "datasets" / "rag" / "evaluation"
V1 = DATASETS / "legal_retrieval_gold_v1.json"
V2 = DATASETS / "legal_retrieval_gold_v2.json"


def _cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def test_v2_loads_and_has_60_cases() -> None:
    dataset = GoldenDatasetLoader().load(path=V2)

    assert dataset.name == "legal-retrieval-gold-v2"
    assert dataset.size == 60


def test_every_v2_case_is_complete_and_labelled() -> None:
    cases = _cases(V2)

    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        assert case["query"].strip()
        assert case["expected_evidence"] and all(e.strip() for e in case["expected_evidence"])
        assert case["expected_sources"]
        assert case["style"] in {"statutory", "paraphrase"}


def test_v2_keeps_every_v1_query() -> None:
    v2 = {case["id"]: case for case in _cases(V2)}

    for case in _cases(V1):
        assert v2[case["id"]]["query"] == case["query"]


def test_both_styles_are_well_represented() -> None:
    styles = [case["style"] for case in _cases(V2)]

    assert styles.count("paraphrase") >= 15
    assert styles.count("statutory") >= 30
