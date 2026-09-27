"""
User memory write-path composition.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from adapters.persistence.sqlalchemy.session import session_factory
from agentic.guardrails.pii import PresidioPIIDetector
from application.services.memory_content_guard import MemoryContentGuard
from application.services.user_memory_extraction import (
    MemoryExtractionScheduler,
    UserMemoryExtractor,
)

if TYPE_CHECKING:
    from agentic.guardrails.schemas import PIIDetection
    from config.settings import Settings
    from wiring.containers import ClientContainer


class LazyPresidioPIIDetector:
    """
    A PresidioPIIDetector built on first use.

    PresidioPIIDetector loads a spaCy model at construction. Memory
    extraction is rare and runs in the background, so paying that cost
    at startup (in addition to the output guardrail's own detector)
    would slow every boot for a feature most requests never reach.
    Built at most once, under a lock: ``review`` is called from worker
    threads (see MemoryContentGuard.check).
    """

    def __init__(
        self,
        *,
        spacy_model: str,
    ) -> None:
        self._spacy_model = spacy_model
        self._detector: PresidioPIIDetector | None = None
        self._lock = threading.Lock()

    def review(
        self,
        *,
        text: str,
        evidence_text: str,
    ) -> tuple[str, tuple[PIIDetection, ...]]:
        if self._detector is None:
            with self._lock:
                if self._detector is None:
                    self._detector = PresidioPIIDetector(
                        spacy_model=self._spacy_model,
                    )

        return self._detector.review(
            text=text,
            evidence_text=evidence_text,
        )


def create_memory_extraction_scheduler(
    *,
    settings: Settings,
    clients: ClientContainer,
) -> MemoryExtractionScheduler:
    """
    Build the process-wide scheduler for user-memory extraction.

    Called once from main.py's lifespan and read from ``app.state``,
    never constructed per request: it owns the set of in-flight
    background runs (at most one per conversation), which only means
    something if there is exactly one of it. Shares the orchestrator's
    embedding provider and LLM resolver rather than loading its own.
    """

    return MemoryExtractionScheduler(
        extractor=UserMemoryExtractor(
            session_factory=session_factory,
            embedding_provider=clients.embedding_provider,
            llm_client_factory=clients.llm_resolver.get,
            guard=MemoryContentGuard(
                pii_detector=LazyPresidioPIIDetector(
                    spacy_model=settings.guardrails.GUARDRAIL_SPACY_MODEL,
                ),
            ),
        ),
    )
