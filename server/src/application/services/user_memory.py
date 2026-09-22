"""
User memory service.

Durable, per-user facts that persist across conversations -- distinct
from ConversationSummarizationService, whose rolling summary lives on one
Conversation row and is only ever read back into that same conversation.

Consent is opt-in and owned here: nothing is retrieved for, or stored
about, a user whose ``memory_enabled`` flag is false, and withdrawing
consent hard-deletes everything stored in the same transaction.

Transaction ownership
---------------------
Building blocks that run inside a larger unit of work (``remember``,
``update``, ``supersede``, ``retrieve_for_prompt``) never commit -- the
calling service owns the transaction, as with ConversationEventService.
User-facing operations that are a complete unit on their own
(``set_consent``, ``delete_memory``, ``delete_all``) commit themselves.

Logging
-------
Memory content is user data. Log lines carry ids, counts and the content
hash only -- never the text.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.models.user import User
from adapters.persistence.sqlalchemy.models.user_memory import UserMemory
from agentic.agents.prompts.token_budget import count_tokens
from agentic.agents.prompts.user_memory import format_memory_line
from application.services.base import BaseService
from core.constants import (
    USER_MEMORY_EXTRACTION_CONTEXT_K,
    USER_MEMORY_MAX_CONTENT_CHARS,
    USER_MEMORY_MAX_PER_USER,
    USER_MEMORY_MAX_PROFILE_ITEMS,
    USER_MEMORY_MAX_PROMPT_TOKENS,
    USER_MEMORY_MIN_SIMILARITY,
    USER_MEMORY_RECENCY_BONUS_MAX,
    USER_MEMORY_RECENCY_WINDOW_DAYS,
    USER_MEMORY_RETENTION_DAYS,
    USER_MEMORY_RETRIEVAL_TOP_K,
)
from core.dto.user_memory import UserMemoryContextItem
from core.enums import (
    ActorTypeEnum,
    UserMemoryKindEnum,
    UserMemoryOperationEnum,
    UserMemoryStatusEnum,
)
from core.exceptions.database import DatabaseError
from core.exceptions.httpx import NotFoundError, UserNotFoundError
from core.exceptions.user_memory import (
    InvalidUserMemoryContentError,
    UserMemoryLimitExceededError,
)
from core.utils.datetime import utcnow

if TYPE_CHECKING:
    from adapters.persistence.sqlalchemy.repositories.conversation import (
        ConversationRepository,
    )
    from adapters.persistence.sqlalchemy.repositories.user import UserRepository
    from adapters.persistence.sqlalchemy.repositories.user_memory import (
        UserMemoryRepository,
    )
    from application.services.compliance_log import ComplianceLogService
    from core.types import ConversationId, UserId, UserMemoryId
    from rag.protocols.embedding_provider import EmbeddingProviderProtocol

logger = get_logger(__name__)

# Non-profile candidates fetched from the database before recency
# re-ranking. Wider than the final top-k so a slightly less similar but
# recently used memory can still win a near-tie.
_CANDIDATE_POOL_MULTIPLIER = 3


def normalize_content(
    content: str,
) -> str:
    """
    Collapse whitespace. The stored form of a memory.
    """

    return " ".join(content.split())


def hash_content(
    content: str,
) -> str:
    """
    Dedupe key for a memory: sha256 of the case-folded, whitespace-
    normalized content.
    """

    return hashlib.sha256(
        normalize_content(content).casefold().encode("utf-8"),
    ).hexdigest()


def expiry_from(
    moment: datetime,
) -> datetime:
    """
    When a memory used at ``moment`` expires.
    """

    return moment + timedelta(days=USER_MEMORY_RETENTION_DAYS)


def _as_utc(
    moment: datetime,
) -> datetime:
    # SQLite (unit tests) returns naive datetimes for timezone-aware
    # columns; everything stored here is UTC.
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


class UserMemoryService(BaseService):
    """
    Business logic for durable, per-user memory.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        repository: UserMemoryRepository,
        user_repository: UserRepository,
        conversation_repository: ConversationRepository,
        embedding_provider: EmbeddingProviderProtocol,
        compliance_log: ComplianceLogService,
    ) -> None:
        super().__init__(session)
        self._repository = repository
        self._user_repository = user_repository
        self._conversation_repository = conversation_repository
        self._embedding_provider = embedding_provider
        self._compliance_log = compliance_log

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------

    async def is_enabled(
        self,
        *,
        user_id: UserId,
    ) -> bool:
        """
        Whether the user has opted in to memory.
        """

        user = await self._user_repository.get(user_id)

        return bool(user is not None and user.memory_enabled)

    async def is_enabled_for_conversation(
        self,
        *,
        user_id: UserId,
        conversation_id: ConversationId,
    ) -> bool:
        """
        Whether memory may be used in this conversation: the user has
        opted in AND has not switched "don't remember this" on for it.

        Fails closed: a conversation that does not exist for this user
        (or was archived) is not one memory may be used in.
        """

        if not await self.is_enabled(user_id=user_id):
            return False

        disabled = await self._conversation_repository.get_memory_disabled(
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return disabled is False

    async def set_consent(
        self,
        *,
        user_id: UserId,
        enabled: bool,
    ) -> User:
        """
        Turn memory on or off for a user.

        Withdrawing consent (on -> off) hard-deletes every stored
        memory in the same transaction as the flag change, so there is
        no window where consent is withdrawn but data remains. Setting
        a value the user already has is a no-op.
        """

        user = await self._user_repository.get(user_id)

        if user is None:
            raise UserNotFoundError(
                message="User not found.",
            )

        if bool(user.memory_enabled) == enabled:
            return user

        try:
            user.memory_enabled = enabled
            user.memory_consent_updated_at = utcnow()

            deleted = 0

            if not enabled:
                deleted = await self._repository.delete_all(
                    user_id=user_id,
                )

            await self._audit(
                user_id=user_id,
                operation=(
                    UserMemoryOperationEnum.CONSENT_GRANTED
                    if enabled
                    else UserMemoryOperationEnum.CONSENT_WITHDRAWN
                ),
                actor_type=ActorTypeEnum.USER,
                count=deleted if not enabled else None,
            )

            await self.commit()

        except SQLAlchemyError as exc:
            await self.rollback()

            logger.exception(
                "Database error while changing memory consent.",
                extra={
                    "operation": "set_memory_consent",
                    "user_id": str(user_id),
                },
            )

            raise DatabaseError(
                "Failed to update memory consent.",
            ) from exc

        logger.info(
            "Memory consent changed.",
            extra={
                "operation": "set_memory_consent",
                "user_id": str(user_id),
                "enabled": enabled,
                "deleted_count": deleted,
            },
        )

        return user

    # ------------------------------------------------------------------
    # Write building blocks (caller owns the transaction)
    # ------------------------------------------------------------------

    async def remember(
        self,
        *,
        user_id: UserId,
        kind: UserMemoryKindEnum,
        content: str,
        confidence: float = 1.0,
        source_conversation_id: str | None = None,
        source_event_id: str | None = None,
    ) -> UserMemory:
        """
        Store a fact, or refresh it if the user already has it.

        An identical active fact (same normalized content) is not
        duplicated: its retention window is slid forward instead. Does
        not check consent -- the caller decides whether memory is
        allowed for this user and conversation.

        Raises:
            InvalidUserMemoryContentError:
                Content is empty or longer than one atomic fact.
            UserMemoryLimitExceededError:
                The user is at USER_MEMORY_MAX_PER_USER.
        """

        content = self._validate_content(content)
        content_hash = hash_content(content)
        now = utcnow()

        existing = await self._repository.find_active_by_hash(
            user_id=user_id,
            content_hash=content_hash,
        )

        if existing is not None:
            await self._repository.touch(
                user_id=user_id,
                memory_ids=[existing.id],
                last_used_at=now,
                expires_at=expiry_from(now),
            )
            await self.refresh(existing)

            return existing

        if (
            await self._repository.count_visible(
                user_id=user_id,
                now=now,
            )
            >= USER_MEMORY_MAX_PER_USER
        ):
            raise UserMemoryLimitExceededError(
                f"Memory limit of {USER_MEMORY_MAX_PER_USER} reached.",
            )

        embedding = await self._embed(content)

        try:
            # SAVEPOINT: losing a race on the unique (user, hash) index
            # must not abort the caller's whole transaction.
            async with self.session.begin_nested():
                memory = await self._repository.add(
                    user_id=user_id,
                    kind=kind,
                    content=content,
                    content_hash=content_hash,
                    embedding=embedding,
                    embedding_model=self._embedding_provider.metadata.model_name,
                    confidence=confidence,
                    last_used_at=now,
                    expires_at=expiry_from(now),
                    source_conversation_id=source_conversation_id,
                    source_event_id=source_event_id,
                )

        except IntegrityError:
            winner = await self._repository.find_active_by_hash(
                user_id=user_id,
                content_hash=content_hash,
            )

            if winner is None:
                raise

            return winner

        await self._audit(
            user_id=user_id,
            operation=UserMemoryOperationEnum.STORED,
            actor_type=ActorTypeEnum.AGENT,
            memory_id=memory.id,
            content_hash=content_hash,
            kind=kind.value,
            conversation_id=source_conversation_id,
            conversation_event_id=source_event_id,
        )

        logger.info(
            "User memory stored.",
            extra={
                "operation": "remember",
                "user_id": str(user_id),
                "memory_id": str(memory.id),
                "kind": kind.value,
                "content_hash": content_hash,
            },
        )

        return memory

    async def update(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
        kind: UserMemoryKindEnum,
        content: str,
        confidence: float = 1.0,
        source_conversation_id: str | None = None,
        source_event_id: str | None = None,
    ) -> UserMemory:
        """
        Rewrite one of the user's memories in place.

        Raises:
            NotFoundError:
                The id is not one of this user's memories.
            InvalidUserMemoryContentError:
                Content is empty or longer than one atomic fact.
        """

        content = self._validate_content(content)
        now = utcnow()

        memory = await self._repository.update_content(
            user_id=user_id,
            memory_id=memory_id,
            kind=kind,
            content=content,
            content_hash=hash_content(content),
            embedding=await self._embed(content),
            embedding_model=self._embedding_provider.metadata.model_name,
            confidence=confidence,
            last_used_at=now,
            expires_at=expiry_from(now),
            source_conversation_id=source_conversation_id,
            source_event_id=source_event_id,
        )

        if memory is None:
            raise NotFoundError(
                message="Memory not found.",
            )

        await self._audit(
            user_id=user_id,
            operation=UserMemoryOperationEnum.UPDATED,
            actor_type=ActorTypeEnum.AGENT,
            memory_id=memory.id,
            content_hash=memory.content_hash,
            kind=kind.value,
            conversation_id=source_conversation_id,
            conversation_event_id=source_event_id,
        )

        return memory

    async def supersede(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
    ) -> None:
        """
        Mark a memory as replaced by a newer one. It stops being
        injected and stops being shown to the user.
        """

        memory = await self._repository.get(
            user_id=user_id,
            memory_id=memory_id,
        )

        updated = memory is not None and await self._repository.set_status(
            user_id=user_id,
            memory_id=memory_id,
            status=UserMemoryStatusEnum.SUPERSEDED,
        )

        if memory is None or not updated:
            raise NotFoundError(
                message="Memory not found.",
            )

        await self._audit(
            user_id=user_id,
            operation=UserMemoryOperationEnum.SUPERSEDED,
            actor_type=ActorTypeEnum.AGENT,
            memory_id=memory.id,
            content_hash=memory.content_hash,
            kind=memory.kind,
        )

    async def forget(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
    ) -> None:
        """
        Hard-delete one memory as part of a larger unit of work (a
        model-directed delete during extraction). Does not commit.
        User-initiated deletes go through delete_memory(), which
        commits and is audited as a user action.

        Raises:
            NotFoundError:
                The id is not one of this user's memories.
        """

        memory = await self._repository.get(
            user_id=user_id,
            memory_id=memory_id,
        )

        if memory is None or not await self._repository.delete(
            user_id=user_id,
            memory_id=memory_id,
        ):
            raise NotFoundError(
                message="Memory not found.",
            )

        await self._audit(
            user_id=user_id,
            operation=UserMemoryOperationEnum.DELETED,
            actor_type=ActorTypeEnum.AGENT,
            memory_id=memory.id,
            content_hash=memory.content_hash,
            kind=memory.kind,
        )

    async def related_for_extraction(
        self,
        *,
        user_id: UserId,
        text: str,
    ) -> list[UserMemory]:
        """
        The memories shown to the extraction model so it can dedupe and
        supersede instead of blindly inserting: the user's profile
        memories plus those most similar to ``text``, capped at
        USER_MEMORY_EXTRACTION_CONTEXT_K. Does not touch retention --
        being shown to the extractor is not "use".
        """

        now = utcnow()

        profile = await self._repository.list_live_by_kind(
            user_id=user_id,
            kind=UserMemoryKindEnum.PROFILE,
            now=now,
            limit=USER_MEMORY_MAX_PROFILE_ITEMS,
        )

        similar = await self._repository.search_similar(
            user_id=user_id,
            embedding=await self._embed(text),
            embedding_model=self._embedding_provider.metadata.model_name,
            now=now,
            limit=USER_MEMORY_EXTRACTION_CONTEXT_K,
            # Nearest neighbours whatever their score: this is context
            # for the model, not a relevance decision.
            min_similarity=-1.0,
        )

        related: dict[str, UserMemory] = {memory.id: memory for memory in profile}

        for memory, _similarity in similar:
            related.setdefault(memory.id, memory)

        return list(related.values())[:USER_MEMORY_EXTRACTION_CONTEXT_K]

    async def purge_expired(
        self,
        *,
        user_id: UserId,
    ) -> int:
        """
        Hard-delete this user's expired memories. Does not commit: the
        caller owns the transaction (see _purge_expired_and_commit for
        the self-committing variant used by user-facing reads).
        """

        purged = await self._repository.purge_expired(
            user_id=user_id,
            now=utcnow(),
        )

        if purged:
            await self._audit(
                user_id=user_id,
                operation=UserMemoryOperationEnum.PURGED_EXPIRED,
                actor_type=ActorTypeEnum.AGENT,
                count=purged,
            )

            logger.info(
                "Expired user memories purged.",
                extra={
                    "operation": "purge_expired_memories",
                    "user_id": str(user_id),
                    "purged_count": purged,
                },
            )

        return purged

    async def _purge_expired_and_commit(
        self,
        *,
        user_id: UserId,
    ) -> None:
        try:
            if await self.purge_expired(user_id=user_id):
                await self.commit()

        except SQLAlchemyError:
            await self.rollback()

            logger.exception(
                "Failed to purge expired user memories; continuing.",
                extra={
                    "operation": "purge_expired_memories",
                    "user_id": str(user_id),
                },
            )

    # ------------------------------------------------------------------
    # Self-service (each is a complete unit and commits)
    # ------------------------------------------------------------------

    async def list_memories(
        self,
        *,
        user_id: UserId,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[UserMemory], int]:
        """
        The user's own visible memories, newest first, and the total.

        Expired rows are hard-deleted before the list is built, so what
        the user sees is exactly what is stored -- nothing past its
        retention window lingers invisibly. The purge commits on its
        own (this is a complete unit of work, and get_db_session does
        not commit) and is best-effort: a failed purge is logged and
        the list is still returned, since expired rows are already
        excluded from it by the query.
        """

        await self._purge_expired_and_commit(user_id=user_id)

        now = utcnow()

        items = await self._repository.list_visible(
            user_id=user_id,
            now=now,
            limit=limit,
            offset=offset,
        )

        total = await self._repository.count_visible(
            user_id=user_id,
            now=now,
        )

        return items, total

    async def get_memory(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
    ) -> UserMemory:
        """
        One of the user's own visible memories.

        Raises:
            NotFoundError:
                No such memory for this user -- including another
                user's id, an expired row, or a superseded row.
        """

        memory = await self._repository.get(
            user_id=user_id,
            memory_id=memory_id,
        )

        if memory is None or not self._is_visible(memory):
            raise NotFoundError(
                message="Memory not found.",
            )

        return memory

    async def delete_memory(
        self,
        *,
        user_id: UserId,
        memory_id: UserMemoryId,
    ) -> None:
        """
        Hard-delete one of the user's memories, in any status.

        Raises:
            NotFoundError:
                No such memory for this user.
        """

        try:
            memory = await self._repository.get(
                user_id=user_id,
                memory_id=memory_id,
            )

            deleted = memory is not None and await self._repository.delete(
                user_id=user_id,
                memory_id=memory_id,
            )

            if memory is not None and deleted:
                await self._audit(
                    user_id=user_id,
                    operation=UserMemoryOperationEnum.DELETED,
                    actor_type=ActorTypeEnum.USER,
                    memory_id=memory.id,
                    content_hash=memory.content_hash,
                    kind=memory.kind,
                )

            await self.commit()

        except SQLAlchemyError as exc:
            await self.rollback()

            logger.exception(
                "Database error while deleting user memory.",
                extra={
                    "operation": "delete_memory",
                    "user_id": str(user_id),
                    "memory_id": str(memory_id),
                },
            )

            raise DatabaseError(
                "Failed to delete memory.",
            ) from exc

        if not deleted:
            raise NotFoundError(
                message="Memory not found.",
            )

        logger.info(
            "User memory deleted.",
            extra={
                "operation": "delete_memory",
                "user_id": str(user_id),
                "memory_id": str(memory_id),
            },
        )

    async def delete_all(
        self,
        *,
        user_id: UserId,
    ) -> int:
        """
        Hard-delete every memory the user has. Returns the count.
        """

        try:
            deleted = await self._repository.delete_all(
                user_id=user_id,
            )

            await self._audit(
                user_id=user_id,
                operation=UserMemoryOperationEnum.DELETED_ALL,
                actor_type=ActorTypeEnum.USER,
                count=deleted,
            )

            await self.commit()

        except SQLAlchemyError as exc:
            await self.rollback()

            logger.exception(
                "Database error while deleting all user memories.",
                extra={
                    "operation": "delete_all_memories",
                    "user_id": str(user_id),
                },
            )

            raise DatabaseError(
                "Failed to delete memories.",
            ) from exc

        logger.info(
            "All user memories deleted.",
            extra={
                "operation": "delete_all_memories",
                "user_id": str(user_id),
                "deleted_count": deleted,
            },
        )

        return deleted

    # ------------------------------------------------------------------
    # Read path (caller owns the transaction)
    # ------------------------------------------------------------------

    async def retrieve_for_prompt(
        self,
        *,
        user_id: UserId,
        conversation_id: ConversationId,
        query: str,
    ) -> tuple[UserMemoryContextItem, ...]:
        """
        Select the memories to inject into this turn's prompt.

        Returns () unless the user has opted in AND the conversation's
        "don't remember this" switch is off -- the switch suppresses
        reading as well as writing. Otherwise:

        * up to USER_MEMORY_MAX_PROFILE_ITEMS "profile" memories are
          always included, regardless of similarity to ``query``;
        * the remaining slots (USER_MEMORY_RETRIEVAL_TOP_K in total)
          go to the memories most similar to ``query`` at or above
          USER_MEMORY_MIN_SIMILARITY, with a small recency bonus
          breaking near-ties;
        * the block is cut off, whole items at a time, once it would
          exceed USER_MEMORY_MAX_PROMPT_TOKENS -- fit_to_budget never
          truncates the system side of a prompt, so the cap has to be
          enforced here.

        Selected memories have their retention window slid forward.

        Best-effort: any failure is logged and yields (), never an
        error -- memory must not be able to break a chat request. The
        database work, consent lookup included, runs in a SAVEPOINT so a
        failure cannot leave the caller's transaction aborted.
        """

        if not query.strip():
            return ()

        try:
            # One SAVEPOINT around every database touch (including the
            # consent lookup): if anything in here fails, only the
            # savepoint is rolled back and the caller's transaction
            # stays usable.
            async with self.session.begin_nested():
                if not await self.is_enabled_for_conversation(
                    user_id=user_id,
                    conversation_id=conversation_id,
                ):
                    return ()

                embedding = await self._embed(query)
                now = utcnow()

                profile = await self._repository.list_live_by_kind(
                    user_id=user_id,
                    kind=UserMemoryKindEnum.PROFILE,
                    now=now,
                    limit=USER_MEMORY_MAX_PROFILE_ITEMS,
                )

                candidates = await self._repository.search_similar(
                    user_id=user_id,
                    embedding=embedding,
                    embedding_model=self._embedding_provider.metadata.model_name,
                    now=now,
                    limit=USER_MEMORY_RETRIEVAL_TOP_K * _CANDIDATE_POOL_MULTIPLIER,
                    min_similarity=USER_MEMORY_MIN_SIMILARITY,
                )

                selected = self._select(
                    profile=profile,
                    candidates=candidates,
                    now=now,
                )

                if selected:
                    await self._repository.touch(
                        user_id=user_id,
                        memory_ids=[memory.id for memory in selected],
                        last_used_at=now,
                        expires_at=expiry_from(now),
                    )

            return tuple(
                UserMemoryContextItem(
                    id=memory.id,
                    kind=UserMemoryKindEnum(memory.kind),
                    content=memory.content,
                )
                for memory in selected
            )

        except Exception:
            logger.exception(
                "User memory retrieval failed; continuing without memory.",
                extra={
                    "operation": "retrieve_user_memory",
                    "user_id": str(user_id),
                },
            )

            return ()

    def _select(
        self,
        *,
        profile: list[UserMemory],
        candidates: list[tuple[UserMemory, float]],
        now: datetime,
    ) -> list[UserMemory]:
        ranked = sorted(
            candidates,
            key=lambda pair: pair[1] + self._recency_bonus(pair[0], now=now),
            reverse=True,
        )

        chosen: list[UserMemory] = list(profile)
        seen = {memory.id for memory in chosen}

        for memory, _similarity in ranked:
            if len(chosen) >= USER_MEMORY_RETRIEVAL_TOP_K:
                break

            if memory.id not in seen:
                chosen.append(memory)
                seen.add(memory.id)

        chosen = chosen[:USER_MEMORY_RETRIEVAL_TOP_K]

        kept: list[UserMemory] = []
        used_tokens = 0

        for memory in chosen:
            cost = count_tokens(
                format_memory_line(
                    kind=UserMemoryKindEnum(memory.kind),
                    content=memory.content,
                ),
            )

            if used_tokens + cost > USER_MEMORY_MAX_PROMPT_TOKENS:
                break

            kept.append(memory)
            used_tokens += cost

        return kept

    @staticmethod
    def _recency_bonus(
        memory: UserMemory,
        *,
        now: datetime,
    ) -> float:
        age_days = (now - _as_utc(memory.last_used_at)).total_seconds() / 86_400

        freshness = max(0.0, 1.0 - age_days / USER_MEMORY_RECENCY_WINDOW_DAYS)

        return USER_MEMORY_RECENCY_BONUS_MAX * freshness

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_content(
        content: str,
    ) -> str:
        normalized = normalize_content(content)

        if not normalized:
            raise InvalidUserMemoryContentError(
                "Memory content must not be empty.",
            )

        if len(normalized) > USER_MEMORY_MAX_CONTENT_CHARS:
            raise InvalidUserMemoryContentError(
                f"Memory content exceeds {USER_MEMORY_MAX_CONTENT_CHARS} characters.",
            )

        return normalized

    @staticmethod
    def _is_visible(
        memory: UserMemory,
    ) -> bool:
        if memory.status not in (
            UserMemoryStatusEnum.ACTIVE.value,
            UserMemoryStatusEnum.PENDING.value,
        ):
            return False

        if memory.expires_at is None:
            return True

        return _as_utc(memory.expires_at) > utcnow()

    async def _audit(
        self,
        *,
        user_id: UserId,
        operation: UserMemoryOperationEnum,
        actor_type: ActorTypeEnum,
        memory_id: str | None = None,
        content_hash: str | None = None,
        kind: str | None = None,
        count: int | None = None,
        conversation_id: str | None = None,
        conversation_event_id: str | None = None,
    ) -> None:
        """
        Record a memory operation in the compliance log, in the caller's
        transaction. Identifiers, counts and the content hash only --
        record_memory_operation() has no parameter that could carry
        memory text.
        """

        await self._compliance_log.record_memory_operation(
            user_id=str(user_id),
            tenant_id=str(user_id),
            operation=operation,
            actor_type=actor_type,
            memory_id=memory_id,
            content_hash=content_hash,
            kind=kind,
            count=count,
            conversation_id=conversation_id,
            conversation_event_id=conversation_event_id,
        )

    async def _embed(
        self,
        text: str,
    ) -> list[float]:
        vectors = await self._embedding_provider.embed(
            texts=[text],
        )

        return vectors[0]
