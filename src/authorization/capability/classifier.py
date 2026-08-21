"""
TF-IDF based external action classification.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.core.dto.capability import CapabilityMatchDTO
from src.core.enums import ActionTypeEnum


class TFIDFCapabilityClassifier:
    """
    Classifies natural-language requests into supported external
    actions using TF-IDF and cosine similarity.

    This classifier identifies requested actions only.
    It does not perform authorization or approval decisions.
    """

    def __init__(
        self,
        examples: dict[ActionTypeEnum, tuple[str, ...]],
        threshold: float = 0.35,
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

        self._actions: list[ActionTypeEnum] = []
        documents: list[str] = []

        for action, action_examples in examples.items():
            if not action_examples:
                continue

            for example in action_examples:
                self._actions.append(action)
                documents.append(example)

        if not documents:
            raise ValueError(
                "Capability examples cannot contain empty action sets.",
            )

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
        Identify externally impactful actions requested by the user.
        """

        if not content.strip():
            return ()

        content_vector = self._vectorizer.transform(
            [content],
        )

        similarities = cosine_similarity(
            content_vector,
            self._matrix,
        )[0]

        matches: dict[ActionTypeEnum, float] = {}

        for action, score in zip(
            self._actions,
            similarities,
            strict=False,
        ):
            current_score = matches.get(
                action,
                0.0,
            )

            if score > current_score:
                matches[action] = float(score)

        return tuple(
            CapabilityMatchDTO(
                action=action,
                score=score,
            )
            for action, score in matches.items()
            if score >= self._threshold
        )
