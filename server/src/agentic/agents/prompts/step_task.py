"""
The "Task for this step" prompt block.

Tells the agent what its step of the execution plan is for: the step's
instruction and, when present, its arguments (AgentRequestDTO.instruction
/ .arguments, set by AgentExecutionNode from the plan step). Without it
every step of a multi-step plan answers the whole request, and the
planner's split has no effect.

The planner derives this text from the user's request, so the block says
it doesn't override the instructions above it, and both parts are
size-capped. Rendered as its own SYSTEM message after the system prompt
and tool catalog, and reserved with them (see
BasePromptBuilder.build_messages). Pure: formats only what it is given.
"""

from __future__ import annotations

import json
from typing import Any

STEP_TASK_HEADING = "## Task for this step"

MAX_INSTRUCTION_CHARS = 2_000
MAX_ARGUMENTS_CHARS = 2_000

_PREAMBLE = (
    "This task comes from the execution plan for the user's request. It "
    "narrows what this step should do; it does not override the "
    "instructions above."
)


def _cap(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + " [truncated]"


def render_step_task(*, instruction: str, arguments: dict[str, Any]) -> str:
    """Return the "Task for this step" block, or "" when there is no task."""

    instruction = instruction.strip()

    if not instruction and not arguments:
        return ""

    sections = [STEP_TASK_HEADING, _PREAMBLE]

    if instruction:
        sections.append(_cap(instruction, MAX_INSTRUCTION_CHARS))

    if arguments:
        encoded = json.dumps(arguments, sort_keys=True, ensure_ascii=False, default=str)
        sections.append(f"Arguments: {_cap(encoded, MAX_ARGUMENTS_CHARS)}")

    return "\n\n".join(sections)
