"""
LangSmith observability configuration.

Provides application-level configuration for the LangSmith SDK.
AI components use the SDK's native tracing mechanism directly.
"""

from __future__ import annotations

import os

from src.core.config import Settings


def configure_langsmith(
    *,
    settings: Settings,
) -> None:
    """
    Configure LangSmith SDK tracing from application settings.

    The configuration is applied once during application startup.
    """

    if not settings.LANGSMITH_TRACING:
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_TRACING_V2"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_key
