"""
Structured schemas for agent decisions.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentic.decisions.decision import AgentDecisionType


class AgentToolCall(BaseModel):
    """A tool invocation requested by the agent."""

    tool_name: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentDelegation(BaseModel):
    """A delegation request to another agent."""

    target_agent_id: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentUserInputRequest(BaseModel):
    """Information the agent needs from the user before continuing."""

    question: str = Field(min_length=1)


class AgentFailure(BaseModel):
    """Structured description of an agent failure."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class AgentDecision(BaseModel):
    """
    Structured decision produced by an agent reasoning step.

    The decision describes what should happen next. It does not execute
    tools or delegate work itself.
    """

    decision_type: AgentDecisionType
    reason: str | None = None

    final_response: str | None = None
    tool_call: AgentToolCall | None = None
    delegation: AgentDelegation | None = None
    user_input: AgentUserInputRequest | None = None
    failure: AgentFailure | None = None
