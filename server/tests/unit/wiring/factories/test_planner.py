"""
The planner's clients: the local model, with the provider named by
PLANNER_FAILOVER_PROVIDER (Groq by default; empty turns failover off) as its
failover. The local model is warmed up in the background at startup.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.enums import LLMProviderEnum
from wiring.factories import clients as clients_factory
from wiring.factories import planner as planner_factory


def _clients() -> MagicMock:
    clients = MagicMock()
    clients.llm_resolver.get.side_effect = lambda provider: f"client:{provider.value}"
    return clients


@pytest.mark.parametrize(
    ("setting", "expected_fallback"),
    [("groq", "client:groq"), ("", None)],
)
def test_the_planner_fails_over_to_the_configured_provider(
    setting: str, expected_fallback: str | None
) -> None:
    settings = MagicMock()
    settings.llm.PLANNER_FAILOVER_PROVIDER = setting
    settings.llm.PLANNER_TIMEOUT_S = 45.0
    settings.llm.PLANNER_UNAVAILABLE_RETRY_AFTER_S = 12
    settings.agent_policy.PLAN_MAX_STEPS = 6

    with patch.object(planner_factory, "get_settings", return_value=settings):
        planner = planner_factory.create_planner(clients=_clients(), registries=MagicMock())

    llm_planner = planner._llm_planner
    assert llm_planner._llm == f"client:{LLMProviderEnum.LOCAL.value}"
    assert llm_planner._fallback_llm == expected_fallback
    assert llm_planner._unavailable_retry_after_seconds == 12


async def test_the_local_model_warm_up_logs_its_duration() -> None:
    local = MagicMock()
    local.warm_up = AsyncMock()
    clients = MagicMock()
    clients.llm_resolver.get.return_value = local

    with patch.object(clients_factory, "log") as log:
        await clients_factory.warm_up_local_llm(clients)

    clients.llm_resolver.get.assert_called_once_with(LLMProviderEnum.LOCAL)
    local.warm_up.assert_awaited_once()
    assert "duration_seconds" in log.info.call_args.kwargs["extra"]


async def test_a_failed_warm_up_is_logged_and_never_raised() -> None:
    local = MagicMock()
    local.warm_up = AsyncMock(side_effect=ConnectionError("ollama down"))
    clients = MagicMock()
    clients.llm_resolver.get.return_value = local

    with patch.object(clients_factory, "log") as log:
        await clients_factory.warm_up_local_llm(clients)

    log.warning.assert_called_once()
