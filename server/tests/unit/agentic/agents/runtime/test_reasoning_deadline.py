"""
The agent's reasoning call runs under the turn's deadline (core.deadline),
which is what lets FailoverLLMClient skip or cut short a slow fallback.
"""

from __future__ import annotations

import pytest

from core.deadline import deadline_within, remaining_seconds
from tests.unit.agentic.agents.runtime.test_delegation import PARENT_ANSWER, _final, _llm, _Runtime


def _recording_llm(seen: list[float | None]):
    llm = _llm()

    async def decide(**_kwargs):
        seen.append(remaining_seconds())
        return _final(PARENT_ANSWER)

    llm.generate_structured.side_effect = decide
    return llm


@pytest.mark.asyncio
async def test_the_reasoning_call_sees_the_turn_deadline() -> None:
    seen: list[float | None] = []
    runtime = _Runtime(legal=_recording_llm(seen), contract=_llm())

    handle, _ = await runtime.run_legal()

    (remaining,) = seen
    assert remaining is not None
    assert 0 < remaining <= handle.state.budget.max_execution_time_seconds


@pytest.mark.asyncio
async def test_an_earlier_outer_deadline_wins() -> None:
    seen: list[float | None] = []
    runtime = _Runtime(legal=_recording_llm(seen), contract=_llm())

    # e.g. the graph timeout, with little of it left.
    with deadline_within(5):
        await runtime.run_legal()

    (remaining,) = seen
    assert remaining is not None and remaining <= 5
