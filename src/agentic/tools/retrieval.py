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
from application.context.request import get_request_context
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

        allowed_document_ids = get_request_context().allowed_document_ids

        try:
            results = await self._retriever.retrieve(
                query=query,
                top_k=top_k,
                allowed_source_ids=allowed_document_ids,
            )

        except Exception:
            log.exception("Retrieval failed.")
            return "Retrieval failed — please try again."

        if not results:
            return "No relevant content found."

        lines = [
            f"[{chunk.document_id} / chunk {chunk.metadata.get('chunk_index')}] "
            f"(relevance={score:.3f})\n{chunk.text}"
            for chunk, score in results
        ]

        return "\n\n".join(lines)
