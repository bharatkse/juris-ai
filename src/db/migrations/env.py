"""
Alembic environment configuration.

This module configures Alembic to use the application's Settings object as the
single source of truth for the database connection.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

import src.db.models  # noqa: F401
from src.core.config import get_settings
from src.db.base import Base

settings = get_settings()

# ------------------------------------------------------------------------------
# Ensure project root is importable
# ------------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ------------------------------------------------------------------------------
# Alembic configuration
# ------------------------------------------------------------------------------

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

# Use application configuration instead of alembic.ini
config.set_main_option("sqlalchemy.url", settings.database_url)

# Metadata used for autogenerate
target_metadata = Base.metadata


def get_engine():
    """Create SQLAlchemy engine for Alembic."""

    return engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""

    engine = get_engine()

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
