"""
Unit tests for core.usage (the per-request token meter, review R3).
"""

from __future__ import annotations

import asyncio

import pytest

from core.usage import record_llm_usage, usage_scope


def _record(prompt: int, completion: int, *, provider: str = "groq", model: str = "m") -> None:
    record_llm_usage(
        provider=provider,
        model=model,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
    )


def test_recording_outside_a_scope_is_a_no_op() -> None:
    _record(10, 5)  # must not raise

    with usage_scope() as meter:
        pass

    assert meter.calls == 0


def test_a_scope_sums_every_call() -> None:
    with usage_scope() as meter:
        _record(100, 20)
        _record(50, 5)

    assert (meter.prompt_tokens, meter.completion_tokens, meter.total_tokens) == (150, 25, 175)
    assert meter.calls == 2


def test_provider_and_model_are_reported_only_when_all_calls_agree() -> None:
    with usage_scope() as same:
        _record(1, 1)
        _record(1, 1)

    with usage_scope() as mixed:
        _record(1, 1, provider="local", model="qwen3:8b")
        _record(1, 1, provider="groq", model="gpt-oss")

    assert (same.provider, same.model) == ("groq", "m")
    assert (mixed.provider, mixed.model) == (None, None)


@pytest.mark.asyncio
async def test_calls_in_tasks_created_inside_the_scope_are_counted() -> None:
    """LangGraph nodes and parallel plan steps run in child tasks."""

    async def step(prompt: int) -> None:
        await asyncio.sleep(0)
        _record(prompt, 1)

    with usage_scope() as meter:
        await asyncio.gather(step(10), step(20), step(30))

    assert meter.prompt_tokens == 60
    assert meter.calls == 3


def test_a_nested_scope_counts_separately_and_restores_the_outer_one() -> None:
    with usage_scope() as outer:
        _record(1, 0)
        with usage_scope() as inner:
            _record(10, 0)
        _record(2, 0)

    assert inner.prompt_tokens == 10
    assert outer.prompt_tokens == 3


def test_the_scope_is_closed_when_the_block_raises() -> None:
    with pytest.raises(RuntimeError), usage_scope() as meter:
        raise RuntimeError

    _record(5, 5)

    assert meter.calls == 0
