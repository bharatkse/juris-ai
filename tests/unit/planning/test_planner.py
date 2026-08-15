"""
Tests for execution planning orchestration.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from src.core.dto.planning import ExecutionPlanDTO
from src.core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from src.core.exceptions.planning import PlanValidationError
from src.orchestration.schemas.context import (
    ConversationContext,
    DocumentContext,
    OrchestrationContext,
    RequestContext,
    RuntimeContext,
    UserContext,
)
from src.planning.planner import ExecutionPlanner
from src.planning.templates import PlanTemplateRegistry
from tests.builders.orchestrator import build_conversation_message
from tests.builders.planning import build_context, build_planning_request
from tests.helpers.identifiers import unknown_conversation_id, unknown_user_id


@pytest.mark.asyncio
async def test_create_plan_uses_template_without_llm(
    planner: ExecutionPlanner,
    mock_template_registry: Mock,
    mock_llm_planner: Mock,
    mock_plan_validator: Mock,
) -> None:
    """
    Use a deterministic template without calling the LLM.
    """

    template_plan = PlanTemplateRegistry().resolve(
        request=build_planning_request("Review this contract."),
    )

    assert template_plan is not None

    mock_template_registry.resolve.return_value = template_plan
    mock_plan_validator.validate.return_value = template_plan

    context = build_context(
        message="Review this contract.",
    )

    result = await planner.create_plan(
        context=context,
    )

    mock_template_registry.resolve.assert_called_once()

    mock_llm_planner.generate.assert_not_called()

    mock_plan_validator.validate.assert_called_once_with(template_plan)

    assert result is template_plan


@pytest.mark.asyncio
async def test_create_plan_uses_llm_when_template_does_not_match(
    planner: ExecutionPlanner,
    mock_template_registry: Mock,
    mock_llm_planner: Mock,
    mock_plan_validator: Mock,
) -> None:
    """
    Use the LLM planner when no deterministic template matches.
    """

    mock_template_registry.resolve.return_value = None

    llm_plan = ExecutionPlanDTO(
        intent=IntentEnum.RISK_ANALYSIS,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            # Keep this test focused on planner orchestration.
            # The LLMPlanGenerator tests already cover step mapping.
            # A minimal valid domain step is enough here.
            __import__(
                "src.core.dto.planning",
                fromlist=["ExecutionStepDTO"],
            ).ExecutionStepDTO(
                id="identify_risks",
                agent=AgentTypeEnum.CONTRACT,
                instruction="Identify contractual risks.",
            ),
        ),
    )

    mock_llm_planner.generate.return_value = llm_plan
    mock_plan_validator.validate.return_value = llm_plan

    context = build_context(
        message="What contractual risks should I consider?",
    )

    result = await planner.create_plan(
        context=context,
    )

    mock_template_registry.resolve.assert_called_once()

    mock_llm_planner.generate.assert_awaited_once()

    mock_plan_validator.validate.assert_called_once_with(llm_plan)

    assert result is llm_plan


@pytest.mark.asyncio
async def test_create_plan_passes_planning_request_to_template(
    planner: ExecutionPlanner,
    mock_template_registry: Mock,
    mock_plan_validator: Mock,
) -> None:
    """
    Build and pass the planning request to the template registry.
    """

    template_plan = PlanTemplateRegistry().default()

    mock_template_registry.resolve.return_value = template_plan
    mock_plan_validator.validate.return_value = template_plan

    context = build_context(
        message="Review this contract.",
    )

    await planner.create_plan(
        context=context,
    )

    request = mock_template_registry.resolve.call_args.kwargs["request"]

    assert request.message == "Review this contract."
    assert request.history == ()


@pytest.mark.asyncio
async def test_create_plan_passes_conversation_history(
    planner: ExecutionPlanner,
    mock_template_registry: Mock,
    mock_plan_validator: Mock,
) -> None:
    """
    Preserve conversation history when building the planning request.
    """

    template_plan = PlanTemplateRegistry().default()

    mock_template_registry.resolve.return_value = template_plan
    mock_plan_validator.validate.return_value = template_plan

    history = [
        build_conversation_message(
            content="The contract is governed by Indian law.",
        ),
    ]

    context = OrchestrationContext(
        request=RequestContext(
            message="Review the governing law clause.",
        ),
        conversation=ConversationContext(
            conversation_id=unknown_conversation_id(),
            history=history,
        ),
        user=UserContext(
            user_id=unknown_user_id(),
        ),
        documents=DocumentContext(),
        runtime=RuntimeContext(),
    )

    await planner.create_plan(
        context=context,
    )

    request = mock_template_registry.resolve.call_args.kwargs["request"]

    assert request.message == "Review the governing law clause."
    assert request.history == tuple(history)


@pytest.mark.asyncio
async def test_create_plan_validates_resolved_plan(
    planner: ExecutionPlanner,
    mock_template_registry: Mock,
    mock_plan_validator: Mock,
) -> None:
    """
    Validate every resolved execution plan.
    """

    plan = PlanTemplateRegistry().default()

    mock_template_registry.resolve.return_value = plan
    mock_plan_validator.validate.return_value = plan

    context = build_context(
        message="Review this contract.",
    )

    result = await planner.create_plan(
        context=context,
    )

    mock_plan_validator.validate.assert_called_once_with(plan)

    assert result is plan


@pytest.mark.asyncio
async def test_create_plan_propagates_validation_error(
    planner: ExecutionPlanner,
    mock_template_registry: Mock,
    mock_plan_validator: Mock,
) -> None:
    """
    Propagate plan validation failures.

    Invalid plans must not silently fall back to a generic plan.
    """

    plan = PlanTemplateRegistry().default()

    mock_template_registry.resolve.return_value = plan

    mock_plan_validator.validate.side_effect = PlanValidationError(
        message="Invalid execution plan.",
    )

    context = build_context(
        message="Review this contract.",
    )

    with pytest.raises(
        PlanValidationError,
        match="Invalid execution plan",
    ):
        await planner.create_plan(
            context=context,
        )

    mock_plan_validator.validate.assert_called_once_with(plan)
