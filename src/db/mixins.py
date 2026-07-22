"""
Reusable SQLAlchemy mixins.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, event
from sqlalchemy.orm import Mapped, Mapper, declared_attr, mapped_column

from src.core.datetime import utcnow


def generate_prefixed_uuid_pk(prefix: str) -> str:
    """
    Generate a UUID-based primary key with the given prefix.

    Args:
        prefix: String prefix (e.g., 'user', 'document')

    Returns:
        Prefixed UUID string (e.g., 'user_a1b2c3d4...')
    """
    return f"{prefix}_{uuid.uuid4().hex}"


class PrimaryKeyMixin:
    """
    Mixin that provides a prefixed string primary key.

    Concrete models MUST define `_id_prefix`.
    """

    _id_prefix: str

    @declared_attr
    @classmethod
    def id(cls) -> Mapped[str]:
        return mapped_column(
            String(64),
            primary_key=True,
            default=lambda: generate_prefixed_uuid_pk(
                cls._id_prefix,
            ),
        )


class TimestampMixin:
    """
    Optional mixin providing created/updated timestamps.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )


class SoftDeleteMixin:
    """
    Soft delete support.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@event.listens_for(Mapper, "mapper_configured")
def _enforce_id_prefix(mapper: Mapper, cls) -> None:
    if not hasattr(cls, "__tablename__"):
        return

    if not issubclass(cls, PrimaryKeyMixin):
        return

    if not getattr(cls, "_id_prefix", None):
        raise RuntimeError(f"{cls.__name__} must define `_id_prefix`")
