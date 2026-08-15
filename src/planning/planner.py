"""
Execution planner.

Coordinates execution plan generation.

Flow:

OrchestrationContext
│
▼
PlanningRequestDTO
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
      │
      │ ONE LLM CALL
      ▼
   ExecutionPlan
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
from src.observability.tracing import span
from src.orchestration.schemas.context import OrchestrationContext
from src.planning.llm_planner import LLMPlanGenerator
from src.planning.templates import PlanTemplateRegistry
from src.planning.validator import ExecutionPlanValidator


class ExecutionPlanner:
    """
    Coordinates execution plan generation.

    Planning follows a deterministic-first strategy:

        1. Build a planning request.
        2. Attempt deterministic template resolution.
        3. Fall back to the LLM planner when no template matches.
        4. Validate the resulting execution plan.

    The LLM planner performs intent classification and
    execution-plan generation in a single LLM call.
    """

    def __init__(
        self,
        *,
        template_registry: PlanTemplateRegistry,
        llm_planner: LLMPlanGenerator,
        validator: ExecutionPlanValidator,
    ) -> None:
        self._template_registry = template_registry
        self._llm_planner = llm_planner
        self._validator = validator

    async def create_plan(
        self,
        *,
        context: OrchestrationContext,
    ) -> ExecutionPlanDTO:
        """
        Create a validated execution plan.
        """

        with span(
            "juris_ai.planning",
        ) as current_span:
            request = self._build_planning_request(
                context=context,
            )

            plan, source = await self._resolve_plan(
                request=request,
            )

            validated_plan = self._validate_plan(
                plan=plan,
            )

            current_span.set_attribute(
                "planning.intent",
                validated_plan.intent,
            )
            current_span.set_attribute(
                "planning.source",
                source,
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
    ) -> tuple[
        ExecutionPlanDTO,
        str,
    ]:
        """
        Resolve an execution plan.

        Deterministic templates are attempted first. The LLM
        planner is invoked only when no deterministic template
        matches.

        Returns:
            The execution plan and its source.
        """

        plan = self._template_registry.resolve(
            request=request,
        )

        if plan is not None:
            return plan, "template"

        plan = await self._llm_planner.generate(
            request=request,
        )

        return plan, "llm"

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
        *,
        plan: ExecutionPlanDTO,
    ) -> ExecutionPlanDTO:
        """
        Validate an execution plan.

        Validation failures are propagated to the caller.

        An invalid plan must not silently fall back to a
        generic execution plan because that could change the
        intended semantics of the user's request.
        """

        return self._validator.validate(
            plan,
        )
