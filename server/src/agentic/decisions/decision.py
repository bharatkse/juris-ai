"""
Agent decision domain types.
"""

from __future__ import annotations

from enum import StrEnum


class AgentDecisionType(StrEnum):
    """
    Decision types produced by an agent's reasoning step.
    """

    FINAL = "final"
    TOOL_CALL = "tool_call"
    DELEGATE = "delegate"
    NEED_INPUT = "need_input"
    FAIL = "fail"
