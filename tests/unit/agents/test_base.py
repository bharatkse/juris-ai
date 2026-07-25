"""
Unit tests for BaseAgent.
"""

from __future__ import annotations

import pytest

from src.agents.base import BaseAgent


def test_base_agent_is_abstract() -> None:
    """
    It should not allow direct instantiation.
    """

    with pytest.raises(TypeError):
        BaseAgent()
