"""
Files attached to a chat message, as the agent's starting context.

The Executor parses the attachments once per execution, before the graph
runs, and puts the result in the graph's initial reasoning_context: every
plan step's agent starts from the documents the user handed over, and the
LangGraph checkpoint keeps them for a resume() after an approval.

Each readable file becomes one evidence item (an answer can be grounded
in it and cite it). A file that can't be used -- unsupported type, parse
failure, no text, or text withheld because it contained a prompt-injection
pattern -- becomes a runtime note instead, so the model knows the file
was received but never treats it as a source.

Parsing and screening are ParserTool's (the same parsers and
SecuritySanitizer); the model can't call the parser itself.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence

from agentic.agents.runtime.feedback import runtime_feedback
from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.tools.library.parser import ParsedFile, ParserTool
from core.dto.tool import RetrievedContentDTO, ToolFileDTO
from core.enums import RetrievalSourceEnum

UPLOADED_FILE = "uploaded_file"

# The runtime's per-evidence-item limit: a large upload is truncated,
# not dropped.
MAX_ATTACHMENT_CHARS = AgentExecutionBudget().max_evidence_item_chars

# The user chose to hand these over: keep them ahead of retrieved chunks
# when the prompt has to be trimmed (lowest score is dropped first).
ATTACHMENT_SCORE = 1.0

_UNSAFE_NAME_CHARS = re.compile(r"[\x00-\x1f\x7f<>`]+")
_MAX_NAME_CHARS = 120


def display_name(filename: str) -> str:
    """The filename as shown to the model: base name, one line, no markup."""

    base = re.split(r"[\\/]", filename)[-1]
    cleaned = _UNSAFE_NAME_CHARS.sub(" ", base).strip()
    return cleaned[:_MAX_NAME_CHARS] or "unnamed file"


def _to_context(parsed: ParsedFile) -> RetrievedContentDTO:
    name = display_name(parsed.filename)

    if parsed.text is None:
        return runtime_feedback(
            f"The uploaded file '{name}' could not be used: {parsed.problem}",
        )

    text = parsed.text
    if len(text) > MAX_ATTACHMENT_CHARS:
        text = text[:MAX_ATTACHMENT_CHARS] + "\n[truncated]"

    return RetrievedContentDTO(
        source=RetrievalSourceEnum.DOCUMENT,
        source_name=name,
        content=f"[Uploaded file: {name}]\n{text}",
        score=ATTACHMENT_SCORE,
        metadata={"title": name, "source_type": UPLOADED_FILE},
    )


async def attachment_context(
    *,
    parser: ParserTool,
    files: Sequence[ToolFileDTO],
) -> tuple[RetrievedContentDTO, ...]:
    """Parse the attached files, concurrently and off the event loop."""

    if not files:
        return ()

    parsed = await asyncio.gather(
        *(asyncio.to_thread(parser.parse_file, file) for file in files),
    )

    return tuple(_to_context(item) for item in parsed)
