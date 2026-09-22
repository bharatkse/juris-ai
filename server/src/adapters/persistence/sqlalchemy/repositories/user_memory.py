"""
User memory repository.

This is the tenant-isolation boundary for user memories. Two rules hold
for every method here, and both are enforced by structure rather than by
caller discipline:

1. Every public method takes a required, keyword-only ``user_id``.
2. Every statement is built from ``_scoped()``, which already carries the
   ``user_id`` predicate -- there is no code path that builds a
   UserMemory query without one, and no method that looks a row up by id
   alone. A memory id belonging to another user is simply "not found".

tests/unit/adapters/repositories/test_user_memory.py asserts rule 1 for
every public method, so adding an unscoped method fails the suite.

"Live" means status == ACTIVE and not past expires_at. Expired rows are
treated as inactive at query time; they are only physically removed by
purge_expired().
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

from sqlalchemy import ColumnElement, CursorResult, Select, and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.persistence.sqlalchemy.models.user_memory import UserMemory
from adapters.persistence.sqlalchemy.repositories.base import BaseRepository
from core.enums import UserMemoryKindEnum, UserMemoryStatusEnum
from core.types import UserId, UserMemoryId


class UserMemoryRepository(
    BaseRepository[UserMemory],
):
    """
    Repository responsible for UserMemory persistence.
    """

    _model = UserMemory

    def __init__(
        self,
        *,
        session: AsyncSession,
    ) -> None:
        super().__init__(session=session)

    # ------------------------------------------------------------------
    # Statement construction -- the only place a query is started.
    # ------------------------------------------------------------------

    @staticmethod
    def _require_user_id(
        user_id: str,
    ) -> None:
        if not user_id:
            raise ValueError("user_id is required for every user memory query.")

    def _scoped(
        self,
        *,
        user_id: UserId,
    ) -> Select[Any]:
        self._require_user_id(user_id)

        return select(UserMemory).where(
            UserMemory.user_id == user_id,
        )

    @staticmethod
    def _live(
        *,
        now: datetime,
    ) -> tuple[ColumnElement[bool], ...]:
        return (
            UserMemory.status == UserMemoryStatusEnum.ACTIVE.value,
            or_(
                UserMemory.expires_at.is_(None),
                UserMemory.expires_at > now,
            ),
        )

    @staticmethod
    def _visible(
        *,
        now: datetime,
    ) -> tuple[ColumnElement[bool], ...]:
        """
        What a user may see about themselves: active or pending,
        not expired. Superseded rows are history, not memory.
        """

        return (
            UserMemory.status.in_(
                (
                    UserMemoryStatusEnum.ACTIVE.value,
                    UserMemoryStatusEnum.PENDING.value,
                ),
            ),
            or_(
                UserMemory.expires_at.is_(None),
                UserMemory.expires_at > now,
            ),
        )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def add(
        self,
        *,
        user_id: UserId,
        kind: UserMemoryKindEnum,
        content: str,
        content_hash: str,
        embedding: list[float],
        embedding_model: str,
        confidence: float,
        expires_at: datetime,
        last_used_at: datetime,
        source_conversation_id: str | None = None,
        source_event_id: str | None = None,
        status: UserMemoryStatusEnum = UserMemoryStatusEnum.ACTIVE,
    ) -> UserMemory:
        """
        Persist a new user-scoped memory.

        Takes fields, not a prebuilt entity, so a row cannot be created
        without an owner.
        """

        self._require_user_id(user_id)

        memory = UserMemory(
            user_id=user_id,
            kind=kind.value,
            content=content,
            content_hash=content_hash,
            embedding=embedding,
            embedding_model=embedding_model,
            confidence=confidence,
            status=status.value,
            expires_at=expires_at,
            last_used_at=last_used_at,
            source_conversation_id=source_conversation_id,
            source_event_id=source_event_id,
        )

        return await self.persist(
            memory,
        )

    async def update_content(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
        kind: UserMemoryKindEnum,
        content: str,
        content_hash: str,
        embedding: list[float],
        embedding_model: str,
        confidence: float,
        expires_at: datetime,
        last_used_at: datetime,
        source_conversation_id: str | None = None,
        source_event_id: str | None = None,
    ) -> UserMemory | None:
        """
        Rewrite an existing memory in place. Returns None when the id
        does not belong to this user.
        """

        memory = await self.get(
            user_id=user_id,
            memory_id=memory_id,
        )

        if memory is None:
            return None

        memory.kind = kind.value
        memory.content = content
        memory.content_hash = content_hash
        memory.embedding = embedding
        memory.embedding_model = embedding_model
        memory.confidence = confidence
        memory.expires_at = expires_at
        memory.last_used_at = last_used_at
        memory.source_conversation_id = source_conversation_id
        memory.source_event_id = source_event_id

        await self.flush()
        await self.refresh(memory)

        return memory

    async def set_status(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
        status: UserMemoryStatusEnum,
    ) -> bool:
        """
        Change a memory's lifecycle status. True if a row was updated.
        """

        self._require_user_id(user_id)

        result = await self._session.execute(
            update(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                UserMemory.id == memory_id,
            )
            .values(status=status.value),
        )

        return cast(CursorResult[Any], result).rowcount > 0

    async def touch(
        self,
        *,
        user_id: UserId,
        memory_ids: Sequence[UserMemoryId],
        last_used_at: datetime,
        expires_at: datetime,
    ) -> int:
        """
        Record use of memories and slide their expiry forward.
        Returns the number of rows updated.
        """

        self._require_user_id(user_id)

        if not memory_ids:
            return 0

        result = await self._session.execute(
            update(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                UserMemory.id.in_(list(memory_ids)),
            )
            .values(
                last_used_at=last_used_at,
                expires_at=expires_at,
            ),
        )

        return cast(CursorResult[Any], result).rowcount

    async def delete(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
    ) -> bool:
        """
        Hard-delete one memory. True if a row was deleted.
        """

        self._require_user_id(user_id)

        result = await self._session.execute(
            delete(UserMemory).where(
                UserMemory.user_id == user_id,
                UserMemory.id == memory_id,
            ),
        )

        return cast(CursorResult[Any], result).rowcount > 0

    async def delete_all(
        self,
        *,
        user_id: UserId,
    ) -> int:
        """
        Hard-delete every memory a user has, in every status.
        Returns the number of rows deleted.
        """

        self._require_user_id(user_id)

        result = await self._session.execute(
            delete(UserMemory).where(
                UserMemory.user_id == user_id,
            ),
        )

        return cast(CursorResult[Any], result).rowcount

    async def purge_expired(
        self,
        *,
        user_id: UserId,
        now: datetime,
    ) -> int:
        """
        Hard-delete this user's expired rows. Returns the number deleted.
        """

        self._require_user_id(user_id)

        # "fetch": let the database decide which rows match instead of
        # the ORM's default of re-evaluating the datetime comparison in
        # Python against objects already in the session, which breaks on
        # any mix of naive and timezone-aware values.
        result = await self._session.execute(
            delete(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                UserMemory.expires_at.is_not(None),
                UserMemory.expires_at <= now,
            )
            .execution_options(synchronize_session="fetch"),
        )

        return cast(CursorResult[Any], result).rowcount

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def get(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
    ) -> UserMemory | None:
        """
        Retrieve one of this user's memories in any status, expired or
        not. Visibility rules belong to the service; this lets a user
        delete a row regardless of its state.
        """

        result = await self._session.execute(
            self._scoped(user_id=user_id).where(
                UserMemory.id == memory_id,
            ),
        )

        return cast(
            UserMemory | None,
            result.scalar_one_or_none(),
        )

    async def find_active_by_hash(
        self,
        *,
        user_id: UserId,
        content_hash: str,
    ) -> UserMemory | None:
        """
        Find this user's ACTIVE memory with the given content hash.

        Deliberately ignores expiry: the partial unique index on
        (user_id, content_hash) covers every active row, expired or
        not, so a dedupe lookup must see expired rows too or a re-insert
        would collide with one.
        """

        result = await self._session.execute(
            self._scoped(user_id=user_id).where(
                UserMemory.content_hash == content_hash,
                UserMemory.status == UserMemoryStatusEnum.ACTIVE.value,
            ),
        )

        return cast(
            UserMemory | None,
            result.scalar_one_or_none(),
        )

    async def list_visible(
        self,
        *,
        user_id: UserId,
        now: datetime,
        limit: int,
        offset: int = 0,
    ) -> list[UserMemory]:
        """
        Memories the user can see (active or pending, not expired),
        newest first.
        """

        result = await self._session.execute(
            self._scoped(user_id=user_id)
            .where(*self._visible(now=now))
            .order_by(
                UserMemory.created_at.desc(),
                UserMemory.id.desc(),
            )
            .limit(limit)
            .offset(offset),
        )

        return list(result.scalars().all())

    async def count_visible(
        self,
        *,
        user_id: UserId,
        now: datetime,
    ) -> int:
        """
        Number of memories the user can see (active or pending, not
        expired).
        """

        self._require_user_id(user_id)

        result = await self._session.execute(
            select(func.count())
            .select_from(UserMemory)
            .where(
                UserMemory.user_id == user_id,
                *self._visible(now=now),
            ),
        )

        return int(result.scalar_one())

    async def list_live_by_kind(
        self,
        *,
        user_id: UserId,
        kind: UserMemoryKindEnum,
        now: datetime,
        limit: int,
    ) -> list[UserMemory]:
        """
        Live memories of one kind, most recently used first.
        """

        result = await self._session.execute(
            self._scoped(user_id=user_id)
            .where(
                UserMemory.kind == kind.value,
                *self._live(now=now),
            )
            .order_by(
                UserMemory.last_used_at.desc(),
                UserMemory.created_at.desc(),
                UserMemory.id.desc(),
            )
            .limit(limit),
        )

        return list(result.scalars().all())

    async def search_similar(
        self,
        *,
        user_id: UserId,
        embedding: list[float],
        embedding_model: str,
        now: datetime,
        limit: int,
        min_similarity: float,
    ) -> list[tuple[UserMemory, float]]:
        """
        Rank this user's live memories by cosine similarity to
        ``embedding``.

        The user_id/status/expiry filter runs first and the exact
        distance is computed over the survivors only -- no ANN index,
        by design, so a query can never surface another user's row even
        if that row is an exact vector match.

        Only rows embedded with ``embedding_model`` are comparable.
        Returns (memory, similarity) with similarity = 1 - cosine
        distance, best first, at or above ``min_similarity``.
        """

        if not embedding or limit <= 0:
            return []

        cosine_distance = UserMemory.embedding.cosine_distance(embedding)

        result = await self._session.execute(
            self._scoped(user_id=user_id)
            .add_columns(
                (1 - cosine_distance).label("similarity"),
            )
            .where(
                and_(
                    UserMemory.embedding_model == embedding_model,
                    *self._live(now=now),
                    cosine_distance <= 1 - min_similarity,
                ),
            )
            .order_by(cosine_distance.asc())
            .limit(limit),
        )

        return [(memory, float(similarity)) for memory, similarity in result.all()]
