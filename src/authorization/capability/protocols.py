"""
Protocols for capability analysis.
"""

from __future__ import annotations

from typing import Protocol

from src.core.dto.capability import CapabilityAnalysisDTO


class CapabilityAnalyzerProtocol(Protocol):
    """
    Identifies capabilities requested by input.

    This protocol is classification-only.

    It does not:
    - authorize the actor,
    - evaluate RBAC,
    - evaluate approval policy,
    - create approvals,
    - execute actions.
    """

    def analyze(
        self,
        content: str,
    ) -> CapabilityAnalysisDTO:
        """
        Analyze input and identify requested capabilities.
        """
        ...
