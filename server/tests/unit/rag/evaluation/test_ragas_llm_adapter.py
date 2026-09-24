"""
Tests for the Judge -> ragas BaseRagasLLM adapter, against the real
installed ragas (not a mock) so a ragas upgrade that changes the
BaseRagasLLM contract -- e.g. 0.4 making is_finished abstract -- fails
here rather than at eval time.
"""

from __future__ import annotations

import pytest
from langchain_core.prompt_values import StringPromptValue

from rag.evaluation.ragas_llm_adapter import build_judge_ragas_llm


async def _judge(prompt: str) -> str:
    return f"echo: {prompt}"


def test_adapter_instantiates_against_installed_ragas() -> None:
    llm = build_judge_ragas_llm(judge=_judge)

    from ragas.llms.base import BaseRagasLLM

    assert isinstance(llm, BaseRagasLLM)


async def test_agenerate_text_returns_judge_output_n_times() -> None:
    llm = build_judge_ragas_llm(judge=_judge)

    result = await llm.agenerate_text(StringPromptValue(text="hi"), n=2)

    assert [g.text for g in result.generations[0]] == ["echo: hi", "echo: hi"]


async def test_is_finished_is_true_so_ragas_does_not_reject_output() -> None:
    llm = build_judge_ragas_llm(judge=_judge)

    result = await llm.agenerate_text(StringPromptValue(text="hi"))

    assert llm.is_finished(result) is True


async def test_generate_passes_through_ragas_finished_check() -> None:
    llm = build_judge_ragas_llm(judge=_judge)

    result = await llm.generate(StringPromptValue(text="hi"))

    assert result.generations[0][0].text == "echo: hi"


def test_sync_generate_text_is_unsupported() -> None:
    llm = build_judge_ragas_llm(judge=_judge)

    with pytest.raises(NotImplementedError):
        llm.generate_text(StringPromptValue(text="hi"))
