"""
Helpers for placing untrusted text inside prompt delimiters.
"""

from __future__ import annotations

import re


def escape_delimiter(text: str, tag: str) -> str:
    """
    Neutralize every opening or closing ``tag`` inside untrusted ``text``.

    Untrusted content (retrieved documents, web pages, a response under
    review) is wrapped in ``<tag>...</tag>`` so the model can tell it apart
    from instructions. If the content itself contains ``</tag>`` it can
    close the wrapper early and have the text after it read as
    instructions. Replacing the leading ``<`` with ``&lt;`` keeps the text
    readable while making it impossible to form a real delimiter.
    Matching is case-insensitive and tolerates whitespace inside the tag
    (``< / TAG >``).
    """

    pattern = re.compile(rf"<(\s*/?\s*{re.escape(tag)})(?=[\s>/]|$)", re.IGNORECASE)
    return pattern.sub(r"&lt;\1", text)
