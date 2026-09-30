"""
The planner fails over from the local model to a second provider
(PLANNER_FAILOVER_PROVIDER, Groq by default): when the local call times out
(PLANNER_TIMEOUT_S) or fails, the plan is asked once of the failover client,
within what is left of the request's deadline. No time left means no second
call and 504 PLANNING_TIMEOUT; both failing is 504 too. With no failover
client the planner behaves as before.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agentic.planning import llm_planner
from agentic.planning.llm_planner import LLMPlanGenerator
from config.llm import LLMSettings
from core.deadline import deadline_within
from core.exceptions.client import ClientConnectionError, ClientProviderError
from core.exceptions.planning import PlanningTimeoutError
from core.exceptions.rate_limit import RequestTokenQuotaExceededError
from tests.builders.agentic.planning import (
    build_execution_plan_response,
    build_planning_request,
)


async def _hang(**_kwargs):
    await asyncio.Event().wait()


def _client(provider: str, **generate) -> MagicMock:
    client = MagicMock()
    client.provider = provider
    client.generate_structured = AsyncMock(**generate)
    return client


def _generator(
    primary: MagicMock,
    fallback: MagicMock | None,
    prompt_builder: Mock,
    catalog: Mock,
    *,
    timeout: float = 30,
    min_fallback_seconds: float = 0.1,
) -> LLMPlanGenerator:
    return LLMPlanGenerator(
        llm_client=primary,
        fallback_llm_client=fallback,
        prompt_builder=prompt_builder,
        capability_catalog=catalog,
        timeout_seconds=timeout,
        min_fallback_seconds=min_fallback_seconds,
    )


@pytest.mark.parametrize(
    "primary_failure",
    [
        {"side_effect": ClientConnectionError()},
        {"side_effect": ClientProviderError(message="model not found")},
        {"side_effect": _hang},
    ],
    ids=["connection error", "provider error", "timeout"],
)
async def test_a_failed_local_plan_is_asked_of_the_failover_provider(
    mock_prompt_builder: Mock, mock_capability_catalog: Mock, primary_failure: dict
) -> None:
    plan = build_execution_plan_response()
    local = _client("local", **primary_failure)
    groq = _client("groq", return_value=plan)
    generator = _generator(local, groq, mock_prompt_builder, mock_capability_catalog, timeout=0.2)

    with (
        deadline_within(10),
        patch.object(llm_planner.metrics, "record_llm_failover") as record,
    ):
        result = await generator.generate(request=build_planning_request())

    assert result.intent == plan.intent
    groq.generate_structured.assert_awaited_once()
    assert record.call_args.kwargs["primary"] == "local"
    assert record.call_args.kwargs["fallback"] == "groq"
    assert record.call_args.kwargs["outcome"] == "attempted"


async def test_both_providers_failing_is_a_planning_timeout(
    mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    local = _client("local", side_effect=_hang)
    groq = _client("groq", side_effect=_hang)
    generator = _generator(local, groq, mock_prompt_builder, mock_capability_catalog, timeout=0.2)

    started = time.monotonic()
    with deadline_within(0.6), pytest.raises(PlanningTimeoutError) as caught:
        await generator.generate(request=build_planning_request())

    assert time.monotonic() - started < 1.5
    assert caught.value.status_code == 504
    groq.generate_structured.assert_awaited_once()


async def test_a_failover_provider_error_is_a_planning_timeout_too(
    mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    local = _client("local", side_effect=ClientConnectionError())
    groq = _client("groq", side_effect=ClientConnectionError())
    generator = _generator(local, groq, mock_prompt_builder, mock_capability_catalog)

    with deadline_within(10), pytest.raises(PlanningTimeoutError):
        await generator.generate(request=build_planning_request())


async def test_no_time_left_means_no_failover_call(
    mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    local = _client("local", side_effect=ClientConnectionError())
    groq = _client("groq", return_value=build_execution_plan_response())
    generator = _generator(
        local, groq, mock_prompt_builder, mock_capability_catalog, min_fallback_seconds=5
    )

    with deadline_within(1), pytest.raises(PlanningTimeoutError):
        await generator.generate(request=build_planning_request())

    groq.generate_structured.assert_not_awaited()


async def test_a_request_token_quota_refusal_is_not_failed_over(
    mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    """The user's per-request quota: another provider would be refused too."""

    refusal = RequestTokenQuotaExceededError(quota=10, used=0, requested=20)
    local = _client("local", side_effect=refusal)
    groq = _client("groq", return_value=build_execution_plan_response())
    generator = _generator(local, groq, mock_prompt_builder, mock_capability_catalog)

    with deadline_within(10), pytest.raises(RequestTokenQuotaExceededError):
        await generator.generate(request=build_planning_request())

    groq.generate_structured.assert_not_awaited()


async def test_without_failover_a_local_error_is_raised_as_before(
    mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    local = _client("local", side_effect=ClientConnectionError())
    generator = _generator(local, None, mock_prompt_builder, mock_capability_catalog)

    with pytest.raises(ClientConnectionError):
        await generator.generate(request=build_planning_request())


async def test_without_failover_a_local_timeout_is_a_planning_timeout(
    mock_prompt_builder: Mock, mock_capability_catalog: Mock
) -> None:
    local = _client("local", side_effect=_hang)
    generator = _generator(local, None, mock_prompt_builder, mock_capability_catalog, timeout=0.2)

    with pytest.raises(PlanningTimeoutError):
        await generator.generate(request=build_planning_request())


def test_planner_settings_defaults() -> None:
    settings = LLMSettings()

    assert settings.PLANNER_TIMEOUT_S == 45
    assert settings.PLANNER_FAILOVER_PROVIDER == "groq"
    assert LLMSettings(PLANNER_FAILOVER_PROVIDER="").PLANNER_FAILOVER_PROVIDER == ""
