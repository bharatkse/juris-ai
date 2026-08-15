"""
Orchestration exceptions.

Orchestration exceptions are raised while coordinating the AI
request lifecycle.

The orchestrator coordinates the planning and execution pipeline but
does not perform business logic itself.

Pipeline:

Request
    │
    ▼
Intent Analysis
    │
    ▼
Planning
    │
    ▼
Execution
    │
    ▼
Response Aggregation
"""

from __future__ import annotations

from src.core.constants import ERROR_ORCHESTRATION
from src.core.exceptions.base import AIError


class OrchestrationError(AIError):
    """
    Raised when orchestration of an AI request fails.

    Examples:
        - Failed to coordinate planning and execution
        - Invalid orchestration lifecycle
        - Unexpected orchestration failure
    """

    error_code = ERROR_ORCHESTRATION
    default_message = "AI orchestration failed."
