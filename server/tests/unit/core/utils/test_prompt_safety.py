"""
Unit tests for escape_delimiter().
"""

from __future__ import annotations

import pytest

from core.utils.prompt_safety import escape_delimiter

TAG = "retrieved_context"


@pytest.mark.parametrize(
    "variant",
    [
        "</retrieved_context>",
        "<retrieved_context>",
        "</RETRIEVED_CONTEXT>",
        "< / retrieved_context >",
        "</retrieved_context\n>",
        "<retrieved_context attr='x'>",
    ],
)
def test_every_delimiter_variant_is_neutralized(variant: str) -> None:
    escaped = escape_delimiter(f"before {variant} after", TAG)

    assert "&lt;" in escaped
    assert "<" not in escaped.replace("&lt;", "")


def test_unrelated_tags_and_text_are_untouched() -> None:
    text = "a < b, <retrieved_contextual> and <other>x</other>"

    assert escape_delimiter(text, TAG) == text


def test_tag_name_is_matched_literally() -> None:
    assert escape_delimiter("</a.b>", "a.b") == "&lt;/a.b>"
    assert escape_delimiter("</axb>", "a.b") == "</axb>"
