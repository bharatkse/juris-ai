from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class AgentExecutionBudget:
    """
    Immutable limits for a single agent execution.

    Limits cover both execution work and in-memory state growth.

    A budget belongs to one execution configuration and must never
    contain mutable runtime state.
    """

    # Execution limits
    max_iterations: int = 10
    max_tool_calls: int = 20
    max_agent_hops: int = 5
    max_total_steps: int = 30
    max_execution_time_seconds: float = 120.0

    # Loop-control limits
    max_repeated_action: int = 2
    max_no_progress: int = 2
    max_validation_attempts: int = 2

    # Collection limits
    max_decisions: int = 50
    max_tool_call_records: int = 50
    max_tool_result_records: int = 50
    max_evidence_items: int = 100
    max_context_items: int = 100

    # Per-value memory limits
    max_partial_response_chars: int = 50_000
    max_context_item_chars: int = 20_000
    max_evidence_item_chars: int = 20_000
    max_tool_call_record_chars: int = 10_000
    max_tool_result_record_chars: int = 20_000

    def __post_init__(self) -> None:
        integer_limits = {
            "max_iterations": self.max_iterations,
            "max_tool_calls": self.max_tool_calls,
            "max_agent_hops": self.max_agent_hops,
            "max_total_steps": self.max_total_steps,
            "max_repeated_action": self.max_repeated_action,
            "max_no_progress": self.max_no_progress,
            "max_validation_attempts": self.max_validation_attempts,
            "max_decisions": self.max_decisions,
            "max_tool_call_records": self.max_tool_call_records,
            "max_tool_result_records": self.max_tool_result_records,
            "max_evidence_items": self.max_evidence_items,
            "max_context_items": self.max_context_items,
            "max_partial_response_chars": self.max_partial_response_chars,
            "max_context_item_chars": self.max_context_item_chars,
            "max_evidence_item_chars": self.max_evidence_item_chars,
            "max_tool_call_record_chars": self.max_tool_call_record_chars,
            "max_tool_result_record_chars": self.max_tool_result_record_chars,
        }

        for name, value in integer_limits.items():
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer.")

            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

        if isinstance(self.max_execution_time_seconds, bool):
            raise TypeError("max_execution_time_seconds must be a number.")

        if not isinstance(self.max_execution_time_seconds, (int | float)):
            raise TypeError("max_execution_time_seconds must be a number.")

        if not isfinite(self.max_execution_time_seconds):
            raise ValueError("max_execution_time_seconds must be finite.")

        if self.max_execution_time_seconds <= 0:
            raise ValueError(
                "max_execution_time_seconds must be greater than zero.",
            )
