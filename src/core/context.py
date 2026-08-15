"""
Request context shared across the application.

This object is created once per HTTP request and enriched
throughout the request lifecycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from src.core.schemas.response import AIUsageModel, MetadataModel


@dataclass(slots=True)
class RequestContext:
    """Per-request execution context."""

    request_id: str = field(default_factory=lambda: str(uuid4()))

    conversation_id: str | None = None

    trace_id: str | None = None

    ai: AIUsageModel | None = None

    def to_metadata(self) -> MetadataModel:
        """Convert execution context into response metadata."""

        return MetadataModel(
            request_id=self.request_id,
            trace_id=self.trace_id,
            ai=self.ai,
        )
