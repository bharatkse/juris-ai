"""
Unit tests for reusable identifier types.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from core.types import (
    AgentActionId,
    ApprovalId,
    ConversationEventId,
    ConversationId,
    KnowledgeChunkId,
    KnowledgeEmbeddingId,
    KnowledgeSourceId,
    LibraryId,
    UserId,
    prefixed_id_validator,
)


def test_prefixed_id_returns_field_metadata() -> None:
    """
    It should return Pydantic field metadata containing the
    prefixed identifier validation pattern.
    """

    prefixed_id = prefixed_id_validator("test")

    assert prefixed_id.description == "test identifier."
    assert prefixed_id.metadata
    assert prefixed_id.metadata[0].pattern == r"^test_[0-9a-f]{32}$"


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

    with pytest.raises(ValidationError):
        Model(id="invalid")


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


def test_library_id_enforces_prefix() -> None:
    """
    It should enforce the library file identifier prefix.
    """

    class Model(BaseModel):
        id: LibraryId

    model = Model(
        id="liby_" + "d" * 32,
    )

    assert model.id == "liby_" + "d" * 32

    with pytest.raises(ValidationError):
        Model(
            id="user_" + "d" * 32,
        )


@pytest.mark.parametrize(
    ("identifier_type", "valid_identifier"),
    [
        (UserId, "user_" + "a" * 32),
        (ConversationId, "conv_" + "b" * 32),
        (ConversationEventId, "evnt_" + "c" * 32),
        (AgentActionId, "actn_" + "d" * 32),
        (ApprovalId, "appr_" + "e" * 32),
        (LibraryId, "liby_" + "f" * 32),
        (KnowledgeSourceId, "ksrc_" + "0" * 32),
        (KnowledgeChunkId, "kchn_" + "1" * 32),
        (KnowledgeEmbeddingId, "kemb_" + "2" * 32),
    ],
)
def test_identifier_accepts_valid_identifier(
    identifier_type,
    valid_identifier: str,
) -> None:
    """
    It should accept a valid identifier for every supported identifier type.
    """

    class Model(BaseModel):
        id: identifier_type

    model = Model(id=valid_identifier)

    assert model.id == valid_identifier


@pytest.mark.parametrize(
    ("identifier_type", "prefix"),
    [
        (UserId, "user"),
        (ConversationId, "conv"),
        (ConversationEventId, "evnt"),
        (AgentActionId, "actn"),
        (ApprovalId, "appr"),
        (LibraryId, "liby"),
        (KnowledgeSourceId, "ksrc"),
        (KnowledgeChunkId, "kchn"),
        (KnowledgeEmbeddingId, "kemb"),
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


@pytest.mark.parametrize(
    ("identifier_type", "prefix"),
    [
        (UserId, "user"),
        (ConversationId, "conv"),
        (ConversationEventId, "evnt"),
        (AgentActionId, "actn"),
        (ApprovalId, "appr"),
        (LibraryId, "liby"),
        (KnowledgeSourceId, "ksrc"),
        (KnowledgeChunkId, "kchn"),
        (KnowledgeEmbeddingId, "kemb"),
    ],
)
def test_identifier_rejects_non_hex_characters(
    identifier_type,
    prefix: str,
) -> None:
    """
    It should reject identifiers containing non-hexadecimal characters.
    """

    class Model(BaseModel):
        id: identifier_type

    with pytest.raises(ValidationError):
        Model(
            id=f"{prefix}_{'g' * 32}",
        )
