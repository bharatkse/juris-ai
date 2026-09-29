"""
Token usage of the LLM calls made in the current context.

The orchestrator needs one request's total token usage (it becomes the
response's usage, which feeds the user's daily token quota); the LLM
clients are the only place that sees each call's usage. This carries a
meter between them through a ContextVar, the same way core.deadline
carries the deadline, so neither layer imports the other.

The meter is one mutable object: asyncio tasks copy the context they are
created in, so LangGraph nodes and parallel plan steps add to the same
meter as the call that opened the scope.

The same meter enforces the per-request token quota
(RATE_LIMIT_REQUEST_TOKEN_QUOTA), the per-request counterpart of the
daily quota and enforced the same way: checked before tokens are spent,
counted after. ChatService sets the quota (request_token_quota()); the
scope opened inside it picks it up; every LLM call checks it before it
is made (check_request_token_quota(), from LLMClient.generate()).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from core.exceptions.rate_limit import RequestTokenQuotaExceededError

TokenEstimator = Callable[[str], int]


def _rough_token_estimate(text: str) -> int:
    """About four characters per token; for a scope opened without a tokenizer."""

    return math.ceil(len(text) / 4)


@dataclass(slots=True)
class UsageMeter:
    """Token counts summed over every LLM call made within one scope."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    providers: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    # Per-request token quota; None means no limit.
    quota: int | None = None
    estimate_tokens: TokenEstimator = _rough_token_estimate
    # The first refused call, once the quota has refused one.
    refused: RequestTokenQuotaExceededError | None = None

    def add(
        self,
        *,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> None:
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.calls += 1
        self.providers.add(provider)
        self.models.add(model)

    @property
    def provider(self) -> str | None:
        """The provider, when every call used the same one."""

        return next(iter(self.providers)) if len(self.providers) == 1 else None

    @property
    def model(self) -> str | None:
        """The model, when every call used the same one."""

        return next(iter(self.models)) if len(self.models) == 1 else None

    def check(self, prompt_texts: Iterable[str]) -> None:
        """
        Raise RequestTokenQuotaExceededError if a call with this prompt
        would take the scope past its quota.

        Only the prompt is known before a call, so the request's total
        can end up past the quota by at most one call's output (and by
        calls that run in parallel and pass the check together) -- the
        same overshoot the daily quota accepts. Once one call has been
        refused, every later call in the scope is refused too.
        """

        if self.quota is None:
            return

        if self.refused is not None:
            raise self.quota_error()

        requested = sum(self.estimate_tokens(text) for text in prompt_texts)

        if self.total_tokens + requested > self.quota:
            self.refused = RequestTokenQuotaExceededError(
                quota=self.quota,
                used=self.total_tokens,
                requested=requested,
            )
            raise self.quota_error()

    def quota_error(self) -> RequestTokenQuotaExceededError:
        """The refusal, carrying the tokens the scope has used so far."""

        if self.refused is None:
            raise RuntimeError("The request token quota refused no call.")

        return RequestTokenQuotaExceededError(
            quota=self.refused.quota,
            used=self.refused.used,
            requested=self.refused.requested,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
        )


_meter: ContextVar[UsageMeter | None] = ContextVar("usage_meter", default=None)
_request_quota: ContextVar[int | None] = ContextVar("request_token_quota", default=None)


@contextmanager
def request_token_quota(quota: int | None) -> Iterator[None]:
    """
    Cap the tokens of every usage scope opened within this block at
    `quota` (None: no cap). Restores the previous value with set(), for
    the same reason as usage_scope().
    """

    previous = _request_quota.get()
    _request_quota.set(quota)

    try:
        yield
    finally:
        _request_quota.set(previous)


@contextmanager
def usage_scope(
    *,
    estimate_tokens: TokenEstimator = _rough_token_estimate,
) -> Iterator[UsageMeter]:
    """
    Count the LLM calls made within this block on a new meter, capped
    by the request_token_quota() in effect, if any. estimate_tokens
    sizes each prompt for that check.

    Restores the previous meter with set(), not reset(token): a scope
    held open across an async generator's yields may be closed from a
    different context (a client disconnecting mid-stream), where
    reset() raises.
    """

    previous = _meter.get()
    meter = UsageMeter(quota=_request_quota.get(), estimate_tokens=estimate_tokens)
    _meter.set(meter)

    try:
        yield meter
    finally:
        _meter.set(previous)


def check_request_token_quota(prompt_texts: Iterable[str]) -> None:
    """
    Refuse an LLM call, before it is made, that would take the current
    scope past its token quota; a no-op outside a scope or without one.
    """

    meter = _meter.get()

    if meter is None:
        return

    meter.check(prompt_texts)


def record_llm_usage(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> None:
    """Add one call's usage to the current meter; a no-op outside a scope."""

    meter = _meter.get()

    if meter is None:
        return

    meter.add(
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
