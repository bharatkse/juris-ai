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


# ---------------------------------------------------------------------------
# Per-request token quota (review R3): checked before each call
# ---------------------------------------------------------------------------


def _one_token_per_char(text: str) -> int:
    return len(text)


def test_without_a_quota_every_call_is_allowed() -> None:
    from core.usage import check_request_token_quota

    check_request_token_quota(["x" * 10_000])  # outside a scope

    with usage_scope(estimate_tokens=_one_token_per_char) as meter:
        check_request_token_quota(["x" * 10_000])

    assert meter.quota is None
    assert meter.refused is None


def test_a_call_within_the_quota_is_allowed() -> None:
    from core.usage import check_request_token_quota, request_token_quota

    with request_token_quota(100), usage_scope(estimate_tokens=_one_token_per_char) as meter:
        _record(40, 10)
        check_request_token_quota(["x" * 30, "y" * 20])  # 50 used + 50 = 100

    assert meter.quota == 100
    assert meter.refused is None


def test_a_call_that_would_cross_the_quota_is_refused_before_it_is_made() -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import check_request_token_quota, request_token_quota

    with request_token_quota(100), usage_scope(estimate_tokens=_one_token_per_char) as meter:
        _record(40, 10)

        with pytest.raises(RequestTokenQuotaExceededError) as raised:
            check_request_token_quota(["x" * 51])

    error = raised.value
    assert (error.quota, error.used, error.requested) == (100, 50, 51)
    assert (error.prompt_tokens, error.completion_tokens) == (40, 10)
    assert error.status_code == 413
    assert error.error_code == "REQUEST_TOKEN_QUOTA_EXCEEDED"
    assert meter.refused is not None
    # Nothing was recorded for the refused call.
    assert meter.calls == 1


def test_after_one_refusal_every_later_call_is_refused() -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import check_request_token_quota, request_token_quota

    with request_token_quota(10), usage_scope(estimate_tokens=_one_token_per_char):
        with pytest.raises(RequestTokenQuotaExceededError):
            check_request_token_quota(["x" * 11])

        with pytest.raises(RequestTokenQuotaExceededError):
            check_request_token_quota(["x"])


def test_the_quota_error_carries_usage_recorded_after_the_refusal() -> None:
    """A parallel call already in flight may finish after the refusal."""

    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import check_request_token_quota, request_token_quota

    with request_token_quota(10), usage_scope(estimate_tokens=_one_token_per_char) as meter:
        with pytest.raises(RequestTokenQuotaExceededError):
            check_request_token_quota(["x" * 11])
        _record(7, 3)

    assert (meter.quota_error().prompt_tokens, meter.quota_error().completion_tokens) == (7, 3)


def test_the_quota_applies_only_to_scopes_opened_inside_it() -> None:
    from core.usage import request_token_quota

    with request_token_quota(100):
        with usage_scope() as capped:
            pass
        with request_token_quota(None), usage_scope() as uncapped_inside:
            pass

    with usage_scope() as after:
        pass

    assert capped.quota == 100
    assert uncapped_inside.quota is None
    assert after.quota is None


def test_without_an_estimator_prompts_are_sized_at_four_characters_per_token() -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import check_request_token_quota, request_token_quota

    with request_token_quota(10), usage_scope():
        check_request_token_quota(["x" * 40])  # 10 tokens

        with pytest.raises(RequestTokenQuotaExceededError):
            check_request_token_quota(["x" * 41])


def test_a_tally_collects_every_scope_however_it_closes() -> None:
    """R19: a scope that raised still adds its calls to the tally."""

    from core.usage import usage_tally

    with usage_tally() as tally:
        with usage_scope():
            record_llm_usage(
                provider="groq", model="m", prompt_tokens=10, completion_tokens=2, total_tokens=12
            )

        with pytest.raises(RuntimeError), usage_scope():
            record_llm_usage(
                provider="local", model="q", prompt_tokens=5, completion_tokens=1, total_tokens=6
            )
            raise RuntimeError("failed after a call")

    assert (tally.prompt_tokens, tally.completion_tokens, tally.calls) == (15, 3, 2)
    assert tally.providers == {"groq", "local"}

    # Outside the block, scopes report to no tally.
    with usage_scope():
        record_llm_usage(
            provider="groq", model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2
        )
    assert tally.calls == 2


def test_scopes_under_one_request_quota_share_it() -> None:
    """
    G1: summarization runs in its own scope before the orchestrator's;
    the request's quota covers both, so the second scope starts from the
    tokens the first one spent.
    """

    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import check_request_token_quota, request_token_quota

    with request_token_quota(100):
        with usage_scope(estimate_tokens=_one_token_per_char):
            _record(50, 10)  # summarization: 60 tokens

        with usage_scope(estimate_tokens=_one_token_per_char) as second:
            check_request_token_quota(["x" * 40])  # 60 + 40 = 100: allowed

            with pytest.raises(RequestTokenQuotaExceededError) as raised:
                check_request_token_quota(["x" * 41])

    assert (raised.value.quota, raised.value.used, raised.value.requested) == (100, 60, 41)
    assert second.refused is not None


def test_a_refusal_in_one_scope_refuses_later_scopes_of_the_same_request() -> None:
    from core.exceptions.rate_limit import RequestTokenQuotaExceededError
    from core.usage import check_request_token_quota, request_token_quota

    with request_token_quota(10):
        with (
            usage_scope(estimate_tokens=_one_token_per_char),
            pytest.raises(RequestTokenQuotaExceededError),
        ):
            check_request_token_quota(["x" * 11])

        with usage_scope(estimate_tokens=_one_token_per_char) as later:
            with pytest.raises(RequestTokenQuotaExceededError):
                check_request_token_quota(["x"])

    assert later.refused is not None


def test_separate_requests_do_not_share_a_quota() -> None:
    from core.usage import check_request_token_quota, request_token_quota

    with request_token_quota(100), usage_scope(estimate_tokens=_one_token_per_char):
        _record(90, 0)

    with request_token_quota(100), usage_scope(estimate_tokens=_one_token_per_char) as meter:
        check_request_token_quota(["x" * 100])

    assert meter.refused is None
