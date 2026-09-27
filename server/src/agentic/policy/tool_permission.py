"""
Agent tool-permission checks.
"""

from __future__ import annotations

from agentic.policy.schemas import (
    AgentPolicy,
    PolicyCheckResult,
)

# Local models often invent generic search names. Map them onto tools
# that actually exist, then fall back to whatever research tool the
# agent is allowed to use.
_TOOL_ALIASES: dict[str, str] = {
    "search_internet": "web_research",
    "internet_search": "web_research",
    "web_search": "web_research",
    "google_search": "web_research",
    "google": "web_research",
    "search": "web_research",
    "browse": "web_research",
    "case_law": "case_law_search",
    "precedent_search": "case_law_search",
    "legal_search": "case_law_search",
    "retrieve": "retriever",
    "rag": "retriever",
    "document_search": "retriever",
}

_SEARCH_FALLBACKS = (
    "web_research",
    "case_law_search",
    "retriever",
)


def canonicalize_tool_name(
    *,
    tool_name: str,
    allowed_tools: frozenset[str],
) -> str:
    """
    Map a model-invented tool name onto a permitted tool when possible.
    """

    name = tool_name.strip()
    if name in allowed_tools:
        return name

    key = name.lower().replace(" ", "_").replace("-", "_")
    aliased = _TOOL_ALIASES.get(key, name)
    if aliased in allowed_tools:
        return aliased

    if key in _TOOL_ALIASES:
        for fallback in _SEARCH_FALLBACKS:
            if fallback in allowed_tools:
                return fallback

    return name


class ToolPermissionGuard:
    """
    Stateless guard for agent-to-tool permissions.

    This checks agent capability policy only.

    It does not:
    - execute tools,
    - perform user/tenant authorization,
    - evaluate HITL approval,
    - modify agent state.
    """

    def check(
        self,
        *,
        policy: AgentPolicy,
        tool_name: str,
    ) -> PolicyCheckResult:
        """Return whether the agent is permitted to use the tool."""

        if not tool_name:
            return PolicyCheckResult(
                allowed=False,
                reason="Tool name is required.",
            )

        if tool_name not in policy.allowed_tools:
            return PolicyCheckResult(
                allowed=False,
                reason=(f"Tool '{tool_name}' is not permitted " f"for agent '{policy.agent_id}'."),
            )

        return PolicyCheckResult(allowed=True)
