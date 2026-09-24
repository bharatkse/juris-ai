"""
LangSmith observability configuration.

Provides application-level configuration for the LangSmith SDK.
AI components use the SDK's native tracing mechanism directly.
"""

from __future__ import annotations

import os

from adapters.observability.logger import get_logger
from config.settings import Settings

log = get_logger(__name__)


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

    api_key = settings.llm.langsmith_key

    if api_key is None:
        # Previously os.environ[...] = None, a TypeError at startup.
        log.warning(
            "LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is not set; tracing disabled."
        )
        return

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_TRACING_V2"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.llm.LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_PROJECT"] = settings.llm.LANGSMITH_PROJECT
    os.environ["LANGSMITH_API_KEY"] = api_key
