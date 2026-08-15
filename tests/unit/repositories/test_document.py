"""
Tests for document repository.
"""

from __future__ import annotations

import pytest

from src.core.enums import DocumentStatusEnum
from src.repositories.document import DocumentRepository
from tests.factories.conversation import ConversationFactory
from tests.factories.document import DocumentFactory

pytestmark = pytest.mark.asyncio


async def test_create_document(
    document_repository: DocumentRepository,
) -> None:
    """
    Test creating a document.
    """

    document = DocumentFactory.build()

    created_document = await document_repository.create(
        document=document,
    )

    assert created_document == document
    assert created_document.id is not None


async def test_get_document(
    document_repository: DocumentRepository,
) -> None:
    """
    Test retrieving a document by identifier.
    """

    document = await document_repository.create(
        document=DocumentFactory.build(),
    )

    retrieved_document = await document_repository.get(
        document_id=document.id,
    )

    assert retrieved_document == document


async def test_get_document_not_found(
    document_repository: DocumentRepository,
) -> None:
    """
    Test retrieving a missing document.
    """

    document = await document_repository.get(
        document_id="doc_missing",
    )

    assert document is None


async def test_list_by_conversation_returns_documents(
    document_repository: DocumentRepository,
) -> None:
    """
    Test listing documents for a conversation.
    """

    conversation = ConversationFactory.build()

    first_document = await document_repository.create(
        document=DocumentFactory.build(
            conversation=conversation,
        ),
    )

    second_document = await document_repository.create(
        document=DocumentFactory.build(
            conversation=conversation,
        ),
    )

    documents = await document_repository.list_by_conversation(
        conversation_id=conversation.id,
    )

    assert documents == [
        first_document,
        second_document,
    ]


async def test_list_by_conversation_returns_empty_list(
    document_repository: DocumentRepository,
) -> None:
    """
    Test listing documents when none exist.
    """

    conversation = ConversationFactory.build()

    documents = await document_repository.list_by_conversation(
        conversation_id=conversation.id,
    )

    assert documents == []


async def test_update_document(
    document_repository: DocumentRepository,
) -> None:
    """
    Test updating a document.
    """

    document = await document_repository.create(
        document=DocumentFactory.build(),
    )

    document.status = DocumentStatusEnum.READY

    updated_document = await document_repository.update(
        document=document,
    )

    assert updated_document.status == DocumentStatusEnum.READY

    retrieved_document = await document_repository.get(
        document_id=document.id,
    )

    assert retrieved_document is not None
    assert retrieved_document.status == DocumentStatusEnum.READY


async def test_delete_document(
    document_repository: DocumentRepository,
) -> None:
    """
    Test deleting a document.
    """

    document = await document_repository.create(
        document=DocumentFactory.build(),
    )

    await document_repository.delete(
        document=document,
    )

    assert (
        await document_repository.get(
            document_id=document.id,
        )
        is None
    )
