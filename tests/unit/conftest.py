"""
Unit pytest configuration.
"""

from __future__ import annotations

import os

pytest_plugins = [
    "tests.unit.fixtures.environment",
    "tests.unit.fixtures.faker",
    "tests.unit.fixtures.adapters.database",
    "tests.unit.fixtures.adapters.repositories",
    "tests.unit.fixtures.adapters.clients.storage",
    "tests.unit.fixtures.adapters.clients.llm",
    "tests.unit.fixtures.adapters.clients.groq",
    "tests.unit.fixtures.adapters.security",
    "tests.unit.fixtures.factories.config",
    "tests.unit.fixtures.factories.conversation",
    "tests.unit.fixtures.api.client",
    "tests.unit.fixtures.application.services",
    "tests.unit.fixtures.application.authorization",
    "tests.unit.fixtures.agentic.orchestrator",
    "tests.unit.fixtures.agentic.planning",
    "tests.unit.fixtures.agentic.execution",
    "tests.unit.fixtures.agentic.agents",
]

os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
