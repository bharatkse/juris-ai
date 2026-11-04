"""
A per-run SQLite database for the unit tests.

Imported by server/conftest.py before any application module, so it must
not import application code itself.
"""

from __future__ import annotations

import tempfile
from pathlib import Path


def make_temp_database() -> tuple[str, str]:
    """
    A fresh temp directory and the async SQLite URL of a database in it.

    Returns (url, directory). The database file is created on first
    connection; the caller removes the directory when it's done.
    """

    directory = tempfile.mkdtemp(prefix="juris-unit-db-")
    path = Path(directory) / "unit.db"

    return f"sqlite+aiosqlite:///{path}", directory
