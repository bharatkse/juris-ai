"""
LangGraph PostgreSQL checkpointer.
"""

from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from src.core.config import get_settings


def create_checkpointer() -> AsyncPostgresSaver:
    """
    Create the LangGraph PostgreSQL checkpointer.

    The checkpointer is responsible for durable LangGraph
    execution state and pause/resume support.

    It is intentionally separate from the application's
    SQLAlchemy persistence layer.
    """

    settings = get_settings()

    return AsyncPostgresSaver.from_conn_string(
        settings.database_url,
    )
