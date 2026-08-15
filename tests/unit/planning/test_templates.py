"""
Tests for deterministic planning templates.
"""

from __future__ import annotations

import pytest

from src.core.dto.planning import PlanningRequestDTO
from src.core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from src.planning.templates import PlanTemplateRegistry


@pytest.mark.parametrize(
    (
        "message",
        "expected_intent",
        "expected_agent",
        "expected_step_id",
    ),
    (
        (
            "Review this contract.",
            IntentEnum.CONTRACT_REVIEW,
            AgentTypeEnum.CONTRACT,
            "review_contract",
        ),
        (
            "Analyze this contract.",
            IntentEnum.CONTRACT_ANALYSIS,
            AgentTypeEnum.CONTRACT,
            "analyze_contract",
        ),
        (
            "Extract important clauses.",
            IntentEnum.CLAUSE_EXTRACTION,
            AgentTypeEnum.CONTRACT,
            "extract_clauses",
        ),
        (
            "Identify contractual risks.",
            IntentEnum.RISK_ANALYSIS,
            AgentTypeEnum.CONTRACT,
            "identify_risks",
        ),
        (
            "Research the applicable regulation.",
            IntentEnum.LEGAL_RESEARCH,
            AgentTypeEnum.LEGAL,
            "answer_legal_question",
        ),
    ),
)
def test_resolve_returns_matching_template(
    template_registry: PlanTemplateRegistry,
    message: str,
    expected_intent: IntentEnum,
    expected_agent: AgentTypeEnum,
    expected_step_id: str,
) -> None:
    """
    Resolve an unambiguous supported request to its template.
    """

    plan = template_registry.resolve(
        request=PlanningRequestDTO(
            message=message,
        ),
    )

    assert plan is not None
    assert plan.intent is expected_intent
    assert plan.mode is ExecutionModeEnum.SEQUENTIAL
    assert len(plan.steps) == 1

    step = plan.steps[0]

    assert step.id == expected_step_id
    assert step.agent is expected_agent
    assert step.depends_on == ()
    assert step.stage == 1
    assert step.instruction


def test_resolve_returns_none_for_unknown_request(
    template_registry: PlanTemplateRegistry,
) -> None:
    """
    Return None when no deterministic template matches.
    """

    plan = template_registry.resolve(
        request=PlanningRequestDTO(
            message="What is the limitation period for a civil claim?",
        ),
    )

    assert plan is None


def test_resolve_returns_none_for_ambiguous_request(
    template_registry: PlanTemplateRegistry,
) -> None:
    """
    Return None when multiple templates match the request.

    Ambiguous requests must be delegated to the LLM planner.
    """

    plan = template_registry.resolve(
        request=PlanningRequestDTO(
            message=("Review this contract and identify " "contractual risks."),
        ),
    )

    assert plan is None


@pytest.mark.parametrize(
    "message",
    (
        "  REVIEW   THIS   CONTRACT  ",
        "Review this contract.",
        "review this contract",
    ),
)
def test_resolve_normalizes_request(
    template_registry: PlanTemplateRegistry,
    message: str,
) -> None:
    """
    Normalize whitespace and casing before matching.
    """

    plan = template_registry.resolve(
        request=PlanningRequestDTO(
            message=message,
        ),
    )

    assert plan is not None
    assert plan.intent is IntentEnum.CONTRACT_REVIEW


def test_default_returns_general_plan(
    template_registry: PlanTemplateRegistry,
) -> None:
    """
    Return the default general execution plan.
    """

    plan = template_registry.default()

    assert plan.intent is IntentEnum.GENERAL
    assert plan.mode is ExecutionModeEnum.SEQUENTIAL
    assert len(plan.steps) == 1

    step = plan.steps[0]

    assert step.id == "answer"
    assert step.agent is AgentTypeEnum.LEGAL
    assert step.depends_on == ()
    assert step.stage == 1
