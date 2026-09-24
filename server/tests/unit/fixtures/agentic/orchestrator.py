"""
Orchestrator fixtures.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agentic.orchestration.orchestrator import AIOrchestrator


@pytest.fixture
def mock_orchestrator() -> MagicMock:
    """
    Return a mocked AI orchestrator.
    """

    orchestrator = MagicMock(
        spec=AIOrchestrator,
    )

    orchestrator.handle = AsyncMock()
    orchestrator.stream = MagicMock()

    return orchestrator
