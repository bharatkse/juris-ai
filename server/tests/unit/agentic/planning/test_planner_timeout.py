"""
The planner's LLM call is bounded (review R18): PLANNER_TIMEOUT_S, or less
when the request's own deadline (core.deadline, opened by the orchestrator
before planning) is closer. A call still running then is cancelled and
PlanningTimeoutError (504 PLANNING_TIMEOUT) raised: no unbounded waits.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest

from agentic.planning.llm_planner import LLMPlanGenerator
from config.llm import LLMSettings
from core.deadline import deadline_within, remaining_seconds
from core.exceptions.planning import PlanningTimeoutError
from tests.builders.agentic.planning import (
    build_execution_plan_response,
    build_planning_request,
)


def _generator(llm: Mock, prompt_builder: Mock, catalog: Mock, timeout: float) -> LLMPlanGenerator:
    return LLMPlanGenerator(
        llm_client=llm,
        prompt_builder=prompt_builder,
        capability_catalog=catalog,
        timeout_seconds=timeout,
    )


async def _hang(**_kwargs):
    await asyncio.Event().wait()


async def test_a_hung_planner_call_times_out_within_the_limit(
    mock_llm_client: Mock, mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    mock_llm_client.generate_structured = AsyncMock(side_effect=_hang)
    generator = _generator(mock_llm_client, mock_prompt_builder, mock_capability_catalog, 0.2)

    started = time.monotonic()
    with pytest.raises(PlanningTimeoutError) as caught:
        await generator.generate(request=build_planning_request())

    assert time.monotonic() - started < 1.0
    assert caught.value.status_code == 504
    assert caught.value.error_code == "PLANNING_TIMEOUT"


async def test_a_closer_request_deadline_shortens_the_planner_timeout(
    mock_llm_client: Mock, mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    mock_llm_client.generate_structured = AsyncMock(side_effect=_hang)
    generator = _generator(mock_llm_client, mock_prompt_builder, mock_capability_catalog, 30)

    started = time.monotonic()
    with deadline_within(0.2), pytest.raises(PlanningTimeoutError):
        await generator.generate(request=build_planning_request())

    assert time.monotonic() - started < 1.0


async def test_the_planner_call_sees_its_deadline(
    mock_llm_client: Mock, mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    """So FailoverLLMClient's deadline check applies to a planner call too."""

    seen: list[float | None] = []

    async def plan(**_kwargs):
        seen.append(remaining_seconds())
        return build_execution_plan_response()

    mock_llm_client.generate_structured = AsyncMock(side_effect=plan)
    generator = _generator(mock_llm_client, mock_prompt_builder, mock_capability_catalog, 30)

    await generator.generate(request=build_planning_request())

    assert seen[0] is not None and 0 < seen[0] <= 30


def test_the_planner_timeout_setting_is_positive() -> None:
    assert LLMSettings().PLANNER_TIMEOUT_S > 0

    with pytest.raises(ValueError):
        LLMSettings(PLANNER_TIMEOUT_S=0)
