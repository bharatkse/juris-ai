"""
Offline retrieval evaluation runner.

Executes a golden retrieval dataset against the configured RAG
retriever and aggregates the resulting metric evaluations.

This module is evaluation orchestration only.

It does not:

    - modify the production retriever
    - implement retrieval
    - calculate retrieval metrics
    - call an LLM
    - access persistence directly
"""

from __future__ import annotations

from typing import Protocol


class RetrieverProtocol(Protocol):
    """
    Minimal retrieval capability required by the evaluation runner.
    """

    async def retrieve(
        self,
        *,
        query: str,
        top_k: int,
        allowed_source_ids: set[str] | None = None,
    ) -> list:
        """
        Retrieve ranked results for an evaluation query.
        """

        ...
