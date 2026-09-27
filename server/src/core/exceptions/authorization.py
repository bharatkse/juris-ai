"""
Authorization-related exceptions.
"""

from core.exceptions.base import DomainError


class AuthorizationError(DomainError):
    """
    Raised when an actor is not authorized to perform an action.
    """

    def __init__(
        self,
        message: str = "User is not authorized to perform this action.",
    ) -> None:
        super().__init__(message)


class ApprovalRequiredError(AuthorizationError):
    """
    Raised when an action requires human approval before execution.
    """

    def __init__(
        self,
        *,
        approval_id: str,
    ) -> None:
        self.approval_id = approval_id

        super().__init__(
            f"Human approval required: {approval_id}",
        )
