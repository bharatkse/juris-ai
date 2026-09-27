"""Unit tests for tool-name canonicalization."""

from __future__ import annotations

from agentic.policy.tool_permission import canonicalize_tool_name


def test_search_internet_maps_to_web_research_when_allowed() -> None:
    assert (
        canonicalize_tool_name(
            tool_name="search_internet",
            allowed_tools=frozenset({"retriever", "web_research"}),
        )
        == "web_research"
    )


def test_search_internet_falls_back_to_case_law_search() -> None:
    assert (
        canonicalize_tool_name(
            tool_name="search_internet",
            allowed_tools=frozenset({"retriever", "case_law_search"}),
        )
        == "case_law_search"
    )


def test_permitted_name_is_unchanged() -> None:
    assert (
        canonicalize_tool_name(
            tool_name="retriever",
            allowed_tools=frozenset({"retriever", "case_law_search"}),
        )
        == "retriever"
    )
