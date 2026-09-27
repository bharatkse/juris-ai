from core.exceptions.base import AppError


class DatabaseError(AppError):
    """Any database operation failure."""
