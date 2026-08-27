"""
Agent response schemas.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.enums import ActionTypeEnum


class AgentActionResponseSchema(BaseModel):
    """
    Concrete action proposed by an agent.

    This is an LLM-facing representation.
    Runtime execution identifiers are intentionally excluded.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    action_type: ActionTypeEnum

    tool_name: str | None

    target_agent_id: str | None

    resource_type: str | None

    resource_id: str | None

    parameters: dict[str, Any] = Field(
        default_factory=dict,
    )

    reason: str


class AgentResponseSchema(BaseModel):
    """
    Structured response produced by an AI agent.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    content: str

    action: AgentActionResponseSchema | None
    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )
