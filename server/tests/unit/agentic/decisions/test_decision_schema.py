"""
Unit tests for decision_json_schema().
"""

from __future__ import annotations

from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision, decision_json_schema


def _tool_name(schema: dict) -> dict:
    return schema["$defs"]["AgentToolCall"]["properties"]["tool_name"]


def test_tool_names_are_limited_to_the_agents_tools() -> None:
    schema = decision_json_schema(tool_names=["retriever", "case_law_search", "retriever"])

    assert _tool_name(schema)["enum"] == ["case_law_search", "retriever"]


def test_with_no_tools_no_tool_call_is_possible() -> None:
    schema = decision_json_schema(tool_names=[])

    assert schema["properties"]["tool_call"] == {"type": "null", "default": None}


def test_the_rest_of_the_decision_contract_is_unchanged() -> None:
    base = AgentDecision.model_json_schema()
    schema = decision_json_schema(tool_names=["retriever"])

    assert schema["required"] == base["required"]
    assert schema["properties"].keys() == base["properties"].keys()
    assert schema["$defs"]["AgentDecisionType"] == base["$defs"]["AgentDecisionType"]


def test_the_model_class_schema_is_not_modified() -> None:
    decision_json_schema(tool_names=["retriever"])

    assert "enum" not in _tool_name(AgentDecision.model_json_schema())


def test_a_decision_matching_the_schema_still_validates_as_agent_decision() -> None:
    decision = AgentDecision.model_validate(
        {
            "decision_type": AgentDecisionType.TOOL_CALL,
            "tool_call": {"tool_name": "retriever", "parameters": {"query": "FIR"}},
        }
    )

    assert (
        decision.tool_call.tool_name
        in _tool_name(decision_json_schema(tool_names=["retriever"]))["enum"]
    )
