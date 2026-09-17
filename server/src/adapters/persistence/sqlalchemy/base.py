"""
Declarative base shared by all ORM models.
Import Base here and inherit from it in every ORM model.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Naming convention ensures Alembic can name constraints reproducibly
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """
    Declarative base class for all ORM models.

    All SQLAlchemy model classes must inherit from this base
    to ensure consistent metadata registration.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
