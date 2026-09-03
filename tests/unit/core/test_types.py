"""
Unit tests for reusable identifier types.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from core.types import (
    ConversationEventId,
    ConversationId,
    LibraryFileId,
    UserId,
    _prefixed_id_field,
)


def test_prefixed_id_returns_field_metadata() -> None:
    """
    It should return Pydantic field metadata containing the
    prefixed identifier validation pattern.
    """

    prefixed_id = _prefixed_id_field(
        "test",
    )

    assert prefixed_id.description == "test identifier."

    assert prefixed_id.metadata

    assert prefixed_id.metadata[0].pattern == (r"^test_[0-9a-f]{32}$")


def test_user_id_accepts_valid_identifier() -> None:
    """
    It should accept a valid user identifier.
    """

    class Model(BaseModel):
        id: UserId

    model = Model(
        id="user_" + "a" * 32,
    )

    assert model.id == "user_" + "a" * 32


def test_user_id_rejects_invalid_identifier() -> None:
    """
    It should reject an invalid user identifier.
    """

    class Model(BaseModel):
        id: UserId

    with pytest.raises(
        ValidationError,
    ):
        Model(
            id="invalid",
        )


def test_conversation_id_accepts_valid_identifier() -> None:
    """
    It should accept a valid conversation identifier.
    """

    class Model(BaseModel):
        id: ConversationId

    model = Model(
        id="conv_" + "b" * 32,
    )

    assert model.id == "conv_" + "b" * 32


def test_conversation_event_id_accepts_valid_identifier() -> None:
    """
    It should accept a valid conversation event identifier.
    """

    class Model(BaseModel):
        id: ConversationEventId

    model = Model(
        id="evnt_" + "c" * 32,
    )

    assert model.id == "evnt_" + "c" * 32


def test_upload_file_id_enforces_prefix() -> None:
    """
    It should enforce the upload file identifier prefix.
    """

    class Model(BaseModel):
        id: LibraryFileId

    model = Model(
        id="libf_" + "d" * 32,
    )

    assert model.id == "libf_" + "d" * 32

    with pytest.raises(
        ValidationError,
    ):
        Model(
            id="user_" + "d" * 32,
        )


@pytest.mark.parametrize(
    ("identifier_type", "prefix"),
    [
        (UserId, "user"),
        (ConversationId, "conv"),
        (ConversationEventId, "evnt"),
        (LibraryFileId, "libf"),
    ],
)
def test_identifier_rejects_wrong_prefix(
    identifier_type,
    prefix: str,
) -> None:
    """
    It should reject identifiers with an incorrect prefix.
    """

    class Model(BaseModel):
        id: identifier_type

    with pytest.raises(ValidationError):
        Model(
            id=f"wrong_{'a' * 32}",
        )
