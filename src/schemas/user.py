"""
User request and response schemas.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from src.core.enums import Gender
from src.core.types import UserId

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

    first_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    last_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    gender: Gender | None = None

    phone_number: str | None = Field(
        default=None,
        min_length=10,
        max_length=20,
    )

    date_of_birth: date | None = None
    password: str = Field(
        min_length=8,
        max_length=128,
        description="User password.",
    )

    confirm_password: str = Field(
        min_length=8,
        max_length=128,
        description="Confirmation of the user password.",
    )

    @model_validator(mode="after")
    def validate_passwords(self) -> CreateUserRequest:
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class UpdateUserRequest(BaseModel):
    """
    Request payload for updating a user profile.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    first_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    last_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=100,
    )

    gender: Gender | None = None

    phone_number: str | None = Field(
        default=None,
        min_length=10,
        max_length=20,
    )

    date_of_birth: date | None = None


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

    id: UserId

    email: EmailStr

    first_name: str | None

    last_name: str | None

    gender: Gender | None

    phone_number: str | None

    date_of_birth: date | None

    created_at: datetime

    updated_at: datetime
