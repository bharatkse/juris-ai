"""
Database configuration and session management.

This module centralizes all database setup concerns, including:
- SQLAlchemy engine configuration
- ORM base class definition
- Request-scoped session lifecycle management

Database migrations are handled externally using Alembic.
This module is designed to integrate cleanly with FastAPI's
dependency injection system.
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import settings


class Base(DeclarativeBase):
    """
    Declarative base class for all ORM models.

    All SQLAlchemy model classes must inherit from this base
    to ensure consistent metadata registration.
    """

    pass


def create_database_engine() -> Engine:
    """
    Create and configure the SQLAlchemy database engine.

    Configuration notes:
    - Connection pooling uses conservative defaults suitable
      for small to medium workloads.
    - `pool_pre_ping` ensures stale connections are detected.
    - Pooling behavior can be tuned per environment via settings.

    Returns:
        Configured SQLAlchemy Engine instance.
    """
    return create_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
    )


# Shared database engine instance
database_engine = create_database_engine()


# Factory for creating new database sessions
SessionLocal = sessionmaker(
    bind=database_engine,
    autocommit=False,
    autoflush=False,
)


def get_db():
    """
    Provide a request-scoped database session.

    This function is intended for use with FastAPI's dependency
    injection system. A new session is created per request and
    is always closed after use.

    Yields:
        sqlalchemy.orm.Session: Active database session.
    """
    database_session = SessionLocal()
    try:
        yield database_session
    finally:
        database_session.close()
