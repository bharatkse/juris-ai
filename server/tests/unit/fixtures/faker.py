"""
Faker fixtures.
"""

from __future__ import annotations

import pytest
from faker import Faker


@pytest.fixture(scope="session")
def faker() -> Faker:
    """
    Return a Faker instance.
    """

    return Faker()
