"""
Retrieval tool.

A singleton, built once at startup alongside HybridRetriever's
embedding/reranker models (factories/rag.py) — same lifetime as the
rest of the tool registry. allowed_document_ids is read from
request_context at execute()-time, NOT bound at construction — a
singleton tool cannot hold a fixed per-request ACL value without
leaking one requester's permissions onto every subsequent request.

Still never exposed as an execute() parameter an LLM could set: it
comes from core.request_context, populated server-side by
middleware before the agent ever runs, invisible to and unsettable by
the model.
"""

from __future__ import annotations

from adapters.observability.logger import get_logger
from agentic.tools.base import Tool
from rag.hybrid_retriever import HybridRetriever

log = get_logger(__name__)


class RetrieverTool(Tool):
    """
    Retrieval tool backed by the hybrid (vector + keyword + rerank)
    pipeline.
    """

    name = "retriever"
    description = (
        "Retrieve relevant document chunks for a query using hybrid "
        "search (semantic + keyword) with reranking, over indexed "
        "contracts and legal documents."
    )

    def __init__(self, *, hybrid_retriever: HybridRetriever) -> None:
        self._retriever = hybrid_retriever

    async def execute(self, *, query: str, top_k: int = 5) -> str:
        log.debug("RetrieverTool.execute(top_k=%d, query_length=%d).", top_k, len(query))

        try:
            results = await self._retriever.retrieve(
                query=query,
                top_k=top_k,
            )

        except Exception:
            log.exception("Retrieval failed.")
            return "Retrieval failed — please try again."

        if not results:
            return "No relevant content found."

        # title is only present on chunks ingested after bug #6's fix;
        # anything indexed before that falls back to source here --
        # that's expected, not a bug.
        lines = [
            f"[{result.chunk.metadata.get('title') or result.chunk.source} / chunk "
            f"{result.chunk.metadata.get('sequence')}] "
            f"(relevance={result.score:.3f})\n{result.chunk.text}"
            for result in results
        ]

        return "\n\n".join(lines)
