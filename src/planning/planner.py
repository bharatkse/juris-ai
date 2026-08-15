"""
Execution planner.

Coordinates execution plan generation.

Flow:

OrchestrationContext
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

from src.core.dto.planning import ExecutionPlanDTO, PlanningRequestDTO
from src.core.exceptions.planning import PlanValidationError
from src.observability.tracing import span
from src.orchestration.schemas.context import OrchestrationContext
from src.planning.intent import IntentAnalyzer
from src.planning.llm_planner import LLMPlanGenerator
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

    async def create_plan(
        self,
        *,
        context: OrchestrationContext,
    ) -> ExecutionPlanDTO:
        """
        Create an execution plan.
        """

        with span(
            "juris_ai.planning",
        ) as current_span:
            request = self._build_planning_request(
                context=context,
            )

            plan = await self._resolve_plan(
                request=request,
            )

            validated_plan = self._validate_plan(
                plan,
            )

            current_span.set_attribute(
                "planning.intent",
                validated_plan.intent,
            )
            current_span.set_attribute(
                "planning.source",
                self._get_plan_source(
                    plan=plan,
                    validated_plan=validated_plan,
                ),
            )
            current_span.set_attribute(
                "execution.mode",
                validated_plan.mode,
            )
            current_span.set_attribute(
                "execution.step_count",
                len(validated_plan.steps),
            )

            return validated_plan

    async def _resolve_plan(
        self,
        *,
        request: PlanningRequestDTO,
    ) -> ExecutionPlanDTO:
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

    @staticmethod
    def _build_planning_request(
        *,
        context: OrchestrationContext,
    ) -> PlanningRequestDTO:
        """
        Build a planning request from orchestration context.
        """

        return PlanningRequestDTO(
            message=context.request.message,
            history=tuple(
                context.conversation.history,
            ),
        )

    def _validate_plan(
        self,
        plan: ExecutionPlanDTO,
    ) -> ExecutionPlanDTO:
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

    @staticmethod
    def _get_plan_source(
        *,
        plan: ExecutionPlanDTO,
        validated_plan: ExecutionPlanDTO,
    ) -> str:
        """
        Determine the source of the execution plan.
        """

        if plan is validated_plan:
            return "template_or_llm"

        return "default_fallback"
