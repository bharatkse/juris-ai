"""
Unit tests: every unit test run gets its own SQLite database.

The unit suite used to share one file, ./pytests.db, relative to the
working directory, so two runs at once (the Stop hook's and a manual one,
or two checkouts) created and dropped each other's tables, and the file
outlived every run. Now each pytest process gets a database in a fresh
temp directory, removed when the run ends; the engine fixture and the
app's TESTING settings both use it.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine

from config.settings import get_settings
from tests.unit.fixtures.temp_database import make_temp_database


def test_each_call_makes_a_separate_database_in_a_temp_directory() -> None:
    first_url, first_dir = make_temp_database()
    second_url, second_dir = make_temp_database()

    try:
        assert first_url != second_url
        for url, directory in ((first_url, first_dir), (second_url, second_dir)):
            assert url.startswith("sqlite+aiosqlite:///")
            assert Path(directory).is_dir()
            assert Path(directory).parent == Path(tempfile.gettempdir())
            assert url.endswith(str(Path(directory) / "unit.db"))
    finally:
        for directory in (first_dir, second_dir):
            os.rmdir(directory)


async def test_the_engine_uses_this_runs_database_not_a_shared_file(
    engine: AsyncEngine,
) -> None:
    database = Path(str(engine.url.database))

    assert database.is_absolute()
    assert database.name == "unit.db"
    assert database.parent.parent == Path(tempfile.gettempdir())
    assert database.parent != Path.cwd()


async def test_the_app_settings_use_the_same_database(engine: AsyncEngine) -> None:
    assert get_settings().database.TEST_DATABASE_URL == engine.url.render_as_string(
        hide_password=False
    )
