"""
Fixtures for deterministic planning .
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from agentic.planning.llm_planner import LLMPlanGenerator
from agentic.planning.planner import ExecutionPlanner
from agentic.planning.prompts.planning import PlanningPromptBuilder
from agentic.planning.templates import PlanTemplateRegistry
from agentic.planning.validator import ExecutionPlanValidator


@pytest.fixture
def template_registry() -> PlanTemplateRegistry:
    """
    Provide a plan template registry.
    """

    return PlanTemplateRegistry()


@pytest.fixture
def plan_validator() -> ExecutionPlanValidator:
    """
    Provide an execution plan validator.
    """

    return ExecutionPlanValidator()


@pytest.fixture
def mock_prompt_builder() -> Mock:
    """
    Provide a mocked planning prompt builder.
    """

    return Mock(spec=PlanningPromptBuilder)


@pytest.fixture
def llm_generator(
    mock_llm_client: Mock,
    mock_prompt_builder: Mock,
) -> LLMPlanGenerator:
    """
    Provide an LLM plan generator.
    """

    return LLMPlanGenerator(
        llm_client=mock_llm_client,
        prompt_builder=mock_prompt_builder,
    )


@pytest.fixture
def mock_llm_planner() -> Mock:
    """
    Provide a mocked LLM planner.
    """

    planner = Mock(spec=LLMPlanGenerator)
    planner.generate = AsyncMock()

    return planner


@pytest.fixture
def mock_template_registry() -> Mock:
    """
    Provide a mocked template registry.
    """

    return Mock(spec=PlanTemplateRegistry)


@pytest.fixture
def mock_plan_validator() -> Mock:
    """
    Provide a mocked execution plan validator.
    """

    return Mock(spec=ExecutionPlanValidator)


@pytest.fixture
def planner(
    mock_template_registry: Mock,
    mock_llm_planner: Mock,
    mock_plan_validator: Mock,
) -> ExecutionPlanner:
    """
    Provide an execution planner.
    """

    return ExecutionPlanner(
        template_registry=mock_template_registry,
        llm_planner=mock_llm_planner,
        validator=mock_plan_validator,
    )
