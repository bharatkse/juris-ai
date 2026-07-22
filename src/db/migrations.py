"""
Programmatic database initialisation and migration helpers.

For production use Alembic (alembic upgrade head).
These helpers are used for:
  - First-time setup in development
  - Test database provisioning
  - CI/CD pipelines where Alembic is overkill
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from src.db.base import Base

log = logging.getLogger(__name__)


def create_all_tables(engine: Engine) -> None:
    """
    Create every table declared in ORM models if it doesn't exist yet.
    Safe to call multiple times (uses CREATE TABLE IF NOT EXISTS semantics).
    """
    import src.db.models  # noqa: F401 — registers all ORM classes with Base

    Base.metadata.create_all(bind=engine, checkfirst=True)
    log.info("Database tables verified / created.")


def drop_all_tables(engine: Engine) -> None:
    """
    Drop every table.  USE WITH CAUTION — irreversible.
    Only intended for test teardown.
    """
    import src.db.models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    log.warning("All database tables dropped.")


def reset_database(engine: Engine) -> None:
    """Drop then recreate all tables.  Test utility only."""
    drop_all_tables(engine)
    create_all_tables(engine)
    log.info("Database reset complete.")


def table_exists(engine: Engine, table_name: str) -> bool:
    """Check whether a specific table exists."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def get_table_row_counts(engine: Engine) -> dict[str, int]:
    """Return {table_name: row_count} for every managed table."""
    import src.db.models  # noqa: F401

    counts: dict[str, int] = {}
    with engine.connect() as conn:
        for table in Base.metadata.sorted_tables:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table.name}"))
            counts[table.name] = result.scalar() or 0
    return counts


def run_health_check(engine: Engine) -> bool:
    """Return True if the DB is reachable and tables exist."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        missing = [t.name for t in Base.metadata.sorted_tables if not table_exists(engine, t.name)]
        if missing:
            log.warning(f"Missing tables: {missing}")
            return False
        return True
    except Exception as exc:
        log.error(f"DB health check failed: {exc}")
        return False
