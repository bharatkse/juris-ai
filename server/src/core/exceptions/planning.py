"""
Planning exceptions.

Planning exceptions are raised while constructing execution
plans or validating generated plans.

These exceptions inherit from ``AIError`` and indicate failures
during the planning phase of the AI orchestration pipeline.

Planning Pipeline:

Plan Template Resolver
        │
        ├── match
        │
        ▼
ExecutionPlan
        │
        └── no match
                │
                ▼
        LLM Plan Generator
                │
                ▼
        Plan Validator
"""

from __future__ import annotations

from core.constants import ERROR_PLAN_GENERATION, ERROR_PLAN_VALIDATION, ERROR_PLANNING
from core.exceptions.base import AIError


class PlanningError(AIError):
    """
    Base exception for planning failures.
    """

    error_code = ERROR_PLANNING
    default_message = "Planning operation failed."


class PlanGenerationError(PlanningError):
    """
    Raised when execution plan generation fails.

    Examples:
        - Plan template resolution failed
        - LLM returned an invalid plan
        - Planner could not construct an execution plan
    """

    error_code = ERROR_PLAN_GENERATION
    default_message = "Execution plan generation failed."


class PlanValidationError(PlanningError):
    """
    Raised when an execution plan fails validation.

    Examples:
        - Unknown execution step
        - Circular dependency detected
        - Missing required inputs
        - Invalid execution mode
    """

    error_code = ERROR_PLAN_VALIDATION
    default_message = "Execution plan validation failed."


class PlanTooLargeError(PlanValidationError):
    """
    Raised when a plan has more steps than one turn may run.

    The orchestrator answers it with a normal reply asking the user to
    split the request, instead of an error.
    """

    def __init__(
        self,
        *,
        step_count: int,
        max_steps: int,
    ) -> None:
        self.step_count = step_count
        self.max_steps = max_steps

        super().__init__(
            f"Execution plan has {step_count} steps; at most {max_steps} are allowed.",
        )
