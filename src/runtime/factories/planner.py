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

from src.core.enums import LLMProviderEnum
from src.planning.llm_planner import LLMPlanGenerator
from src.planning.planner import ExecutionPlanner
from src.planning.prompts.planning import PlanningPromptBuilder
from src.planning.templates import PlanTemplateRegistry
from src.planning.validator import ExecutionPlanValidator
from src.runtime.containers import ClientContainer


def create_planner(*, clients: ClientContainer) -> ExecutionPlanner:
    return ExecutionPlanner(
        template_registry=PlanTemplateRegistry(),
        llm_planner=LLMPlanGenerator(
            llm_client=clients.llm_resolver.get(LLMProviderEnum.LOCAL),
            prompt_builder=PlanningPromptBuilder(),
        ),
        validator=ExecutionPlanValidator(),
    )
