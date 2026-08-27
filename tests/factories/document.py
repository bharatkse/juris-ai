"""
Document factory.
"""

from __future__ import annotations

import factory

from adapters.persistence.sqlalchemy.mixins import generate_prefixed_uuid_pk
from adapters.persistence.sqlalchemy.models.document import Document
from core.enums import DocumentStatusEnum, StorageTypeEnum
from tests.factories.base import BaseFactory
from tests.factories.conversation import ConversationFactory


class DocumentFactory(BaseFactory):
    """
    Factory for Document ORM model.
    """

    class Meta:
        model = Document

    id = factory.LazyFunction(
        lambda: generate_prefixed_uuid_pk("doct"),
    )

    conversation = factory.SubFactory(
        ConversationFactory,
    )

    conversation_id = factory.SelfAttribute(
        "conversation.id",
    )

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

    status = DocumentStatusEnum.UPLOADED
