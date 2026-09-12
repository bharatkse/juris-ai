"""
Tests for RAGEvaluator (rag/evaluation/evaluator.py).

RAGEvaluator has no prior test coverage anywhere in this codebase --
confirmed by searching every import of it: only online_sampler.py
references it, and nothing calls online_sampler.py either. These
tests exercise the real prompt formatting, judge-response parsing
(including _JSON_BLOCK_REGEX extraction from a realistic,
non-pure-JSON judge response), and score validation/clamping
end-to-end -- not just a metric class's delegation to it.
"""

from __future__ import annotations

import pytest

from rag.evaluation.evaluator import RAGEvaluator


@pytest.mark.asyncio
async def test_faithfulness_extracts_score_from_realistic_judge_response() -> None:
    async def realistic_judge(prompt: str) -> str:
        assert "Context:" in prompt
        assert "Answer:" in prompt

        return (
            "Here is my assessment:\n"
            '```json\n{"score": 0.82, "unsupported_claims": ["exact filing date"]}\n```'
        )

    evaluator = RAGEvaluator(judge=realistic_judge)

    score = await evaluator.faithfulness(
        context=(
            "Section 27 of the Limitation Act, 1963 provides that the "
            "right to property is extinguished after twelve years of "
            "adverse possession."
        ),
        answer=(
            "Under Section 27 of the Limitation Act, property rights are "
            "extinguished after twelve years of adverse possession, "
            "effective from the exact filing date."
        ),
    )

    assert score == 0.82


@pytest.mark.asyncio
async def test_faithfulness_clamps_out_of_range_score() -> None:
    async def overconfident_judge(prompt: str) -> str:
        return '{"score": 1.4}'

    evaluator = RAGEvaluator(judge=overconfident_judge)

    score = await evaluator.faithfulness(
        context="The limitation period is three years.",
        answer="The limitation period is three years.",
    )

    assert score == 1.0


@pytest.mark.asyncio
async def test_faithfulness_returns_none_on_malformed_judge_response() -> None:
    async def broken_judge(prompt: str) -> str:
        return "I cannot compute a score for this request."

    evaluator = RAGEvaluator(judge=broken_judge)

    score = await evaluator.faithfulness(
        context="Some context.",
        answer="Some answer.",
    )

    assert score is None
