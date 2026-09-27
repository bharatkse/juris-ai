"""
TF-IDF based capability classification.

Capability classification identifies which supported action types
appear to be requested by the input.

It does not perform authorization, approval, or execution.
"""

from __future__ import annotations

import logging
from typing import Any

from core.dto.capability import CapabilityMatchDTO
from core.enums import ActionTypeEnum

logger = logging.getLogger(__name__)

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:  # pragma: no cover - optional in incomplete local images
    TfidfVectorizer = None
    cosine_similarity = None


class TFIDFCapabilityClassifier:
    """
    Classifies natural-language input into supported action types.

    Classification is responsible only for identifying the capabilities
    requested by the input.

    It does not:
    - authorize the requester,
    - evaluate RBAC permissions,
    - evaluate approval requirements,
    - execute actions.
    """

    def __init__(
        self,
        *,
        examples: dict[ActionTypeEnum, tuple[str, ...]],
        threshold: float = 0.50,
    ) -> None:
        if not examples:
            raise ValueError(
                "Capability examples cannot be empty.",
            )

        if not 0.0 <= threshold <= 1.0:
            raise ValueError(
                "Capability threshold must be between 0 and 1.",
            )

        self._threshold = threshold
        self._vectorizer: Any = None
        self._matrix: Any = None
        self._action_types: list[ActionTypeEnum] = []

        if TfidfVectorizer is None or cosine_similarity is None:
            logger.warning(
                "scikit-learn is not installed; capability classification is disabled.",
            )
            return

        action_types: list[ActionTypeEnum] = []
        documents: list[str] = []

        for action_type, action_examples in examples.items():
            for example in action_examples:
                example = example.strip()

                if not example:
                    continue

                action_types.append(action_type)
                documents.append(example)

        if not documents:
            raise ValueError(
                "Capability examples cannot contain empty action sets.",
            )

        self._action_types = action_types

        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            ngram_range=(1, 2),
        )

        self._matrix = self._vectorizer.fit_transform(
            documents,
        )

    def classify(
        self,
        content: str,
    ) -> tuple[CapabilityMatchDTO, ...]:
        """
        Identify supported action types requested by the input.

        Returns at most one match for each action type, using the
        highest similarity score found for that action type.
        """

        content = content.strip()

        if not content or self._vectorizer is None:
            return ()

        content_vector = self._vectorizer.transform(
            [content],
        )

        similarities = cosine_similarity(
            content_vector,
            self._matrix,
        )[0]

        best_scores: dict[ActionTypeEnum, float] = {}

        for action_type, score in zip(
            self._action_types,
            similarities,
            strict=False,
        ):
            score = float(score)

            current_score = best_scores.get(
                action_type,
                0.0,
            )

            if score > current_score:
                best_scores[action_type] = score

        return tuple(
            CapabilityMatchDTO(
                action_type=action_type,
                score=score,
            )
            for action_type, score in best_scores.items()
            if score >= self._threshold
        )
