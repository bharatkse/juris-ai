"""
LangSmith observability configuration.

Provides application-level configuration for the LangSmith SDK.
AI components use the SDK's native tracing mechanism directly.
"""

from __future__ import annotations

import os

from config.settings import Settings


def configure_langsmith(
    *,
    settings: Settings,
) -> None:
    """
    Configure LangSmith SDK tracing from application settings.

    The configuration is applied once during application startup.
    """

    if not settings.llm.LANGSMITH_TRACING:
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_TRACING_V2"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.llm.LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_PROJECT"] = settings.llm.LANGSMITH_PROJECT
    os.environ["LANGSMITH_API_KEY"] = settings.llm.langsmith_key
