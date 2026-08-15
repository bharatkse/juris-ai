"""
Tests for LLM-backed execution plan generation.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.core.dto.planning import ExecutionPlanDTO
from src.core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from src.core.schemas.planning import (
    ExecutionPlanResponseSchema,
    ExecutionStepResponseSchema,
)
from src.planning.llm_planner import LLMPlanGenerator
from tests.builders.planning import (
    build_execution_plan_response,
    build_planning_request,
)


@pytest.mark.asyncio
async def test_generate_calls_llm_once(
    llm_generator: LLMPlanGenerator,
    mock_llm_client: Mock,
    mock_prompt_builder: Mock,
) -> None:
    """
    Generate an execution plan with exactly one LLM call.
    """
    planning_request = build_planning_request()
    execution_plan_response = build_execution_plan_response()

    mock_llm_client.generate_structured.return_value = execution_plan_response

    plan = await llm_generator.generate(
        request=planning_request,
    )

    assert mock_llm_client.generate_structured.await_count == 1

    mock_prompt_builder.build.assert_called_once_with(
        request=planning_request,
    )

    assert isinstance(
        plan,
        ExecutionPlanDTO,
    )


@pytest.mark.asyncio
async def test_generate_preserves_plan_intent(
    llm_generator: LLMPlanGenerator,
    mock_llm_client: Mock,
) -> None:
    """
    Preserve the intent produced by the planning LLM.
    """
    planning_request = build_planning_request()
    execution_plan_response = build_execution_plan_response()

    mock_llm_client.generate_structured.return_value = execution_plan_response

    plan = await llm_generator.generate(
        request=planning_request,
    )

    assert plan.intent is IntentEnum.RISK_ANALYSIS


@pytest.mark.asyncio
async def test_generate_preserves_execution_mode(
    llm_generator: LLMPlanGenerator,
    mock_llm_client: Mock,
) -> None:
    """
    Preserve the execution mode produced by the planning LLM.
    """
    planning_request = build_planning_request()
    execution_plan_response = build_execution_plan_response()

    mock_llm_client.generate_structured.return_value = execution_plan_response

    plan = await llm_generator.generate(
        request=planning_request,
    )

    assert plan.mode is ExecutionModeEnum.SEQUENTIAL


@pytest.mark.asyncio
async def test_generate_maps_execution_steps(
    llm_generator: LLMPlanGenerator,
    mock_llm_client: Mock,
) -> None:
    """
    Convert LLM execution steps into domain execution steps.
    """
    planning_request = build_planning_request()
    execution_plan_response = build_execution_plan_response()
    mock_llm_client.generate_structured.return_value = execution_plan_response

    plan = await llm_generator.generate(
        request=planning_request,
    )

    assert len(plan.steps) == 1

    step = plan.steps[0]

    assert step.id == "identify_risks"
    assert step.agent is AgentTypeEnum.CONTRACT
    assert step.instruction == "Identify contractual risks."
    assert step.depends_on == ()
    assert step.stage == 1
    assert step.arguments == {
        "severity": "high",
    }


@pytest.mark.asyncio
async def test_generate_preserves_dependencies(
    llm_generator: LLMPlanGenerator,
    mock_llm_client: Mock,
) -> None:
    """
    Preserve execution dependencies returned by the LLM.
    """
    planning_request = build_planning_request()

    response = ExecutionPlanResponseSchema(
        intent=IntentEnum.RISK_ANALYSIS,
        mode=ExecutionModeEnum.HYBRID,
        steps=(
            ExecutionStepResponseSchema(
                id="analyze",
                agent=AgentTypeEnum.CONTRACT,
                instruction="Analyze the contract.",
                depends_on=(),
            ),
            ExecutionStepResponseSchema(
                id="risk",
                agent=AgentTypeEnum.CONTRACT,
                instruction="Identify risks.",
                depends_on=("analyze",),
            ),
        ),
    )

    mock_llm_client.generate_structured.return_value = response

    plan = await llm_generator.generate(
        request=planning_request,
    )

    assert plan.steps[0].depends_on == ()
    assert plan.steps[1].depends_on == ("analyze",)


@pytest.mark.asyncio
async def test_generate_preserves_metadata(
    llm_generator: LLMPlanGenerator, mock_llm_client: Mock
) -> None:
    """
    Preserve planning metadata returned by the LLM.
    """
    planning_request = build_planning_request()
    execution_plan_response = build_execution_plan_response()
    mock_llm_client.generate_structured.return_value = execution_plan_response

    plan = await llm_generator.generate(
        request=planning_request,
    )

    assert plan.metadata == {
        "source": "llm",
    }
