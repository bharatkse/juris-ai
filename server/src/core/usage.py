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
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(slots=True)
class UsageMeter:
    """Token counts summed over every LLM call made within one scope."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0
    providers: set[str] = field(default_factory=set)
    models: set[str] = field(default_factory=set)

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


_meter: ContextVar[UsageMeter | None] = ContextVar("usage_meter", default=None)


@contextmanager
def usage_scope() -> Iterator[UsageMeter]:
    """
    Count the LLM calls made within this block on a new meter.

    Restores the previous meter with set(), not reset(token): a scope
    held open across an async generator's yields may be closed from a
    different context (a client disconnecting mid-stream), where
    reset() raises.
    """

    previous = _meter.get()
    meter = UsageMeter()
    _meter.set(meter)

    try:
        yield meter
    finally:
        _meter.set(previous)


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
