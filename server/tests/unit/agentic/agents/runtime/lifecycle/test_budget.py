import pytest

from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget


def test_budget_defaults():
    budget = AgentExecutionBudget()

    assert budget.max_iterations == 10
    assert budget.max_tool_calls == 20
    assert budget.max_agent_hops == 5
    assert budget.max_total_steps == 30
    assert budget.max_execution_time_seconds == 120.0
    assert budget.max_repeated_action == 2
    assert budget.max_validation_attempts == 2
    assert budget.max_decisions == 50
    assert budget.max_tool_call_records == 50
    assert budget.max_tool_result_records == 50
    assert budget.max_evidence_items == 100
    assert budget.max_context_items == 100
    assert budget.max_partial_response_chars == 50_000
    assert budget.max_context_item_chars == 20_000
    assert budget.max_evidence_item_chars == 20_000
    assert budget.max_tool_call_record_chars == 10_000
    assert budget.max_tool_result_record_chars == 20_000


@pytest.mark.parametrize(
    "field_name",
    [
        "max_iterations",
        "max_tool_calls",
        "max_agent_hops",
        "max_total_steps",
        "max_repeated_action",
        "max_validation_attempts",
        "max_decisions",
        "max_tool_call_records",
        "max_tool_result_records",
        "max_evidence_items",
        "max_context_items",
        "max_partial_response_chars",
        "max_context_item_chars",
        "max_evidence_item_chars",
        "max_tool_call_record_chars",
        "max_tool_result_record_chars",
    ],
)
def test_budget_rejects_boolean_integer_limit(field_name):
    with pytest.raises(TypeError, match=f"{field_name} must be an integer"):
        AgentExecutionBudget(**{field_name: True})


@pytest.mark.parametrize(
    "field_name",
    [
        "max_iterations",
        "max_tool_calls",
        "max_agent_hops",
        "max_total_steps",
        "max_repeated_action",
        "max_validation_attempts",
        "max_decisions",
        "max_tool_call_records",
        "max_tool_result_records",
        "max_evidence_items",
        "max_context_items",
        "max_partial_response_chars",
        "max_context_item_chars",
        "max_evidence_item_chars",
        "max_tool_call_record_chars",
        "max_tool_result_record_chars",
    ],
)
def test_budget_rejects_non_integer_limit(field_name):
    with pytest.raises(TypeError, match=f"{field_name} must be an integer"):
        AgentExecutionBudget(**{field_name: 1.5})


@pytest.mark.parametrize(
    "field_name",
    [
        "max_iterations",
        "max_tool_calls",
        "max_agent_hops",
        "max_total_steps",
        "max_repeated_action",
        "max_validation_attempts",
        "max_decisions",
        "max_tool_call_records",
        "max_tool_result_records",
        "max_evidence_items",
        "max_context_items",
        "max_partial_response_chars",
        "max_context_item_chars",
        "max_evidence_item_chars",
        "max_tool_call_record_chars",
        "max_tool_result_record_chars",
    ],
)
def test_budget_rejects_non_positive_limit(field_name):
    with pytest.raises(ValueError, match=f"{field_name} must be greater than zero"):
        AgentExecutionBudget(**{field_name: 0})


def test_budget_accepts_custom_positive_limits():
    budget = AgentExecutionBudget(
        max_iterations=1,
        max_tool_calls=2,
        max_agent_hops=3,
        max_total_steps=4,
        max_execution_time_seconds=5.5,
        max_repeated_action=1,
        max_validation_attempts=1,
        max_decisions=6,
        max_tool_call_records=7,
        max_tool_result_records=8,
        max_evidence_items=9,
        max_context_items=10,
        max_partial_response_chars=11,
        max_context_item_chars=12,
        max_evidence_item_chars=13,
        max_tool_call_record_chars=14,
        max_tool_result_record_chars=15,
    )

    assert budget.max_iterations == 1
    assert budget.max_tool_calls == 2
    assert budget.max_agent_hops == 3
    assert budget.max_total_steps == 4
    assert budget.max_execution_time_seconds == 5.5
    assert budget.max_repeated_action == 1
    assert budget.max_validation_attempts == 1
    assert budget.max_decisions == 6
    assert budget.max_tool_call_records == 7
    assert budget.max_tool_result_records == 8
    assert budget.max_evidence_items == 9
    assert budget.max_context_items == 10
    assert budget.max_partial_response_chars == 11
    assert budget.max_context_item_chars == 12
    assert budget.max_evidence_item_chars == 13
    assert budget.max_tool_call_record_chars == 14
    assert budget.max_tool_result_record_chars == 15


def test_budget_rejects_boolean_execution_time():
    with pytest.raises(TypeError, match="max_execution_time_seconds must be a number"):
        AgentExecutionBudget(max_execution_time_seconds=True)


@pytest.mark.parametrize(
    "value",
    ["120", None, object()],
)
def test_budget_rejects_non_numeric_execution_time(value):
    with pytest.raises(TypeError, match="max_execution_time_seconds must be a number"):
        AgentExecutionBudget(max_execution_time_seconds=value)


@pytest.mark.parametrize(
    "value",
    [0, -1, -10.5],
)
def test_budget_rejects_non_positive_execution_time(value):
    with pytest.raises(
        ValueError,
        match="max_execution_time_seconds must be greater than zero",
    ):
        AgentExecutionBudget(max_execution_time_seconds=value)


@pytest.mark.parametrize(
    "value",
    [float("inf"), float("-inf"), float("nan")],
)
def test_budget_rejects_non_finite_execution_time(value):
    with pytest.raises(
        ValueError,
        match="max_execution_time_seconds must be finite",
    ):
        AgentExecutionBudget(max_execution_time_seconds=value)


def test_budget_is_immutable():
    budget = AgentExecutionBudget()

    with pytest.raises(AttributeError):
        budget.max_iterations = 20
