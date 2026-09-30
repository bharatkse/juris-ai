"""
Whether the answer judge's provider was unavailable during an evaluation.

A judge that fails returns no score whatever the cause, so the answer
gate can't tell a provider outage (retrying would only call it again)
from an unusable verdict (worth a retry). The judge (wiring) records an
outage here; the evaluator (agentic) opens a probe around one judged
evaluation and reads it. A ContextVar, like core.deadline, so neither
layer imports the other: asyncio tasks copy the context they are created
in, so a judge call in a task started inside the probe still records on
it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(slots=True)
class JudgeAvailabilityProbe:
    """Set when a judge call in this probe's evaluation found its provider down."""

    provider_unavailable: bool = False


_probe: ContextVar[JudgeAvailabilityProbe | None] = ContextVar("judge_probe", default=None)


@contextmanager
def judge_availability_probe() -> Iterator[JudgeAvailabilityProbe]:
    """Within this block, judge calls record an unavailable provider on the probe."""

    probe = JudgeAvailabilityProbe()
    token = _probe.set(probe)

    try:
        yield probe
    finally:
        _probe.reset(token)


def record_judge_provider_unavailable() -> None:
    """Note that a judge call's provider was unavailable; a no-op outside a probe."""

    probe = _probe.get()

    if probe is not None:
        probe.provider_unavailable = True
