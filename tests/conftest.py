"""
Global pytest configuration.
"""

from __future__ import annotations

pytest_plugins = [
    "tests.fixtures.faker",
    "tests.fixtures.database",
    "tests.fixtures.repositories",
    "tests.fixtures.clients",
    "tests.fixtures.agents",
    "tests.fixtures.services",
    "tests.fixtures.factories",
    "tests.fixtures.api",
    "tests.fixtures.groq",
    "tests.fixtures.security",
    "tests.fixtures.environment",
]
