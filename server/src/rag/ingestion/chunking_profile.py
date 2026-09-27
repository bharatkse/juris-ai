from __future__ import annotations

import re
from dataclasses import dataclass

from rag.ingestion.models import ChunkingProfile, ParsedBlock


@dataclass(frozen=True, slots=True)
class ChunkingProfileSelector:
    """Selects a deterministic chunking profile from parsed content."""

    DEFAULT_TARGET_SIZE = 1200
    DEFAULT_MAX_SIZE = 1800
    DEFAULT_OVERLAP = 150

    LEGAL_TARGET_SIZE = 1000
    LEGAL_MAX_SIZE = 1600
    LEGAL_OVERLAP = 120

    def select(self, block: ParsedBlock) -> ChunkingProfile:
        if self._looks_like_legal_text(block.text):
            return ChunkingProfile(
                target_size=self.LEGAL_TARGET_SIZE,
                max_size=self.LEGAL_MAX_SIZE,
                overlap=self.LEGAL_OVERLAP,
                preserve_structure=True,
            )

        return ChunkingProfile(
            target_size=self.DEFAULT_TARGET_SIZE,
            max_size=self.DEFAULT_MAX_SIZE,
            overlap=self.DEFAULT_OVERLAP,
            preserve_structure=True,
        )

    @staticmethod
    def _looks_like_legal_text(text: str) -> bool:
        sample = text[:4000]

        patterns = (
            r"(?m)^\s*\d+[A-Za-z]?(?:\(\d+\))?(?:\([a-z]\))?\s+",
            r"(?m)^\s*\([a-z]\)\s+",
            r"(?m)^\s*\([ivxlcdm]+\)\s+",
            r"(?mi)^\s*(?:explanation|provided that|exception)\s*[\.:—-]",
            r"(?mi)^\s*(?:schedule|article)\s+\d+",
        )

        return any(re.search(pattern, sample) for pattern in patterns)
