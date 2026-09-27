"""
Runtime feedback notes.

Short notes the runtime adds to an agent's reasoning context to steer
its next reasoning call: the answer-quality gate's notes on a rejected
answer, and the runtime's notes on a recoverable error (an invalid
decision, a tool the agent may not use, a failed tool call).

They reach the model like any other context item, but they are not
evidence: an answer can't be grounded in them (the gate excludes them)
and they are never cited (AgentResponseMapper excludes them).
"""

from __future__ import annotations

from core.dto.tool import RetrievedContentDTO
from core.enums import RetrievalSourceEnum

EVALUATION_FEEDBACK = "evaluation_feedback"
CORRECTIVE_RETRIEVAL_FEEDBACK = "corrective_retrieval_feedback"
RUNTIME_FEEDBACK = "runtime_feedback"

FEEDBACK_SOURCE_TYPES = frozenset(
    {EVALUATION_FEEDBACK, CORRECTIVE_RETRIEVAL_FEEDBACK, RUNTIME_FEEDBACK},
)


def is_feedback(item: RetrievedContentDTO) -> bool:
    """Whether a reasoning-context item is a runtime or gate note."""

    return item.metadata.get("source_type") in FEEDBACK_SOURCE_TYPES


def runtime_feedback(content: str) -> RetrievedContentDTO:
    """A note telling the model why its last step was rejected."""

    return RetrievedContentDTO(
        source=RetrievalSourceEnum.MEMORY,
        source_name=RUNTIME_FEEDBACK,
        content=content,
        score=None,
        metadata={"source_type": RUNTIME_FEEDBACK},
    )
