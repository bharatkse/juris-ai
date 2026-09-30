"""
The judge-availability probe: a judge call that fails because its provider
is unavailable is recorded on the probe of the evaluation it ran in.
"""

from __future__ import annotations

import asyncio

from core.judge_availability import (
    judge_availability_probe,
    record_judge_provider_unavailable,
)


def test_recording_outside_a_probe_is_a_no_op() -> None:
    record_judge_provider_unavailable()


def test_a_probe_starts_available_and_records_an_outage() -> None:
    with judge_availability_probe() as probe:
        assert probe.provider_unavailable is False
        record_judge_provider_unavailable()

    assert probe.provider_unavailable is True


async def test_tasks_started_inside_the_probe_record_on_it() -> None:
    with judge_availability_probe() as probe:
        await asyncio.gather(asyncio.create_task(_record()))

    assert probe.provider_unavailable is True


def test_each_probe_is_separate() -> None:
    with judge_availability_probe() as outer:
        with judge_availability_probe() as inner:
            record_judge_provider_unavailable()

    assert inner.provider_unavailable is True
    assert outer.provider_unavailable is False


async def _record() -> None:
    record_judge_provider_unavailable()
