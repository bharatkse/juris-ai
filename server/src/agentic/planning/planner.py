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
Plan  Default one-step plan
│     │
└──┬──┘
   ▼
Validator
   │
   ▼
ExecutionPlan
"""

from __future__ import annotations

from adapters.observability.tracing import span
from agentic.orchestration.schemas.context import OrchestrationContext
from agentic.planning.llm_planner import LLMPlanGenerator
from agentic.planning.templates import PlanTemplateRegistry
from agentic.planning.validator import ExecutionPlanValidator
from core.dto.planning import ExecutionPlanDTO, PlanningRequestDTO


class ExecutionPlanner:
    """
    Coordinates execution plan generation.

    Planning follows a deterministic-first strategy:

        1. Build a planning request.
        2. Attempt deterministic template resolution.
        3. Use the default one-step legal plan when no template matches.
        4. Validate the resulting execution plan.

    The LLM planner is kept for tests and explicit callers. Chat does
    not wait on a planning model: a local 8B planner was adding
    15–100s before the answering call even started.
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
            "juris_agentic.planning",
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

        Deterministic templates are attempted first. Unmatched chat
        requests use the default one-step legal plan instead of a
        second local LLM round-trip.

        Returns:
            The execution plan and its source.
        """

        plan = self._template_registry.resolve(
            request=request,
        )

        if plan is not None:
            return plan, "template"

        return self._template_registry.default(), "default"

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
            user_memory=context.conversation.user_memory,
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
