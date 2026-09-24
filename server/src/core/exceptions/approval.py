"""
Approval-related exceptions.
"""

from __future__ import annotations

from core.constants import (
    ERROR_FORBIDDEN,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
    HTTP_410_GONE,
)
from core.exceptions.base import AIError


class ApprovalError(AIError):
    """
    Base exception for approval-related failures.
    """


class ApprovalNotFoundError(ApprovalError):
    """
    Raised when an approval request cannot be found.
    """

    status_code = HTTP_404_NOT_FOUND
    error_code = "APPROVAL_NOT_FOUND"


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

    status_code = HTTP_410_GONE
    error_code = "APPROVAL_EXPIRED"


class ApprovalNotActionableError(ApprovalError):
    """
    Raised when an approval is not in a state that accepts
    the requested lifecycle transition (it has already been decided).
    """

    status_code = HTTP_409_CONFLICT
    error_code = "APPROVAL_ALREADY_DECIDED"


class ApprovalValidationError(ApprovalError):
    """
    Raised when an approval cannot be validated for execution.
    """
