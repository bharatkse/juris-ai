"""
Upload file lookup tool.

Singleton, built once at startup. Takes the session FACTORY
(async_sessionmaker), not a bound session — a session held across
requests is not safe for concurrent use (SQLAlchemy AsyncSession is
not concurrency-safe), so every method opens and closes its own
short-lived session. allowed_library_file_ids is read from
request_context per call, same reasoning as retrieval.py.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.library_file import LibraryFileRepository
from agentic.tools.base import Tool
from application.context.request import get_request_context
from core.exceptions.domain import DomainError

log = get_logger(__name__)


class LibraryFileLookupTool(Tool):
    """
    Look up and list upload files already stored in Juris-agentic.
    """

    name = "library_file_lookup"
    description = (
        "Retrieve a specific upload file by ID, or list/search upload files "
        "already stored in Juris-AI by title or metadata."
    )

    def __init__(self, *, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _is_allowed(*, library_file_id: str, allowed_library_file_ids: set[str] | None) -> bool:
        return allowed_library_file_ids is None or library_file_id in allowed_library_file_ids

    async def get_library_file(self, *, library_file_id: str) -> str:
        log.debug("LibraryFileLookupTool.get_library_file(library_file_id=%s).", library_file_id)

        allowed_library_file_ids = get_request_context().allowed_library_file_ids

        if not self._is_allowed(
            library_file_id=library_file_id, allowed_library_file_ids=allowed_library_file_ids
        ):
            log.warning(
                "Denied upload file lookup for unauthorized library_file_id=%s.", library_file_id
            )
            return f"No upload file found with id '{library_file_id}'."

        try:
            async with self._session_factory() as session:
                repository = LibraryFileRepository(session=session)
                library_file = await repository.get_by_id(library_file_id=library_file_id)

        except DomainError:
            log.exception("Repository error looking up library_file_id=%s.", library_file_id)
            return "Upload file lookup failed — please try again."

        if library_file is None:
            return f"No upload file found with id '{library_file_id}'."

        return (
            f"Upload File {library_file.id}\n"
            f"Title: {library_file.title}\n"
            f"Status: {library_file.status}\n"
            f"---\n"
            f"{library_file.content}"
        )

    async def list_library_files(
        self,
        *,
        query: str | None = None,
        limit: int = 10,
    ) -> str:
        log.debug(
            "LibraryFileLookupTool.list_library_files(limit=%d, query_length=%d).",
            limit,
            len(query) if query else 0,
        )

        allowed_library_file_ids = get_request_context().allowed_library_file_ids

        try:
            fetch_limit = limit * 3 if allowed_library_file_ids is not None else limit

            async with self._session_factory() as session:
                repository = LibraryFileRepository(session=session)
                library_files = await repository.search(query=query, limit=fetch_limit)

        except DomainError:
            log.exception("Repository error listing upload files.")
            return "Upload file search failed — please try again."

        allowed = [
            d
            for d in library_files
            if self._is_allowed(
                library_file_id=d.id, allowed_library_file_ids=allowed_library_file_ids
            )
        ][:limit]

        if not allowed:
            return "No upload files found."

        return "\n".join(f"- {d.id}: {d.title} ({d.status})" for d in allowed)

    async def execute(
        self,
        *,
        library_file_id: str | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> str:
        """
        Unified entry point matching the Tool interface. Routes to
        get_contract when contract_id is given, otherwise list/search.
        """

        if library_file_id:
            return await self.get_library_file(library_file_id=library_file_id)

        return await self.list_library_files(query=query, limit=limit)
