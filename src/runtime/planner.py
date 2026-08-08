"""
Runtime planner composition.

Creates the execution planner.

Responsibilities:

- Create the intent analyzer
- Create the LLM planner
- Create the template registry
- Create the plan validator
- Assemble the planner

No business logic belongs in this module.
"""

from __future__ import annotations

from src.planning.intent import IntentAnalyzer
from src.planning.llm_planner import LLMPlanGenerator
from src.planning.planner import ExecutionPlanner
from src.planning.templates import PlanTemplateRegistry
from src.planning.validator import ExecutionPlanValidator
from src.runtime.containers import ClientContainer, RegistryContainer


def create_planner(
    *,
    clients: ClientContainer,
    registries: RegistryContainer,
) -> ExecutionPlanner:
    """
    Create the execution planner.
    """

    return ExecutionPlanner(
        intent_analyzer=IntentAnalyzer(),
        template_registry=PlanTemplateRegistry(),
        llm_planner=LLMPlanGenerator(
            llm_client=clients.llm_client,
        ),
        validator=ExecutionPlanValidator(
            agent_registry=registries.agent_registry,
        ),
    )
