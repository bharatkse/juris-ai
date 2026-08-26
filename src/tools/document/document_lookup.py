"""
Document lookup tool.

Singleton, built once at startup. Takes the session FACTORY
(async_sessionmaker), not a bound session — a session held across
requests is not safe for concurrent use (SQLAlchemy AsyncSession is
not concurrency-safe), so every method opens and closes its own
short-lived session. allowed_document_ids is read from
request_context per call, same reasoning as retrieval.py.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.core.exceptions.domain import DomainError
from src.core.logger import get_logger
from src.core.request_context import get_request_context
from src.repositories.document import DocumentRepository
from src.tools.base import Tool

log = get_logger(__name__)


class DocumentLookupTool(Tool):
    """
    Look up and list contracts/documents already stored in Juris-AI.
    """

    name = "document_lookup"
    description = (
        "Retrieve a specific contract by ID, or list/search documents "
        "already stored in Juris-AI by title or metadata."
    )

    def __init__(self, *, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _is_allowed(*, document_id: str, allowed_document_ids: set[str] | None) -> bool:
        return allowed_document_ids is None or document_id in allowed_document_ids

    async def get_contract(self, *, contract_id: str) -> str:
        log.debug("DocumentLookupTool.get_contract(contract_id=%s).", contract_id)

        allowed_document_ids = get_request_context().allowed_document_ids

        if not self._is_allowed(document_id=contract_id, allowed_document_ids=allowed_document_ids):
            log.warning("Denied contract lookup for unauthorized contract_id=%s.", contract_id)
            return f"No contract found with id '{contract_id}'."

        try:
            async with self._session_factory() as session:
                repository = DocumentRepository(session=session)
                document = await repository.get_by_id(document_id=contract_id)

        except DomainError:
            log.exception("Repository error looking up contract_id=%s.", contract_id)
            return "Contract lookup failed — please try again."

        if document is None:
            return f"No contract found with id '{contract_id}'."

        return (
            f"Contract {document.id}\n"
            f"Title: {document.title}\n"
            f"Status: {document.status}\n"
            f"---\n"
            f"{document.content}"
        )

    async def list_documents(
        self,
        *,
        query: str | None = None,
        limit: int = 10,
    ) -> str:
        log.debug(
            "DocumentLookupTool.list_documents(query=%r, limit=%d).",
            query,
            limit,
        )

        allowed_document_ids = get_request_context().allowed_document_ids

        try:
            fetch_limit = limit * 3 if allowed_document_ids is not None else limit

            async with self._session_factory() as session:
                repository = DocumentRepository(session=session)
                documents = await repository.search(query=query, limit=fetch_limit)

        except DomainError:
            log.exception("Repository error listing documents (query=%r).", query)
            return "Document search failed — please try again."

        allowed = [
            d
            for d in documents
            if self._is_allowed(document_id=d.id, allowed_document_ids=allowed_document_ids)
        ][:limit]

        if not allowed:
            return "No documents found."

        return "\n".join(f"- {d.id}: {d.title} ({d.status})" for d in allowed)

    async def execute(
        self,
        *,
        contract_id: str | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> str:
        """
        Unified entry point matching the Tool interface. Routes to
        get_contract when contract_id is given, otherwise list/search.
        """

        if contract_id:
            return await self.get_contract(contract_id=contract_id)

        return await self.list_documents(query=query, limit=limit)
