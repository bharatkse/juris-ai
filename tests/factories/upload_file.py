"""
Document factory.
"""

from __future__ import annotations

import factory

from adapters.persistence.sqlalchemy.mixins import generate_prefixed_uuid_pk
from adapters.persistence.sqlalchemy.models.library_file import LibraryFile
from core.enums import (
    LibraryFileSourceEnum,
    LibraryFileStatusEnum,
    StorageTypeEnum,
)
from tests.factories.base import BaseFactory
from tests.factories.conversation import ConversationFactory


class LibraryFileFactory(BaseFactory):
    """
    Factory for LibraryFile ORM model.
    """

    class Meta:
        model = LibraryFile

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("libf"),
    )

    conversation = factory.SubFactory(
        ConversationFactory,
    )

    conversation_id = factory.SelfAttribute(
        "conversation.id",
    )

    source_type = LibraryFileSourceEnum.FILE

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

    status = LibraryFileStatusEnum.UPLOADED
