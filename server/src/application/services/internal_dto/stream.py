"""
Chat service streaming models.
"""

from __future__ import annotations

from agentic.orchestration.schemas.response import OrchestratorStreamChunk

# AIOrchestrator.stream() (agentic/orchestration/) is the only
# producer of this shape; ChatService.stream_chat() (application/)
# just needs a name for it at this layer. A separate,
# application-layer dataclass here would either duplicate
# OrchestratorStreamChunk's fields (drifting out of sync -- the exact
# bug class Phase 1 of this feature already fixed once, for this same
# file's response type) or force agentic/ to import from application/
# to construct it directly, backwards for this project's layering
# (application/ already depends on agentic/, never the reverse -- see
# OrchestratorStreamChunk's own docstring). A plain alias avoids both.
ChatStreamChunkDTO = OrchestratorStreamChunk
