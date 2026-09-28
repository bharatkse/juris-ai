"""
Structured schemas for agent decisions.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
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


def decision_json_schema(*, tool_names: Sequence[str]) -> dict[str, Any]:
    """
    AgentDecision's JSON Schema with ``tool_call.tool_name`` limited to
    ``tool_names`` (the agent's allowed tools), or with no tool call
    possible when there are none.

    Carried as LLMRequestDTO.response_schema and used only by a client
    that enforces the schema while decoding (Ollama's ``format``, verified
    in review A19), which then can't produce a tool the agent may not use.
    Groq is sent AgentDecision's own schema: with the enum attached, its
    best-effort mode changed decisions (a no-evidence question got a
    retriever call instead of an answer, 3/3 live), so its path stays as
    it was until measured (review A19). The runtime's policy check stays
    the authority either way. Only names are constrained: parameters are
    validated by ToolExecutionService.
    """

    schema = copy.deepcopy(AgentDecision.model_json_schema())
    names = sorted(set(tool_names))

    if names:
        schema["$defs"]["AgentToolCall"]["properties"]["tool_name"]["enum"] = names
    else:
        schema["properties"]["tool_call"] = {"type": "null", "default": None}

    return schema
