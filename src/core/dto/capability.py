"""
Capability analysis data transfer objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.core.enums import ActionTypeEnum


@dataclass(frozen=True, slots=True)
class CapabilityAnalysisDTO:
    """
    Represents the actions/capabilities identified from a user request.

    This DTO describes what the user is requesting. It does not determine
    whether the user is authorized to perform those actions.
    """

    actions: tuple[ActionTypeEnum, ...]
    reason: str


@dataclass(frozen=True, slots=True)
class CapabilityMatchDTO:
    """
    Represents a capability classification result.
    """

    action: ActionTypeEnum
    score: float
