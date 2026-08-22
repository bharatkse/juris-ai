"""
Capability analysis implementation.
"""

from __future__ import annotations

from src.authorization.capability.classifier import TFIDFCapabilityClassifier
from src.authorization.capability.examples import CAPABILITY_EXAMPLES
from src.authorization.capability.protocols import CapabilityAnalyzerProtocol
from src.core.dto.capability import CapabilityAnalysisDTO
from src.core.enums import ActionTypeEnum


class DefaultCapabilityAnalyzer(CapabilityAnalyzerProtocol):
    """
    Default capability analyzer.

    Identifies capabilities requested by natural-language input.

    Classification is independent from authorization and approval.
    """

    def __init__(
        self,
        classifier: TFIDFCapabilityClassifier | None = None,
    ) -> None:
        self._classifier = classifier or TFIDFCapabilityClassifier(
            examples=CAPABILITY_EXAMPLES,
        )

    def analyze(
        self,
        content: str,
    ) -> CapabilityAnalysisDTO:
        """
        Analyze input and identify requested capabilities.
        """

        matches = self._classifier.classify(
            content,
        )

        actions = tuple(match.action for match in matches)

        return CapabilityAnalysisDTO(
            actions=actions,
            reason=self._build_reason(
                actions,
            ),
        )

    @staticmethod
    def _build_reason(
        actions: tuple[ActionTypeEnum, ...],
    ) -> str:
        """
        Build a human-readable explanation of the capability analysis.
        """

        if not actions:
            return "No supported capability was identified."

        capabilities = ", ".join(action.value for action in actions)

        return "Detected requested capabilities: " f"{capabilities}."
