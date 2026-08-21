"""
Approval-related exceptions.
"""

from __future__ import annotations

from src.core.exceptions.base import AIError


class ApprovalError(AIError):
    """
    Base exception for approval-related failures.
    """


class ApprovalNotFoundError(ApprovalError):
    """
    Raised when an approval request cannot be found.
    """


class ApprovalExpiredError(ApprovalError):
    """
    Raised when an approval request has expired.
    """


class ApprovalNotActionableError(ApprovalError):
    """
    Raised when an approval is not in a state that accepts
    the requested lifecycle transition.
    """


class ApprovalValidationError(ApprovalError):
    """
    Raised when an approval cannot be validated for execution.
    """
