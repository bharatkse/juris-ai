"""
Top-level pytest configuration.

pytest_plugins must be declared here, not in tests/unit/conftest.py --
pytest 8.4+ hard-errors on 'pytest_plugins' in a non-top-level conftest
(previously a warning under 8.3.x, which is why this wasn't caught
until dependencies were freshly resolved against the ^8.3.0 pin).
"""

from __future__ import annotations

import os
import shutil

from tests.unit.fixtures.temp_database import make_temp_database

# Each pytest process gets its own SQLite database for the unit tests, in a
# temp directory removed at the end of the run, instead of one shared
# ./pytests.db: two runs at once (the Stop hook's and a manual one, or two
# checkouts) used to create and drop each other's tables. Set before
# pytest_plugins load, since the fixture modules import application code
# that reads settings (TEST_DATABASE_URL, config/database.py). setdefault so
# an explicit TEST_DATABASE_URL still wins.
if "TEST_DATABASE_URL" not in os.environ:
    os.environ["TEST_DATABASE_URL"], _TEST_DATABASE_DIR = make_temp_database()
else:
    _TEST_DATABASE_DIR = None


def pytest_unconfigure() -> None:
    if _TEST_DATABASE_DIR is not None:
        shutil.rmtree(_TEST_DATABASE_DIR, ignore_errors=True)


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
