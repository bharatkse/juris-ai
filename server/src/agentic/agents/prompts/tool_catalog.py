"""
The "Available tools" prompt block.

Tells the agent exactly which tools its policy allows, each with a
one-line purpose and the JSON Schema of the parameters it accepts
(ToolRegistry.describe(), via AgentRequestDTO.tool_catalog). Without it
the model can only guess tool names and parameters, and a wrong guess
is rejected.

Rendered as its own SYSTEM message and reserved with the system prompt
(see BasePromptBuilder.build_messages), so token-budget trimming never
drops it. Pure: formats only what it is given.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from core.dto.tool import ToolSpecDTO

TOOL_CATALOG_HEADING = "## Available tools"

NO_TOOLS_MESSAGE = "No tools are available to you. Do not return a `TOOL_CALL` decision."

_PREAMBLE = (
    "Call only these tools, by their exact name, with parameters that match "
    "the tool's JSON Schema. A call to any other tool, or with any other "
    "parameter or value, is rejected."
)


def render_tool_catalog(catalog: Sequence[ToolSpecDTO]) -> str:
    """Return the "Available tools" block for this agent's tools."""

    if not catalog:
        return f"{TOOL_CATALOG_HEADING}\n\n{NO_TOOLS_MESSAGE}"

    sections = [TOOL_CATALOG_HEADING, _PREAMBLE]

    for spec in catalog:
        schema = json.dumps(spec.parameters_schema, sort_keys=True, separators=(",", ":"))
        sections.append(
            f"### `{spec.name}`\n{spec.description}\nParameters (JSON Schema): {schema}",
        )

    return "\n\n".join(sections)
