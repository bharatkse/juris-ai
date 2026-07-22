"""
User request and response schemas.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# =============================================================================
# Request Schemas
# =============================================================================


class CreateUserRequest(BaseModel):
    """
    Request payload for creating a new user.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    email: EmailStr = Field(
        description="User email address.",
    )

    full_name: str = Field(
        min_length=2,
        max_length=100,
        description="User full name.",
    )

    password: str = Field(
        min_length=8,
        max_length=128,
        description="User password.",
    )


class UpdateUserRequest(BaseModel):
    """
    Request payload for updating a user profile.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    email: EmailStr | None = Field(
        default=None,
        description="Updated email address.",
    )

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="Updated full name.",
    )


# =============================================================================
# Response Schemas
# =============================================================================


class UserResponse(BaseModel):
    """
    User response.
    """

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
    )

    id: UUID

    email: EmailStr

    full_name: str

    is_active: bool

    created_at: datetime

    updated_at: datetime
