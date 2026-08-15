"""
Unit tests for reusable type aliases.
"""

from __future__ import annotations

from typing import Annotated, get_args, get_origin

import pytest
from pydantic import BaseModel, ValidationError

from src.core.types import ConversationEventId, ConversationId, PrefixedId, UserId


def test_prefixed_id_returns_annotated_type() -> None:
    """
    It should return an Annotated string type.
    """

    prefixed_id = PrefixedId(
        "test",
    )

    assert (
        get_origin(
            prefixed_id,
        )
        is Annotated
    )

    assert (
        get_args(
            prefixed_id,
        )[0]
        is str
    )


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
        id="event_" + "c" * 32,
    )

    assert model.id == "event_" + "c" * 32


def test_prefixed_id_uses_requested_prefix() -> None:
    """
    It should enforce the configured identifier prefix.
    """

    class Model(BaseModel):
        id: PrefixedId("doc")

    model = Model(
        id="doc_" + "d" * 32,
    )

    assert model.id == "doc_" + "d" * 32

    with pytest.raises(
        ValidationError,
    ):
        Model(
            id="user_" + "d" * 32,
        )
