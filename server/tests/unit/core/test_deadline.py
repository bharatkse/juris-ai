"""
Unit tests for core.deadline.
"""

from __future__ import annotations

import asyncio

import pytest

from core.deadline import deadline_within, remaining_seconds


def test_no_deadline_outside_a_block() -> None:
    assert remaining_seconds() is None


def test_a_block_sets_the_deadline_and_restores_it() -> None:
    with deadline_within(100):
        assert 99 < remaining_seconds() <= 100

    assert remaining_seconds() is None


def test_an_inner_block_can_only_shorten_the_deadline() -> None:
    with deadline_within(100):
        with deadline_within(500):
            assert remaining_seconds() <= 100
        with deadline_within(10):
            assert remaining_seconds() <= 10
        assert remaining_seconds() > 10


@pytest.mark.asyncio
async def test_tasks_created_inside_a_block_see_its_deadline() -> None:
    async def seen() -> float | None:
        return remaining_seconds()

    with deadline_within(50):
        inherited = await asyncio.wait_for(seen(), timeout=5)

    assert inherited is not None and inherited <= 50
