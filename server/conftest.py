"""
Top-level pytest configuration.

pytest_plugins must be declared here, not in tests/unit/conftest.py --
pytest 8.4+ hard-errors on 'pytest_plugins' in a non-top-level conftest
(previously a warning under 8.3.x, which is why this wasn't caught
until dependencies were freshly resolved against the ^8.3.0 pin).
"""

from __future__ import annotations

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
