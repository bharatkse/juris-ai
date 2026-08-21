"""
External action capability analysis.
"""

from __future__ import annotations

from src.authorization.capability.classifier import TFIDFCapabilityClassifier
from src.authorization.capability.examples import EXTERNAL_ACTION_EXAMPLES
from src.authorization.capability.protocols import CapabilityAnalyzer
from src.core.dto.capability import CapabilityAnalysisDTO


class ExternalActionAnalyzer(CapabilityAnalyzer):
    """
    Identifies externally impactful actions requested by the user.

    This analyzer does not determine whether the user is authorized
    to perform the action.
    """

    def __init__(
        self,
        classifier: TFIDFCapabilityClassifier | None = None,
    ) -> None:
        self._classifier = classifier or TFIDFCapabilityClassifier(
            examples=EXTERNAL_ACTION_EXAMPLES,
        )

    def analyze(
        self,
        content: str,
    ) -> CapabilityAnalysisDTO:
        matches = self._classifier.classify(content)

        actions = tuple(match.action for match in matches)

        return CapabilityAnalysisDTO(
            actions=actions,
            reason=self._build_reason(actions),
        )

    @staticmethod
    def _build_reason(actions) -> str:
        if not actions:
            return "No externally impactful action was identified."

        capabilities = ", ".join(action.value for action in actions)

        return "Detected externally impactful actions: " f"{capabilities}."
