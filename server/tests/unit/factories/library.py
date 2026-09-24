"""
Document factory.
"""

from __future__ import annotations

import factory

from adapters.persistence.sqlalchemy.mixins import generate_prefixed_uuid_pk
from adapters.persistence.sqlalchemy.models.library import Library
from core.enums import (
    LibrarySourceEnum,
    LibraryStatusEnum,
    StorageTypeEnum,
)
from tests.unit.factories.base import BaseFactory
from tests.unit.factories.conversation import ConversationFactory


class LibraryFactory(BaseFactory):
    """
    Factory for Library ORM model.
    """

    class Meta:
        model = Library

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("liby"),
    )

    conversation = factory.SubFactory(
        ConversationFactory,
    )

    conversation_id = factory.SelfAttribute(
        "conversation.id",
    )

    source_type = LibrarySourceEnum.FILE

    original_filename = factory.Sequence(
        lambda n: f"document_{n}.pdf",
    )

    filename = factory.Sequence(
        lambda n: f"doc_{n}.pdf",
    )

    mime_type = "application/pdf"

    size = 1024

    storage_type = StorageTypeEnum.LOCAL

    storage_path = factory.Sequence(
        lambda n: f"documents/doc_{n}.pdf",
    )

    checksum = factory.Sequence(
        lambda n: f"{n:064x}",
    )

    status = LibraryStatusEnum.UPLOADED
