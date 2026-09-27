from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Final

from adapters.observability.logger import get_logger
from rag.ingestion.exceptions import SanitizationError

logger = get_logger(__name__)


class ThreatLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class ThreatDetection:
    rule_name: str
    threat_level: ThreatLevel
    description: str
    matched_snippet: str


@dataclass(frozen=True, slots=True)
class SanitizationResult:
    clean_text: str
    is_safe: bool
    threats: tuple[ThreatDetection, ...] = ()


class SecuritySanitizer:
    """
    Canonicalizes extracted document text and performs bounded security
    threat detection.

    The sanitizer does not remove suspicious legal content. Suspicious
    content is preserved in clean_text and reported separately through
    ThreatDetection.

    The implementation is stateless and safe to reuse across concurrent
    ingestion operations.
    """

    _TAB_SIZE: Final[int] = 4

    _SNIPPET_RADIUS: Final[int] = 20
    _MAX_SNIPPET_LENGTH: Final[int] = 80
    _MAX_THREATS: Final[int] = 100

    # ------------------------------------------------------------------
    # Canonicalization
    # ------------------------------------------------------------------

    _MULTIPLE_HSPACES = re.compile(
        r"[^\S\n\r]+",
    )

    _EXCESSIVE_NEWLINES = re.compile(
        r"\n{3,}",
    )

    _UNSAFE_AND_INVISIBLE_CHARS = re.compile(
        r"[\x00-\x08\x0B\x0E-\x1F\x7F-\x9F" r"\u200B-\u200D\u2060\uFEFF]",
    )

    # ------------------------------------------------------------------
    # Prompt-injection heuristics
    # ------------------------------------------------------------------

    _PROMPT_INJECTION_PATTERNS = (
        (
            "INSTRUCTION_OVERRIDE",
            ThreatLevel.CRITICAL,
            re.compile(
                r"\b(?:"
                r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions"
                r"|disregard\s+(?:all\s+)?(?:prior|previous)"
                r"\s+(?:rules|prompts|context)"
                r"|you\s+must\s+now\s+forget\s+everything"
                r")\b",
                re.IGNORECASE,
            ),
            "Possible instruction override or context-reset attempt.",
        ),
        (
            "ROLE_HIJACKING",
            ThreatLevel.HIGH,
            re.compile(
                r"\b(?:"
                r"you\s+are\s+now\s+(?:a|an)\s+"
                r"(?:unrestricted|jailbroken|god-mode|DAN|developer\s+mode)"
                r"|act\s+as\s+an\s+unfiltered\s+AI"
                r")\b",
                re.IGNORECASE,
            ),
            "Possible adversarial role or persona hijacking.",
        ),
        (
            "DELIMITER_INJECTION",
            ThreatLevel.CRITICAL,
            re.compile(
                r"(?:"
                r"</?(?:system|assistant|human|context|instruction)>"
                r"|\[/?INST\]"
                r"|^[^\S\r\n]*#{2,}\s*"
                r"(?:system|instruction|response)\s*:"
                r"|^[^\S\r\n]*(?:system|assistant|human|instruction)"
                r"\s*:\s*"
                r"(?:ignore|disregard|override|follow)\b"
                r"|^[^\S\r\n]*(?:>|[-*])\s*"
                r"(?:system|assistant|human|instruction)"
                r"\s*:\s*"
                r"(?:ignore|disregard|override|follow)\b"
                r")",
                re.IGNORECASE | re.MULTILINE,
            ),
            "Possible injection of LLM/system framing or directive syntax.",
        ),
        (
            "EXFILTRATION_TRIGGER",
            ThreatLevel.HIGH,
            re.compile(
                r"\b(?:"
                r"repeat\s+the\s+(?:system\s+prompt|words\s+above)"
                r"|print\s+your\s+instructions"
                r"|leak\s+the\s+prompt"
                r")\b",
                re.IGNORECASE,
            ),
            "Possible attempt to extract system instructions or hidden context.",
        ),
    )

    # ------------------------------------------------------------------
    # SQL-injection heuristics
    #
    # These are document-content heuristics only. They are NOT a
    # replacement for parameterized SQL/database security.
    # ------------------------------------------------------------------

    _SQL_INJECTION_PATTERNS = (
        (
            "SQLI_UNION_SELECT",
            ThreatLevel.CRITICAL,
            re.compile(
                r"\bUNION[ \t]+(?:ALL[ \t]+)?SELECT\b",
                re.IGNORECASE,
            ),
            "Possible SQL UNION/SELECT injection sequence.",
        ),
        (
            "SQLI_BOOLEAN_TAUTOLOGY",
            ThreatLevel.HIGH,
            re.compile(
                r"\b(?:OR|AND)[ \t]+"
                r"['\"]?\d+['\"]?[ \t]*=[ \t]*"
                r"['\"]?\d+['\"]?[ \t]+"
                r"(?:--|#|/\*)(?!\S)",
                re.IGNORECASE,
            ),
            "Possible SQL tautology followed by a SQL comment marker.",
        ),
        (
            "SQLI_STACKED_DESTRUCTIVE",
            ThreatLevel.CRITICAL,
            re.compile(
                r";[ \t]*(?:"
                r"DROP|ALTER|TRUNCATE|DELETE[ \t]+FROM"
                r")[ \t]+[A-Za-z_][A-Za-z0-9_]*",
                re.IGNORECASE,
            ),
            "Possible stacked destructive SQL statement.",
        ),
    )

    # ------------------------------------------------------------------
    # Secret / credential heuristics
    # ------------------------------------------------------------------

    _SECRET_PATTERNS = (
        (
            "POTENTIAL_API_KEY",
            ThreatLevel.HIGH,
            re.compile(
                r"\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)"
                r"[ \t]*[:=][ \t]*"
                r"['\"]([A-Za-z0-9_-]{20,256})['\"]",
                re.IGNORECASE,
            ),
            "Possible hardcoded API key or credential value.",
        ),
        (
            "BEARER_TOKEN",
            ThreatLevel.HIGH,
            re.compile(
                r"\bBearer[ \t]+([A-Za-z0-9_.-]{32,512})" r"(?![A-Za-z0-9_.-])",
                re.IGNORECASE,
            ),
            "Possible bearer authorization token.",
        ),
    )

    def sanitize_and_scan(
        self,
        text: str,
        *,
        fail_on: Sequence[ThreatLevel] = (ThreatLevel.CRITICAL,),
    ) -> SanitizationResult:
        """
        Canonicalize and scan document text.

        Suspicious content is preserved. Findings are returned separately.

        Args:
            text:
                Extracted document text.

            fail_on:
                Threat levels that cause is_safe=False.

        Returns:
            SanitizationResult containing canonicalized text and findings.

        Raises:
            TypeError:
                If text is not a string.

            SanitizationError:
                If an unexpected sanitization failure occurs.
        """

        if not isinstance(text, str):
            raise TypeError(
                "text must be a string.",
            )

        if not text:
            return SanitizationResult(
                clean_text="",
                is_safe=True,
            )

        try:
            fail_levels = frozenset(fail_on)

            clean_text = self._canonicalize(
                text,
            )

            detection_text = self._normalize_for_detection(
                clean_text,
            )

            threats = self._detect_threats(
                detection_text,
            )

            is_safe = not any(threat.threat_level in fail_levels for threat in threats)

            if threats:
                logger.warning(
                    "Security threats detected during document sanitization: "
                    "threat_count=%d unsafe=%s",
                    len(threats),
                    not is_safe,
                )

            return SanitizationResult(
                clean_text=clean_text,
                is_safe=is_safe,
                threats=tuple(threats),
            )

        except (TypeError, ValueError):
            raise

        except Exception as exc:
            logger.exception(
                "Unexpected error during document sanitization.",
            )

            raise SanitizationError(
                "Document sanitization failed.",
            ) from exc

    @classmethod
    def _canonicalize(
        cls,
        text: str,
    ) -> str:
        """
        Normalize document text while preserving meaningful indentation.
        """

        cleaned = text.replace(
            "\x0c",
            "\n\n",
        )

        cleaned = cleaned.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        # NFC is used for the actual stored document representation.
        cleaned = unicodedata.normalize(
            "NFC",
            cleaned,
        )

        cleaned = cls._UNSAFE_AND_INVISIBLE_CHARS.sub(
            "",
            cleaned,
        )

        normalized_lines: list[str] = []

        for line in cleaned.split("\n"):
            leading_length = len(line) - len(line.lstrip(" \t"))

            leading = line[:leading_length].expandtabs(
                cls._TAB_SIZE,
            )

            content = line[leading_length:]

            content = cls._MULTIPLE_HSPACES.sub(
                " ",
                content,
            ).rstrip()

            normalized_lines.append(
                f"{leading}{content}",
            )

        cleaned = "\n".join(
            normalized_lines,
        )

        cleaned = cls._EXCESSIVE_NEWLINES.sub(
            "\n\n",
            cleaned,
        )

        return cleaned.strip()

    @staticmethod
    def _normalize_for_detection(
        text: str,
    ) -> str:
        """
        Create an NFKC-normalized representation used only for
        security detection.
        """

        return unicodedata.normalize(
            "NFKC",
            text,
        )

    @classmethod
    def _detect_threats(
        cls,
        text: str,
    ) -> list[ThreatDetection]:
        """
        Run all security heuristics with a hard finding limit.
        """

        threats: list[ThreatDetection] = []

        for (
            rule_name,
            threat_level,
            pattern,
            description,
        ) in (
            *cls._PROMPT_INJECTION_PATTERNS,
            *cls._SQL_INJECTION_PATTERNS,
        ):
            for match in pattern.finditer(text):
                threats.append(
                    ThreatDetection(
                        rule_name=rule_name,
                        threat_level=threat_level,
                        description=description,
                        matched_snippet=cls._build_snippet(
                            text,
                            match.start(),
                            match.end(),
                        ),
                    )
                )

                if len(threats) >= cls._MAX_THREATS:
                    return threats

        for (
            rule_name,
            threat_level,
            pattern,
            description,
        ) in cls._SECRET_PATTERNS:
            for match in pattern.finditer(text):
                threats.append(
                    ThreatDetection(
                        rule_name=rule_name,
                        threat_level=threat_level,
                        description=description,
                        matched_snippet=cls._build_snippet(
                            text,
                            match.start(),
                            match.end(),
                            redact_match=True,
                        ),
                    )
                )

                if len(threats) >= cls._MAX_THREATS:
                    return threats

        return threats

    @classmethod
    def _build_snippet(
        cls,
        text: str,
        start: int,
        end: int,
        *,
        redact_match: bool = False,
    ) -> str:
        """
        Build a bounded detection snippet.

        Secret matches are replaced with [REDACTED] so credentials are
        never exposed through threat metadata or logs.
        """

        start = max(
            0,
            min(start, len(text)),
        )

        end = max(
            start,
            min(end, len(text)),
        )

        snippet_start = max(
            0,
            start - cls._SNIPPET_RADIUS,
        )

        snippet_end = min(
            len(text),
            end + cls._SNIPPET_RADIUS,
        )

        snippet = text[snippet_start:snippet_end].replace(
            "\n",
            " ",
        )

        if redact_match:
            relative_start = start - snippet_start

            relative_end = min(
                end - snippet_start,
                len(snippet),
            )

            if 0 <= relative_start < relative_end:
                snippet = snippet[:relative_start] + "[REDACTED]" + snippet[relative_end:]

        if len(snippet) > cls._MAX_SNIPPET_LENGTH:
            snippet = snippet[: cls._MAX_SNIPPET_LENGTH]

        prefix = "... " if snippet_start > 0 else ""

        suffix = " ..." if snippet_end < len(text) else ""

        return f"{prefix}" f"{snippet}" f"{suffix}"
