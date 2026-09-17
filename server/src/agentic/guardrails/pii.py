"""
PII detection and redaction.

Built on Microsoft Presidio (presidio-analyzer + presidio-anonymizer)
rather than hand-rolled regex, for one reason regex fundamentally
cannot cover: recognizing that a span of text is a person's name or an
address needs named-entity recognition, not pattern matching. Presidio
gives that (spaCy-backed AnalyzerEngine) plus a pluggable registry for
the structured-identifier patterns regex genuinely is good at (SSN,
card numbers, email, phone, IP) -- one engine for both, rather than
NER from one library and a second, parallel regex system for the rest.

Recognizer coverage: Presidio's built-in recognizers are US/UK-centric
(US_SSN, UK_NHS, ...). This product's corpus is Indian legal content
(IT Act 2000), so two custom PatternRecognizers are registered
alongside the built-ins -- IN_PAN, IN_AADHAAR -- using the same
recognizer-registry mechanism Presidio's own built-ins use, not a
second detection path.

Default action per entity, and why (the core design tension: a real
client's name in a citation is expected legal content, not a leak --
over-redacting corrupts correct answers):

    STRUCTURED_ID (SSN/PAN/Aadhaar/card/IBAN/bank account/IP/crypto)
        -> always REDACTED. Never legitimate to surface verbatim in a
           generated answer, even one citing a real case.

    CONTACT (email/phone)
        -> REDACTED, unless the exact matched string also appears in
           this turn's retrieved evidence (a filing party's registered
           email genuinely can be legitimate source content) -> then
           FLAGGED, not redacted.

    NAMED_ENTITY (person/location/organization)
        -> FLAGGED if the matched string appears in retrieved evidence
           (traceable to a real cited source -- expected legal
           content); REDACTED if it does not. An entity with no
           evidentiary basis is a stronger hallucination/leak signal
           than a name genuinely drawn from what was retrieved, and
           redaction is the safer default for that case.

Anonymization detail: Presidio's AnonymizerEngine applies operators
per ENTITY TYPE across a whole analyze() call, which cannot express
"redact this PERSON match but not that one" -- exactly the
evidence-dependent, per-instance decision this module needs. The fix
used here is not a different library, just a narrower call: only the
RecognizerResults this module has already decided to redact are ever
passed to anonymize(); the ones being flagged-not-redacted are simply
never included in that call, so Presidio's per-entity-type operator
limitation never actually binds.
"""

from __future__ import annotations

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_analyzer.recognizer_result import RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from agentic.guardrails.schemas import GuardrailActionEnum, PIICategoryEnum, PIIDetection

# Entity -> category. Only entities in this map are ever acted on;
# anything Presidio's default recognizers surface outside this map
# (DATE_TIME, URL, MAC_ADDRESS, ...) is deliberately ignored rather
# than guessed at -- see review()'s entities= filter, which stops
# Presidio from even running those recognizers.
_ENTITY_CATEGORIES: dict[str, PIICategoryEnum] = {
    "US_SSN": PIICategoryEnum.STRUCTURED_ID,
    "CREDIT_CARD": PIICategoryEnum.STRUCTURED_ID,
    "IBAN_CODE": PIICategoryEnum.STRUCTURED_ID,
    "US_BANK_NUMBER": PIICategoryEnum.STRUCTURED_ID,
    "IP_ADDRESS": PIICategoryEnum.STRUCTURED_ID,
    "CRYPTO": PIICategoryEnum.STRUCTURED_ID,
    "IN_PAN": PIICategoryEnum.STRUCTURED_ID,
    "IN_AADHAAR": PIICategoryEnum.STRUCTURED_ID,
    "EMAIL_ADDRESS": PIICategoryEnum.CONTACT,
    "PHONE_NUMBER": PIICategoryEnum.CONTACT,
    "PERSON": PIICategoryEnum.NAMED_ENTITY,
    "LOCATION": PIICategoryEnum.NAMED_ENTITY,
    "ORGANIZATION": PIICategoryEnum.NAMED_ENTITY,
}


def _build_analyzer(*, spacy_model: str) -> AnalyzerEngine:
    """
    Build the AnalyzerEngine once, with an explicit small spaCy model.

    Presidio's default AnalyzerEngine() tries to load en_core_web_lg
    (not installed here -- torch/sentence-transformers already cover
    this stack's embedding needs; a second, large NER model would be
    a needless addition on top of it). NlpEngineProvider is Presidio's
    documented way to pin a specific, smaller model instead.
    """

    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": spacy_model}],
        },
    )
    nlp_engine = provider.create_engine()

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(nlp_engine=nlp_engine)

    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="IN_PAN",
            patterns=[
                Pattern(
                    name="in_pan",
                    # 5 letters, 4 digits, 1 letter -- the fixed Indian
                    # PAN format (e.g. ABCDE1234F).
                    regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
                    score=0.85,
                ),
            ],
        ),
    )

    registry.add_recognizer(
        PatternRecognizer(
            supported_entity="IN_AADHAAR",
            patterns=[
                # Aadhaar is conventionally printed/typed
                # space-separated in groups of 4; the unspaced 12-digit
                # form is deliberately NOT matched here -- a bare
                # 12-digit run is too weak a signal on its own (phone
                # numbers, case/reference numbers) to redact by
                # default without a much higher false-positive cost.
                Pattern(
                    name="in_aadhaar_spaced",
                    regex=r"\b\d{4}\s\d{4}\s\d{4}\b",
                    score=0.6,
                ),
            ],
        ),
    )

    return AnalyzerEngine(registry=registry, nlp_engine=nlp_engine)


def _resolve_overlaps(results: list[RecognizerResult]) -> list[RecognizerResult]:
    """
    Drop lower-confidence detections that overlap a higher-confidence
    one at the same span.

    Different recognizers run independently and routinely fire on the
    same span (e.g. a PAN-shaped string matches both the IN_PAN
    pattern recognizer and the generic PERSON NER model, both at
    score 0.85; an email address matches both EMAIL_ADDRESS and
    ORGANIZATION) -- confirmed empirically while building this module.
    Passing overlapping spans to AnonymizerEngine.anonymize() raises,
    and even where it wouldn't, two categorizations of the same text
    is not a coherent action to take. Greedy non-max suppression,
    standard for resolving overlapping detections in NLP pipelines:
    process the strongest candidate first, keep a detection only if it
    doesn't overlap one already kept.

    Sort key is (score, category priority), not score alone: the
    IN_PAN/PERSON example above ties exactly on score, and which one
    a bare score-only sort keeps then depends on the analyzer's
    internal recognizer-iteration order -- not a real signal, and not
    reproducible input to input (confirmed: this order differs
    depending on the requested `entities` list's order). Category
    priority breaks the tie deterministically and by an actual
    principle: a pattern-matched structured identifier is inherently
    more specific and reliable than a generic NER named-entity guess
    at the same span, so STRUCTURED_ID outranks CONTACT outranks
    NAMED_ENTITY regardless of iteration order.
    """

    def _priority(result: RecognizerResult) -> int:
        category = _ENTITY_CATEGORIES.get(result.entity_type)

        if category is PIICategoryEnum.STRUCTURED_ID:
            return 2
        if category is PIICategoryEnum.CONTACT:
            return 1
        if category is PIICategoryEnum.NAMED_ENTITY:
            return 0
        return -1

    kept: list[RecognizerResult] = []

    for result in sorted(
        results,
        key=lambda item: (item.score, _priority(item)),
        reverse=True,
    ):
        if any(result.start < other.end and other.start < result.end for other in kept):
            continue
        kept.append(result)

    return sorted(kept, key=lambda item: item.start)


def _evidence_matched(*, matched_text: str, evidence_text: str) -> bool:
    """
    Whether the matched span is traceable to this turn's retrieved
    evidence -- a case-insensitive substring check against the
    evidence text assembled by the caller (see OutputGuardrailService).

    Deliberately simple: this is a provenance signal, not a semantic
    one -- a name/email/phone that was actually retrieved for this
    turn will appear verbatim (or not at all) in the evidence text
    that fed the answer, so substring containment is the right check,
    not fuzzy matching.
    """

    matched_text = matched_text.strip()

    if not matched_text or not evidence_text:
        return False

    return matched_text.lower() in evidence_text.lower()


class PresidioPIIDetector:
    """
    Detects and redacts PII in a final response, per the category
    defaults documented in this module's docstring.
    """

    def __init__(self, *, spacy_model: str = "en_core_web_sm") -> None:
        self._analyzer = _build_analyzer(spacy_model=spacy_model)
        self._anonymizer = AnonymizerEngine()
        self._entities = tuple(_ENTITY_CATEGORIES.keys())

    def review(
        self,
        *,
        text: str,
        evidence_text: str,
    ) -> tuple[str, tuple[PIIDetection, ...]]:
        """
        Analyze ``text`` and return (possibly redacted) text plus the
        detections found.

        Synchronous and CPU-bound (spaCy inference) -- callers running
        inside an event loop must dispatch this via asyncio.to_thread
        (see OutputGuardrailService.review), not call it directly.
        """

        if not text.strip():
            return text, ()

        raw_results = self._analyzer.analyze(
            text=text,
            language="en",
            entities=list(self._entities),
        )

        results = _resolve_overlaps(list(raw_results))

        detections: list[PIIDetection] = []
        to_redact: list[RecognizerResult] = []

        for result in results:
            category = _ENTITY_CATEGORIES.get(result.entity_type)

            if category is None:
                # Outside the filtered entities= list above in
                # practice, but defensive: never act on an
                # unrecognized entity type.
                continue

            matched_text = text[result.start : result.end]

            if category is PIICategoryEnum.STRUCTURED_ID:
                evidence_matched = False
                action = GuardrailActionEnum.REDACTED
            else:
                evidence_matched = _evidence_matched(
                    matched_text=matched_text,
                    evidence_text=evidence_text,
                )
                action = (
                    GuardrailActionEnum.FLAGGED
                    if evidence_matched
                    else GuardrailActionEnum.REDACTED
                )

            detections.append(
                PIIDetection(
                    entity_type=result.entity_type,
                    category=category,
                    action=action,
                    evidence_matched=evidence_matched,
                ),
            )

            if action is GuardrailActionEnum.REDACTED:
                to_redact.append(result)

        if not to_redact:
            return text, tuple(detections)

        operators = {
            entity_type: OperatorConfig(
                "replace",
                {"new_value": f"[REDACTED:{entity_type}]"},
            )
            for entity_type in {result.entity_type for result in to_redact}
        }

        anonymized = self._anonymizer.anonymize(
            text=text,
            # presidio-analyzer and presidio-anonymizer each declare
            # their own RecognizerResult class (analyzer_results is
            # typed against the anonymizer package's copy); confirmed
            # empirically that the analyzer's real return value works
            # correctly here (see this module's own tests) -- a stub
            # mismatch between the two packages, not a real type error.
            analyzer_results=to_redact,  # type: ignore[arg-type]
            operators=operators,
        )

        return anonymized.text, tuple(detections)
