"""
Validation for sanitized document content before chunking and embedding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from adapters.observability.logger import get_logger
from rag.ingestion.exceptions import ContentValidationError

logger = get_logger(__name__)


class ValidationErrorCode(str, Enum):
    EMPTY_CONTENT = "EMPTY_CONTENT"
    INSUFFICIENT_CONTENT = "INSUFFICIENT_CONTENT"
    INSUFFICIENT_ALPHANUMERIC = "INSUFFICIENT_ALPHANUMERIC"
    INVALID_UNICODE = "INVALID_UNICODE"
    EXCESSIVE_REPLACEMENT_CHARS = "EXCESSIVE_REPLACEMENT_CHARS"


@dataclass(frozen=True, slots=True)
class ValidationError:
    code: ValidationErrorCode
    message: str


@dataclass(frozen=True, slots=True)
class ContentValidationResult:
    is_valid: bool
    errors: tuple[ValidationError, ...] = ()


class ContentValidator:
    """
    Validates sanitized document content before chunking.

    This validator is intentionally read-only. It never modifies the
    supplied text and maintains no mutable per-document state.

    The implementation is therefore safe to reuse across concurrent
    ingestion operations.
    """

    _ALPHANUMERIC_PATTERN = re.compile(
        r"\w",
        re.UNICODE,
    )

    def __init__(
        self,
        *,
        min_content_length: int = 10,
        min_alphanumeric_ratio: float = 0.25,
        max_replacement_ratio: float = 0.01,
    ) -> None:
        if min_content_length < 0:
            raise ValueError(
                "min_content_length cannot be negative.",
            )

        if not 0.0 <= min_alphanumeric_ratio <= 1.0:
            raise ValueError(
                "min_alphanumeric_ratio must be between 0.0 and 1.0.",
            )

        if not 0.0 <= max_replacement_ratio <= 1.0:
            raise ValueError(
                "max_replacement_ratio must be between 0.0 and 1.0.",
            )

        self._min_content_length = min_content_length
        self._min_alphanumeric_ratio = min_alphanumeric_ratio
        self._max_replacement_ratio = max_replacement_ratio

    def validate(
        self,
        text: str,
    ) -> ContentValidationResult:
        """
        Validate sanitized document text.

        The input is never mutated.

        Raises:
            TypeError:
                If text is not a string.

            ContentValidationError:
                If an unexpected validation failure occurs.
        """

        if not isinstance(text, str):
            raise TypeError(
                "text must be a string.",
            )

        try:
            if not text or not text.strip():
                return ContentValidationResult(
                    is_valid=False,
                    errors=(
                        ValidationError(
                            code=ValidationErrorCode.EMPTY_CONTENT,
                            message=("Extracted content is empty or contains " "only whitespace."),
                        ),
                    ),
                )

            errors: list[ValidationError] = []

            # ----------------------------------------------------------
            # Unicode integrity
            # ----------------------------------------------------------

            if not self._is_valid_utf8(text):
                errors.append(
                    ValidationError(
                        code=ValidationErrorCode.INVALID_UNICODE,
                        message=(
                            "Extracted content contains invalid UTF-8 "
                            "or lone surrogate code points."
                        ),
                    ),
                )

            # ----------------------------------------------------------
            # Content signal
            # ----------------------------------------------------------

            total_chars = len(text)

            non_whitespace_count = sum(1 for character in text if not character.isspace())

            if non_whitespace_count < self._min_content_length:
                errors.append(
                    ValidationError(
                        code=ValidationErrorCode.INSUFFICIENT_CONTENT,
                        message=(
                            "Extracted content contains only "
                            f"{non_whitespace_count} non-whitespace "
                            "characters; minimum required is "
                            f"{self._min_content_length}."
                        ),
                    ),
                )

            # ----------------------------------------------------------
            # Linguistic signal
            # ----------------------------------------------------------

            alphanumeric_count = sum(1 for character in text if self._is_alphanumeric(character))

            alphanumeric_ratio = (
                alphanumeric_count / non_whitespace_count if non_whitespace_count > 0 else 0.0
            )

            if alphanumeric_ratio < self._min_alphanumeric_ratio:
                errors.append(
                    ValidationError(
                        code=ValidationErrorCode.INSUFFICIENT_ALPHANUMERIC,
                        message=(
                            "Content lacks sufficient linguistic signal. "
                            f"Alphanumeric ratio is "
                            f"{alphanumeric_ratio:.2%}; expected at "
                            f"least "
                            f"{self._min_alphanumeric_ratio:.2%}."
                        ),
                    ),
                )

            # ----------------------------------------------------------
            # Parser/decoding corruption
            # ----------------------------------------------------------

            replacement_count = text.count(
                "\ufffd",
            )

            replacement_ratio = replacement_count / total_chars if total_chars > 0 else 0.0

            if replacement_ratio > self._max_replacement_ratio:
                errors.append(
                    ValidationError(
                        code=ValidationErrorCode.EXCESSIVE_REPLACEMENT_CHARS,
                        message=(
                            "Document contains excessive Unicode "
                            "replacement characters (\\uFFFD). "
                            f"Ratio is {replacement_ratio:.2%}; "
                            "threshold is "
                            f"{self._max_replacement_ratio:.2%}."
                        ),
                    ),
                )

            result = ContentValidationResult(
                is_valid=not errors,
                errors=tuple(errors),
            )

            if not result.is_valid:
                logger.warning(
                    "Document content validation failed: " "error_count=%d",
                    len(result.errors),
                )

            return result

        except (TypeError, ValueError):
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error during document content validation.",
            )

            raise ContentValidationError(
                "Document content validation failed.",
            ) from exc

    @staticmethod
    def _is_alphanumeric(
        character: str,
    ) -> bool:
        """
        Determine whether a character contributes linguistic signal.

        str.isalnum() is preferable to regex allocation here because
        validation is performed for every character in potentially
        large streamed blocks.
        """

        return character.isalnum()

    @staticmethod
    def _is_valid_utf8(
        text: str,
    ) -> bool:
        """
        Verify that the Python string can be strictly encoded as UTF-8.
        """

        try:
            text.encode(
                "utf-8",
                errors="strict",
            )
            return True

        except UnicodeEncodeError:
            return False
