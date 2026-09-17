"""
Shared evidence-text matching helper for retrieval evaluation metrics.

recall.py, precision.py, and mrr.py each need to check whether an
expected_evidence string occurs inside a retrieved chunk's text. This
module is the single, shared definition of that check, rather than
three independent copies drifting apart.

Normalization applied before matching:

    - whitespace runs (including newlines introduced by PDF line-wraps,
      e.g. "are\\nused") collapse to a single space
    - whitespace immediately before punctuation (a PDF-extraction
      artifact, e.g. "arithmetical , or" from a stray space inserted
      before a comma) is stripped

Deliberately NOT handled here: inline legislative citation/amendment
brackets such as "1[electronic\\nsignature]" (seen mid-sentence in the
IT Act corpus). That's a separate, rarer artifact -- flagged as a known
gap, not fixed by this normalization.
"""

from __future__ import annotations

import re

_WHITESPACE_RUN = re.compile(r"\s+")
_WHITESPACE_BEFORE_PUNCTUATION = re.compile(r"\s+([,.;:!?)])")


def normalize_for_matching(text: str) -> str:
    """
    Normalize text for evidence substring matching: case-fold and
    collapse/strip whitespace as described in this module's docstring.

    Case-folding lives here (not at call sites) precisely so every
    caller gets it automatically -- three independent call sites each
    remembering to `.lower()` is exactly the kind of duplication that
    drifts out of sync.
    """

    collapsed = _WHITESPACE_RUN.sub(" ", text.lower())

    return _WHITESPACE_BEFORE_PUNCTUATION.sub(r"\1", collapsed).strip()


def evidence_in_text(evidence: str, text: str) -> bool:
    """
    Whether normalized `evidence` occurs inside normalized `text`.

    Both sides are normalized so a PDF line-wrap or stray space in
    either the authored evidence string or the retrieved chunk text
    doesn't defeat an otherwise-correct match.
    """

    return normalize_for_matching(evidence) in normalize_for_matching(text)
