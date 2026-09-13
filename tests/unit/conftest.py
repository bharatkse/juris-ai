"""
Unit pytest configuration.
"""

from __future__ import annotations

import os

pytest_plugins = [
    "tests.fixtures.environment",
    "tests.fixtures.faker",
    "tests.fixtures.adapters.database",
    "tests.fixtures.adapters.repositories",
    "tests.fixtures.adapters.clients.storage",
    "tests.fixtures.adapters.clients.llm",
    "tests.fixtures.adapters.clients.groq",
    "tests.fixtures.adapters.security",
    "tests.fixtures.factories.config",
    "tests.fixtures.factories.conversation",
    "tests.fixtures.api.client",
    "tests.fixtures.application.services",
    "tests.fixtures.application.authorization",
    "tests.fixtures.agentic.orchestrator",
    "tests.fixtures.agentic.planning",
    "tests.fixtures.agentic.execution",
    "tests.fixtures.agentic.agents",
]

os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
