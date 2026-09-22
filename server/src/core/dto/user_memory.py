"""
User memory context models.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.enums import UserMemoryKindEnum


@dataclass(slots=True, frozen=True)
class UserMemoryContextItem:
    """
    One user memory selected for injection into a prompt.

    Carries only what the prompt needs -- no embedding, no provenance
    -- so it is safe to plumb through request/context objects.
    """

    id: str

    kind: UserMemoryKindEnum

    content: str
