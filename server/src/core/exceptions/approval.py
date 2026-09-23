"""
Approval-related exceptions.
"""

from __future__ import annotations

from core.constants import ERROR_FORBIDDEN, HTTP_403_FORBIDDEN
from core.exceptions.base import AIError


class ApprovalError(AIError):
    """
    Base exception for approval-related failures.
    """


class ApprovalNotFoundError(ApprovalError):
    """
    Raised when an approval request cannot be found.
    """


class ApprovalForbiddenError(ApprovalError):
    """
    Raised when an authenticated user acts on an approval they don't own.

    Only the user who requested an approval may decide it.
    """

    status_code = HTTP_403_FORBIDDEN
    error_code = ERROR_FORBIDDEN


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
