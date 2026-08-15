"""
Execution exceptions.

Execution exceptions are raised while executing an execution plan.

These exceptions inherit from ``AIError`` and represent failures that
occur after planning has completed and execution has begun.

Execution Pipeline:

Execution Plan
        │
        ▼
Executor
        │
        ▼
Execution Strategy
        │
        ▼
Agent Execution
        │
        ▼
Tool Execution
        │
        ▼
Response Aggregation
"""

from __future__ import annotations

from src.core.constants import (
    ERROR_COLLABORATION,
    ERROR_EXECUTION,
    ERROR_STEP_EXECUTION,
    ERROR_STRATEGY,
)
from src.core.exceptions.base import AIError


class ExecutionError(AIError):
    """
    Base exception for execution failures.
    """

    error_code = ERROR_EXECUTION
    default_message = "Execution failed."


class StrategyError(ExecutionError):
    """
    Raised when an execution strategy fails.

    Examples:
        - Unsupported execution strategy
        - Invalid execution mode
        - Strategy initialization failure
    """

    error_code = ERROR_STRATEGY
    default_message = "Execution strategy failed."


class StepExecutionError(ExecutionError):
    """
    Raised when execution of a plan step fails.

    Examples:
        - Agent execution failed
        - Tool execution failed
        - Unexpected runtime exception
    """

    error_code = ERROR_STEP_EXECUTION
    default_message = "Execution step failed."


class CollaborationError(ExecutionError):
    """
    Raised when collaboration between agents fails.

    Examples:
        - Collaboration bus failure
        - Invalid agent message
        - Agent communication timeout
    """

    error_code = ERROR_COLLABORATION
    default_message = "Agent collaboration failed."
