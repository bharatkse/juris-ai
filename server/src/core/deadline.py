"""
Deadline for the work running in the current context.

The execution runtime knows how long a request may take (the graph
timeout, the agent turn's time budget); an LLM client deciding whether a
slow extra call can still finish (FailoverLLMClient) doesn't. This
carries the earliest applicable deadline down to it through a
ContextVar, so neither layer imports the other: asyncio tasks copy the
context they are created in, so LangGraph nodes and asyncio.wait_for see
the deadline set around them.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_deadline: ContextVar[float | None] = ContextVar("deadline", default=None)


def remaining_seconds() -> float | None:
    """Seconds left before the current deadline, or None when there is none."""

    deadline = _deadline.get()

    if deadline is None:
        return None

    return deadline - time.monotonic()


@contextmanager
def deadline_within(seconds: float) -> Iterator[None]:
    """
    Within this block the deadline is ``seconds`` from now, unless an
    enclosing block already set an earlier one.
    """

    candidate = time.monotonic() + seconds
    current = _deadline.get()
    _deadline.set(candidate if current is None else min(current, candidate))

    try:
        yield
    finally:
        # set(), not reset(token): a block held open across an async
        # generator's yields (AIOrchestrator.stream()) may be closed from
        # a different context (a client disconnecting), where reset()
        # raises. Same reason as core.usage.usage_scope().
        _deadline.set(current)
