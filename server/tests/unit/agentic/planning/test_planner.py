"""
Tests for execution planning orchestration.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from agentic.orchestration.schemas.context import (
    ConversationContext,
    DocumentContext,
    OrchestrationContext,
    RequestContext,
    RuntimeContext,
    UserContext,
)
from agentic.planning.planner import ExecutionPlanner
from agentic.planning.templates import PlanTemplateRegistry
from core.exceptions.planning import PlanValidationError
from tests.builders.agentic.orchestrator import build_conversation_message
from tests.builders.agentic.planning import build_context, build_planning_request
from tests.unit.helpers.identifiers import unknown_conversation_id, unknown_user_id


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
async def test_create_plan_uses_default_when_template_does_not_match(
    planner: ExecutionPlanner,
    mock_template_registry: Mock,
    mock_llm_planner: Mock,
    mock_plan_validator: Mock,
) -> None:
    """
    Use the default one-step plan instead of a planning LLM call.
    """

    mock_template_registry.resolve.return_value = None

    default_plan = PlanTemplateRegistry().default()
    mock_template_registry.default.return_value = default_plan
    mock_plan_validator.validate.return_value = default_plan

    context = build_context(
        message="How do I ask for alimony during a divorce?",
    )

    result = await planner.create_plan(
        context=context,
    )

    mock_template_registry.resolve.assert_called_once()
    mock_template_registry.default.assert_called_once_with()
    mock_llm_planner.generate.assert_not_called()
    mock_plan_validator.validate.assert_called_once_with(default_plan)
    assert result is default_plan


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
