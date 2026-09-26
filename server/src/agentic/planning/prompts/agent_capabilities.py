"""
The planner's "Available Agents" prompt block.

Lists the agents a plan may use, each with what it's for and the tools its
policy allows (AgentCapabilityCatalog, via
PlanningRequestDTO.agent_capabilities). Generated per request rather than
written into planning.md, so it can't drift from the policies the runtime
enforces. Tool names and purposes only: parameter schemas are the agent's
concern, not the planner's.

Rendered as its own SYSTEM message after the planning instructions (see
PlanningPromptBuilder.build). Pure: formats only what it is given.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from core.dto.planning import AgentCapabilityDTO

AGENT_CAPABILITIES_HEADING = "## Available Agents"

NO_TOOLS_LINE = "Tools: none. It can only reason over the conversation and the user's files."

_PREAMBLE = (
    "Assign every step to one of these agents, by its exact name. Each "
    "agent can use only the tools listed under it; no other agents or "
    "tools exist. Never plan a step that needs a tool its agent doesn't "
    "have. If the request needs something no agent can do, plan a single "
    "step for the closest agent, instructed to tell the user that it "
    "isn't available."
)


def render_agent_capabilities(capabilities: Sequence[AgentCapabilityDTO]) -> str:
    """Return the "Available Agents" block, or "" when there are none."""

    if not capabilities:
        return ""

    sections = [AGENT_CAPABILITIES_HEADING, _PREAMBLE]

    for capability in capabilities:
        if capability.tools:
            tools = "Tools:\n" + "\n".join(
                f"- `{tool.name}`: {tool.description}" for tool in capability.tools
            )
        else:
            tools = NO_TOOLS_LINE

        sections.append(
            f"### `{capability.agent.value}`\n{capability.description}\n{tools}",
        )

    return "\n\n".join(sections)
