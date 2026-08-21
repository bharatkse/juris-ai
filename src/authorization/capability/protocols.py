"""
Protocols for capability analysis.
"""

from typing import Protocol

from src.core.dto.capability import CapabilityAnalysisDTO


class CapabilityAnalyzer(Protocol):
    """
    Analyzes user input and identifies requested capabilities.

    The analyzer determines what the user is asking to do.
    It does not perform authorization or permission checks.
    """

    def analyze(
        self,
        content: str,
    ) -> CapabilityAnalysisDTO:
        """
        Analyze user content and return the requested capabilities.
        """
        ...
