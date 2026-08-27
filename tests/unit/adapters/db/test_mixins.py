"""
Unit tests for database mixins.
"""

from __future__ import annotations

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from adapters.persistence.sqlalchemy.base import Base
from adapters.persistence.sqlalchemy.mixins import PrimaryKeyMixin, TimestampMixin
from tests.helpers.assertions import assert_prefixed_uuid


class DummyPrimaryKeyModel(
    Base,
    PrimaryKeyMixin,
):
    """
    Test model for PrimaryKeyMixin.
    """

    __tablename__ = "dummy_primary_key_models"

    _id_prefix = "dummy"

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )


class DummyTimestampModel(
    Base,
    TimestampMixin,
):
    """
    Test model for TimestampMixin.
    """

    __tablename__ = "dummy_timestamp_models"

    name: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
    )


@pytest.mark.asyncio
async def test_primary_key_is_generated(
    db_session,
) -> None:
    model = DummyPrimaryKeyModel(
        name="John",
    )

    db_session.add(model)
    await db_session.flush()

    assert model.id is not None


@pytest.mark.asyncio
async def test_primary_key_has_expected_format(db_session) -> None:
    """
    It should generate a prefixed UUID.
    """

    model = DummyPrimaryKeyModel(
        name="John",
    )
    db_session.add(model)
    await db_session.flush()
    assert_prefixed_uuid(
        model.id,
        prefix="dummy",
    )


@pytest.mark.asyncio
async def test_primary_key_is_unique(db_session) -> None:
    """
    It should generate unique identifiers.
    """

    model1 = DummyPrimaryKeyModel(
        name="John",
    )
    db_session.add(model1)
    model2 = DummyPrimaryKeyModel(
        name="Jane",
    )
    db_session.add(model2)
    await db_session.flush()
    assert model1.id != model2.id


@pytest.mark.asyncio
async def test_created_at_is_initialized(
    db_session,
) -> None:
    model = DummyTimestampModel(
        name="John",
    )

    db_session.add(model)
    await db_session.flush()

    assert model.created_at is not None
    assert model.updated_at is not None


def test_created_and_updated_at_are_equal_on_creation() -> None:
    """
    created_at and updated_at should be equal when the model
    is first created.
    """

    model = DummyTimestampModel(
        name="John",
    )

    assert model.created_at == model.updated_at
