"""
Runtime planner composition.

Creates the execution planner.

Responsibilities:

- Create the intent analyzer
- Create the LLM planner and its agent capability catalog
- Create the template registry
- Create the plan validator
- Assemble the planner

No business logic belongs in this module.
"""

from __future__ import annotations

from adapters.persistence.sqlalchemy.session import session_factory
from agentic.planning.capabilities import AgentCapabilityCatalog
from agentic.planning.llm_planner import LLMPlanGenerator
from agentic.planning.planner import ExecutionPlanner
from agentic.planning.prompts.planning import PlanningPromptBuilder
from agentic.planning.templates import PlanTemplateRegistry
from agentic.planning.validator import ExecutionPlanValidator
from agentic.policy.agent_policy import DatabaseAgentPolicyProvider
from config.settings import get_settings
from core.enums import LLMProviderEnum
from wiring.containers import ClientContainer, RegistryContainer


def create_planner(
    *,
    clients: ClientContainer,
    registries: RegistryContainer,
) -> ExecutionPlanner:
    # The planner reads the same registries and agent_policies table as
    # the executor's AgentExecution (wiring/factories/executor.py), so the
    # agents and tools it plans with are the ones the runtime allows.
    settings = get_settings()
    max_steps = settings.agent_policy.PLAN_MAX_STEPS

    capability_catalog = AgentCapabilityCatalog(
        agent_registry=registries.agent_registry,
        tool_registry=registries.tool_registry,
        agent_policy_provider=DatabaseAgentPolicyProvider(
            session_factory=session_factory,
        ),
    )

    return ExecutionPlanner(
        template_registry=PlanTemplateRegistry(),
        llm_planner=LLMPlanGenerator(
            # Local first: planning costs no Groq quota, which the agents
            # share (review R18, measured 2026-09-30). Groq is the failover
            # when the local model is down, slow past PLANNER_TIMEOUT_S, or
            # errors; PLANNER_FAILOVER_PROVIDER="" turns that off.
            llm_client=clients.llm_resolver.get(LLMProviderEnum.LOCAL),
            fallback_llm_client=(
                clients.llm_resolver.get(LLMProviderEnum(settings.llm.PLANNER_FAILOVER_PROVIDER))
                if settings.llm.PLANNER_FAILOVER_PROVIDER
                else None
            ),
            prompt_builder=PlanningPromptBuilder(max_steps=max_steps),
            capability_catalog=capability_catalog,
            timeout_seconds=settings.llm.PLANNER_TIMEOUT_S,
        ),
        validator=ExecutionPlanValidator(max_steps=max_steps),
    )
