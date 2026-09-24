"""
Capability analysis data transfer objects.

Capability analysis identifies what capabilities are requested.
It does not perform authorization, approval, or execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.enums import ActionTypeEnum


@dataclass(frozen=True, slots=True)
class CapabilityMatchDTO:
    """
    Represents one capability identified from input.

    The score represents the classifier confidence/similarity.
    It is not an authorization decision.
    """

    action_type: ActionTypeEnum
    score: float


@dataclass(frozen=True, slots=True)
class CapabilityAnalysisDTO:
    """
    Represents capabilities identified from a request.

    This describes what the requester appears to be asking for.

    It does not determine:
    - authorization,
    - RBAC permissions,
    - human approval,
    - execution.
    """

    action_types: tuple[ActionTypeEnum, ...]
    reason: str

    @property
    def has_capabilities(self) -> bool:
        """
        Return whether any capability was identified.
        """

        return bool(self.action_types)
