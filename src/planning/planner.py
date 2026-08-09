"""
Execution planner.

Coordinates execution plan generation.

Flow:

PlanningRequest
        │
        ▼
Intent Analyzer
        │
        ▼
Templates
        │
   Found?
    │
 ┌──┴──┐
 │     │
Yes    No
 │     │
 ▼     ▼
Plan  LLM Generator
 │     │
 └──┬──┘
    ▼
Validator
    │
    ▼
ExecutionPlan
"""

from __future__ import annotations

from src.core.exceptions.planning import PlanValidationError
from src.planning.intent import IntentAnalyzer
from src.planning.llm_planner import LLMPlanGenerator
from src.planning.models import ExecutionPlan, PlanningRequest
from src.planning.templates import PlanTemplateRegistry
from src.planning.validator import ExecutionPlanValidator


class ExecutionPlanner:
    """
    Coordinates execution plan generation.
    """

    def __init__(
        self,
        *,
        intent_analyzer: IntentAnalyzer,
        template_registry: PlanTemplateRegistry,
        llm_planner: LLMPlanGenerator,
        validator: ExecutionPlanValidator,
    ) -> None:
        self._intent_analyzer = intent_analyzer
        self._template_registry = template_registry
        self._llm_planner = llm_planner
        self._validator = validator

    async def plan(
        self,
        *,
        request: PlanningRequest,
    ) -> ExecutionPlan:
        """
        Create an execution plan.
        """

        plan = await self._resolve_plan(
            request=request,
        )

        return self._validate_plan(
            plan,
        )

    async def _resolve_plan(
        self,
        *,
        request: PlanningRequest,
    ) -> ExecutionPlan:
        """
        Resolve an execution plan.
        """

        intent = await self._intent_analyzer.analyze(
            request=request,
        )

        plan = self._template_registry.resolve(
            intent=intent,
        )

        if plan is not None:
            return plan

        return await self._llm_planner.generate(
            request=request,
            intent=intent,
        )

    def _validate_plan(
        self,
        plan: ExecutionPlan,
    ) -> ExecutionPlan:
        """
        Validate an execution plan.

        Falls back to the default plan if validation fails.
        """

        try:
            return self._validator.validate(
                plan,
            )

        except PlanValidationError:
            return self._template_registry.default()
