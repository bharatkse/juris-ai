"""
Base factory for SQLAlchemy models.
"""

from __future__ import annotations

import factory
from factory.alchemy import SQLAlchemyModelFactory

from src.db.mixins import utcnow


class BaseFactory(SQLAlchemyModelFactory):
    """
    Base SQLAlchemy factory.
    """

    class Meta:
        abstract = True
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "flush"

    created_at = factory.LazyFunction(
        utcnow,
    )

    updated_at = factory.LazyFunction(
        utcnow,
    )
