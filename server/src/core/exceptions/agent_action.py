"""
Agent action exceptions.
"""

from __future__ import annotations

from core.exceptions.base import AIError


class AgentActionError(AIError):
    """
    Base exception for AgentAction application failures.
    """
