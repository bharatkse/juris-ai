"""
Unit tests for ToolRegistry.describe(): what an agent's LLM is told about
the tools its policy allows.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from agentic.registry.agent import AgentRegistry
from agentic.registry.tool import ToolRegistry
from wiring.containers import RegistryContainer
from wiring.factories.tools import register_tools


def _production_registry() -> ToolRegistry:
    """Every tool production registers, with stubbed dependencies."""

    registry = ToolRegistry()
    register_tools(
        clients=MagicMock(),
        registries=RegistryContainer(agent_registry=AgentRegistry(), tool_registry=registry),
        approval_service=MagicMock(),
    )
    return registry


def test_describe_lists_only_the_named_agent_callable_tools_sorted() -> None:
    registry = _production_registry()

    specs = registry.describe(
        names={"retriever", "case_law_search", "parser", "not_a_registered_tool"},
    )

    # parser is server-side only (no params_model); an unregistered name
    # is dropped rather than offered to the model.
    assert [spec.name for spec in specs] == ["case_law_search", "retriever"]


def test_describe_renders_each_tools_parameter_schema() -> None:
    (retriever,) = _production_registry().describe(names=["retriever"])

    schema = retriever.parameters_schema

    assert schema["required"] == ["query"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["top_k"]["minimum"] == 1
    assert schema["properties"]["top_k"]["maximum"] == 10
    assert schema["properties"]["top_k"]["default"] == 5
    assert retriever.description == _production_registry().resolve(key="retriever").description

    # pydantic's generated titles are stripped; field descriptions stay.
    assert "title" not in schema
    assert "title" not in schema["properties"]["query"]
    assert schema["properties"]["query"]["description"]


def test_describe_of_no_names_is_empty() -> None:
    assert _production_registry().describe(names=()) == ()


@pytest.mark.parametrize(
    "name",
    ["retriever", "web_research", "case_law_search", "library_lookup", "email", "slack"],
)
def test_params_model_matches_the_tools_execute_signature(name: str) -> None:
    """
    The schema the model sees must describe what execute() really takes:
    same parameter names, required-ness and defaults.
    """

    tool = _production_registry().resolve(key=name)
    assert tool.params_model is not None

    signature = inspect.signature(tool.execute).parameters

    for field_name, field in tool.params_model.model_fields.items():
        assert field_name in signature, field_name
        if field.is_required():
            assert signature[field_name].default is inspect.Parameter.empty, field_name
        else:
            assert signature[field_name].default == field.default, field_name


def test_every_registered_tool_is_either_described_or_server_side_only() -> None:
    registry = _production_registry()

    described = {spec.name for spec in registry.describe(names=registry.keys())}
    server_side_only = {
        name for name in registry.keys() if registry.resolve(key=name).params_model is None
    }

    assert described | server_side_only == set(registry.keys())
    assert server_side_only == {"parser"}


@pytest.mark.parametrize(
    "tool, field, minimum, maximum",
    [
        ("retriever", "top_k", 1, 10),
        ("web_research", "limit", 1, 5),
        ("case_law_search", "limit", 1, 10),
        ("email", "limit", 1, 20),
        ("slack", "limit", 1, 20),
        ("library_lookup", "limit", 1, 20),
    ],
)
def test_result_count_parameters_are_bounded(
    tool: str, field: str, minimum: int, maximum: int
) -> None:
    """The bounds the model is shown -- and every call is validated against."""

    (spec,) = _production_registry().describe(names=[tool])
    bounds = spec.parameters_schema["properties"][field]

    assert (bounds["minimum"], bounds["maximum"]) == (minimum, maximum)


def test_web_research_does_not_let_the_model_choose_search_engines() -> None:
    (spec,) = _production_registry().describe(names=["web_research"])

    assert set(spec.parameters_schema["properties"]) == {"query", "limit"}
