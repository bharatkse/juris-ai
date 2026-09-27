"""
Unit pytest configuration.
"""

from __future__ import annotations

import os

# pytest_plugins for tests/unit/ live in the top-level ../conftest.py --
# see its docstring for why.

os.environ.setdefault("RAGAS_DO_NOT_TRACK", "true")
