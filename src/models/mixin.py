import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, String, event
from sqlalchemy.orm import Mapper


def generate_prefixed_uuid_pk(prefix: str) -> str:
    """
    Generate a UUID-based primary key with the given prefix.

    Args:
        prefix: String prefix (e.g., 'user', 'document')

    Returns:
        Prefixed UUID string (e.g., 'user_a1b2c3d4...')
    """
    return f"{prefix}_{uuid.uuid4().hex}"


class PrefixedPrimaryKeyMixin:
    """
    Mixin that provides a prefixed string primary key.

    Concrete models MUST define `_id_prefix`.
    """

    _id_prefix: str

    id = Column(String(50), primary_key=True)

    def __init__(self, *args, **kwargs):
        # Call SQLAlchemy's default constructor FIRST
        super().__init__(*args, **kwargs)

        # Assign ID only if not already set
        if not getattr(self, "id", None):
            self.id = generate_prefixed_uuid_pk(self._id_prefix)


class TimestampMixin:
    """
    Optional mixin providing created/updated timestamps.
    """

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


@event.listens_for(Mapper, "mapper_configured")
def _enforce_id_prefix(mapper: Mapper, cls) -> None:
    if not hasattr(cls, "__tablename__"):
        return

    if not issubclass(cls, PrefixedPrimaryKeyMixin):
        return

    if not getattr(cls, "_id_prefix", None):
        raise RuntimeError(f"{cls.__name__} must define `_id_prefix`")
