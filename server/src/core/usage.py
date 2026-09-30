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
(TOKEN_QUOTA_PER_REQUEST), the per-request counterpart of the
daily quota and enforced the same way: checked before tokens are spent,
counted after. ChatService sets the quota (request_token_quota()); the
scope opened inside it picks it up; every LLM call checks it before it
is made (check_request_token_quota(), from LLMClient.generate()).
Every scope opened under one request_token_quota() block draws on the
same RequestTokenBudget, so a request whose LLM calls span more than one
scope (conversation summarization before the orchestrator's turn) is
capped as a whole, and a refusal in one scope refuses the later ones.

usage_tally() collects the scopes' usage for a caller that must record
it however the work ends (ChatService, review R19).
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
class RequestTokenBudget:
    """One request's token quota, shared by every scope opened under it."""

    quota: int
    # Tokens of the request's scopes that have already closed.
    used: int = 0
    # The first refused call of the request, once one has been refused.
    refused: RequestTokenQuotaExceededError | None = None


@dataclass(slots=True)
class UsageMeter:
    """Token counts summed over every LLM call made within one scope."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    providers: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)
    # The request's token quota this scope draws on; None means no limit.
    budget: RequestTokenBudget | None = None
    estimate_tokens: TokenEstimator = _rough_token_estimate
    # The first refused call, once the quota has refused one.
    refused: RequestTokenQuotaExceededError | None = None
    # Calls the local failover model answered because the primary
    # provider was unavailable (FailoverLLMClient). A Groq-only judge that
    # can't run then discards that answer (review R17).
    fallback_calls: int = 0

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
    def quota(self) -> int | None:
        """The request's token quota, or None when there is none."""

        return self.budget.quota if self.budget is not None else None

    @property
    def provider(self) -> str | None:
        """The provider, when every call used the same one."""

        return next(iter(self.providers)) if len(self.providers) == 1 else None

    @property
    def model(self) -> str | None:
        """The model, when every call used the same one."""

        return next(iter(self.models)) if len(self.models) == 1 else None

    def merge(self, other: UsageMeter) -> None:
        """Add another meter's counts to this one."""

        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.calls += other.calls
        self.providers |= other.providers
        self.models |= other.models
        self.fallback_calls += other.fallback_calls

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

        budget = self.budget

        if budget is None:
            return

        if self.refused is None and budget.refused is not None:
            # An earlier scope of the same request was refused.
            self.refused = budget.refused

        if self.refused is not None:
            raise self.quota_error()

        requested = sum(self.estimate_tokens(text) for text in prompt_texts)
        used = budget.used + self.total_tokens

        if used + requested > budget.quota:
            self.refused = RequestTokenQuotaExceededError(
                quota=budget.quota,
                used=used,
                requested=requested,
            )
            budget.refused = self.refused
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
_request_budget: ContextVar[RequestTokenBudget | None] = ContextVar(
    "request_token_budget", default=None
)
_tally: ContextVar[UsageMeter | None] = ContextVar("usage_tally", default=None)


@contextmanager
def usage_tally() -> Iterator[UsageMeter]:
    """
    Collect the usage of every usage_scope() opened within this block,
    however each one ends: returned, raised, or cancelled (a client
    disconnecting from a stream). A scope adds its meter to the tally
    when it closes, so the tally is complete once the work inside the
    block has finished or been closed.

    ChatService records one request's usage from its tally in a finally
    (review R19): the orchestrator's own scope only reports usage on a
    returned response or a quota refusal. It counts exactly the calls
    the scopes count, nothing more.
    """

    previous = _tally.get()
    tally = UsageMeter()
    _tally.set(tally)

    try:
        yield tally
    finally:
        _tally.set(previous)


@contextmanager
def request_token_quota(quota: int | None) -> Iterator[None]:
    """
    Cap the tokens of every usage scope opened within this block, taken
    together, at `quota` (None: no cap): one block is one request.
    Restores the previous value with set(), for the same reason as
    usage_scope().
    """

    previous = _request_budget.get()
    _request_budget.set(None if quota is None else RequestTokenBudget(quota=quota))

    try:
        yield
    finally:
        _request_budget.set(previous)


@contextmanager
def usage_scope(
    *,
    estimate_tokens: TokenEstimator = _rough_token_estimate,
) -> Iterator[UsageMeter]:
    """
    Count the LLM calls made within this block on a new meter, capped
    by the request_token_quota() in effect, if any (together with the
    request's scopes that closed before this one). estimate_tokens
    sizes each prompt for that check.

    Restores the previous meter with set(), not reset(token): a scope
    held open across an async generator's yields may be closed from a
    different context (a client disconnecting mid-stream), where
    reset() raises.
    """

    previous = _meter.get()
    tally = _tally.get()
    budget = _request_budget.get()
    meter = UsageMeter(budget=budget, estimate_tokens=estimate_tokens)
    _meter.set(meter)

    try:
        yield meter
    finally:
        _meter.set(previous)

        if budget is not None:
            budget.used += meter.total_tokens

        # The tally in effect when the scope opened, held by reference:
        # a scope closed from another context still reaches it.
        if tally is not None:
            tally.merge(meter)


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


def record_llm_fallback() -> None:
    """
    Note that the fallback provider answered a call in the current scope
    (FailoverLLMClient); a no-op outside a scope.
    """

    meter = _meter.get()

    if meter is not None:
        meter.fallback_calls += 1


def fallback_answered() -> bool:
    """
    Whether any call in the current scope was answered by the fallback
    provider: a judge that can't run then discards that answer (R17).
    """

    meter = _meter.get()

    return meter is not None and meter.fallback_calls > 0
