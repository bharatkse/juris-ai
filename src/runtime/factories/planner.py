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

from agentic.planning.llm_planner import LLMPlanGenerator
from agentic.planning.planner import ExecutionPlanner
from agentic.planning.prompts.planning import PlanningPromptBuilder
from agentic.planning.templates import PlanTemplateRegistry
from agentic.planning.validator import ExecutionPlanValidator
from core.enums import LLMProviderEnum
from runtime.containers import ClientContainer


def create_planner(*, clients: ClientContainer) -> ExecutionPlanner:
    return ExecutionPlanner(
        template_registry=PlanTemplateRegistry(),
        llm_planner=LLMPlanGenerator(
            llm_client=clients.llm_resolver.get(LLMProviderEnum.LOCAL),
            prompt_builder=PlanningPromptBuilder(),
        ),
        validator=ExecutionPlanValidator(),
    )
