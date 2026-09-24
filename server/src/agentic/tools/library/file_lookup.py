"""
Upload file lookup tool.

Singleton, built once at startup. Takes the session FACTORY
(async_sessionmaker), not a bound session — a session held across
requests is not safe for concurrent use (SQLAlchemy AsyncSession is
not concurrency-safe), so every method opens and closes its own
short-lived session. allowed_library_ids is read from
request_context per call, same reasoning as retrieval.py.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.library import LibraryRepository
from agentic.tools.base import Tool
from application.context.request import get_request_context
from core.exceptions.domain import DomainError

log = get_logger(__name__)


class LibraryLookupTool(Tool):
    """
    Look up and list upload files already stored in Juris-agentic.
    """

    name = "library_lookup"
    description = (
        "Retrieve a specific upload file by ID, or list/search upload files "
        "already stored in Juris-AI by title or metadata."
    )

    def __init__(self, *, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _is_allowed(*, library_id: str, allowed_library_ids: set[str] | None) -> bool:
        return allowed_library_ids is None or library_id in allowed_library_ids

    async def get_library(self, *, library_id: str) -> str:
        log.debug("LibraryLookupTool.get_library(library_id=%s).", library_id)

        allowed_library_ids = get_request_context().allowed_library_ids

        if not self._is_allowed(library_id=library_id, allowed_library_ids=allowed_library_ids):
            log.warning("Denied upload file lookup for unauthorized library_id=%s.", library_id)
            return f"No upload file found with id '{library_id}'."

        try:
            async with self._session_factory() as session:
                repository = LibraryRepository(session=session)
                library = await repository.get_by_id(library_id=library_id)

        except DomainError:
            log.exception("Repository error looking up library_id=%s.", library_id)
            return "Upload file lookup failed — please try again."

        if library is None:
            return f"No upload file found with id '{library_id}'."

        # Library has no `title`/`content` field -- it persists upload
        # metadata only (see LibraryRepository's own docstring: parsing/
        # text extraction/content are explicitly not this table's job).
        # filename falls back to original_filename, matching list_library()
        # below; full document content isn't stored inline here at all,
        # so this can only describe the file, not reproduce its text.
        display_name = library.filename or library.original_filename or library.id

        return (
            f"Upload File {library.id}\n"
            f"Filename: {display_name}\n"
            f"Status: {library.status}\n"
            f"Type: {library.mime_type or 'unknown'}\n"
            f"Storage path: {library.storage_path or 'not stored'}"
        )

    async def list_library(
        self,
        *,
        query: str | None = None,
        limit: int = 10,
    ) -> str:
        log.debug(
            "LibraryLookupTool.list_library(limit=%d, query_length=%d).",
            limit,
            len(query) if query else 0,
        )

        allowed_library_ids = get_request_context().allowed_library_ids

        try:
            async with self._session_factory() as session:
                repository = LibraryRepository(session=session)
                # allowed_library_ids is now applied in the SQL WHERE
                # clause itself (LibraryRepository.search()), not just
                # filtered out of an unscoped result afterward -- the
                # comprehension below is defense-in-depth on top of
                # that, not the enforcement point.
                library = await repository.search(
                    query=query,
                    limit=limit,
                    allowed_library_ids=allowed_library_ids,
                )

        except DomainError:
            log.exception("Repository error listing upload files.")
            return "Upload file search failed — please try again."

        allowed = [
            d
            for d in library
            if self._is_allowed(library_id=d.id, allowed_library_ids=allowed_library_ids)
        ][:limit]

        if not allowed:
            return "No upload files found."

        return "\n".join(
            f"- {d.id}: {d.filename or d.original_filename or d.id} ({d.status})" for d in allowed
        )

    async def execute(
        self,
        *,
        library_id: str | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> str:
        """
        Unified entry point matching the Tool interface. Routes to
        get_contract when contract_id is given, otherwise list/search.
        """

        if library_id:
            return await self.get_library(library_id=library_id)

        return await self.list_library(query=query, limit=limit)
