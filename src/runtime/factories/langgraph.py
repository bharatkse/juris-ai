"""
LangGraph runtime infrastructure factory.
"""

from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def create_checkpointer(
    *,
    checkpointer: AsyncPostgresSaver,
) -> AsyncPostgresSaver:
    """
    Return the configured LangGraph PostgreSQL checkpointer.
    """

    return checkpointer
