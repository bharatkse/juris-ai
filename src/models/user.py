__alembic_model__ = True

from sqlalchemy import Column, DateTime, String

from src.database import Base
from src.models.mixin import PrefixedPrimaryKeyMixin, TimestampMixin


class User(PrefixedPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    _id_prefix = "user"

    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    phone_number = Column(String, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
