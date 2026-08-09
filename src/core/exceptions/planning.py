"""
Planning exceptions.

Planning exceptions are raised while analyzing user intent,
constructing execution plans, or validating generated plans.

These exceptions inherit from ``AIError`` and indicate failures
during the planning phase of the AI orchestration pipeline.

Planning Pipeline:

Intent Analyzer
        │
        ▼
Plan Template Resolver
        │
        ▼
LLM Plan Generator
        │
        ▼
Plan Validator
"""

from __future__ import annotations

from src.core.constants import (
    ERROR_INTENT_ANALYSIS,
    ERROR_PLAN_GENERATION,
    ERROR_PLAN_VALIDATION,
    ERROR_PLANNING,
)
from src.core.exceptions.base import AIError


class PlanningError(AIError):
    """
    Base exception for planning failures.
    """

    error_code = ERROR_PLANNING
    default_message = "Planning operation failed."


class IntentAnalysisError(PlanningError):
    """
    Raised when intent analysis fails.

    Examples:
        - Intent classifier failed
        - Intent confidence below threshold
        - Unsupported user intent
    """

    error_code = ERROR_INTENT_ANALYSIS
    default_message = "Intent analysis failed."


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
        - Unknown capability
        - Circular dependency detected
        - Missing required inputs
        - Invalid execution mode
    """

    error_code = ERROR_PLAN_VALIDATION
    default_message = "Execution plan validation failed."
