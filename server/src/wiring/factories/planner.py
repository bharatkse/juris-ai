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
            llm_client=clients.llm_resolver.get(LLMProviderEnum.LOCAL),
            prompt_builder=PlanningPromptBuilder(),
            capability_catalog=capability_catalog,
        ),
        validator=ExecutionPlanValidator(),
    )
