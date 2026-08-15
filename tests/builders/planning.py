"""
Fixtures for deterministic planning .
"""

from __future__ import annotations

from src.core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO, PlanningRequestDTO
from src.core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum
from src.core.schemas.planning import (
    ExecutionPlanResponseSchema,
    ExecutionStepResponseSchema,
)
from src.orchestration.schemas.context import (
    ConversationContext,
    DocumentContext,
    OrchestrationContext,
    RequestContext,
    RuntimeContext,
    UserContext,
)
from tests.helpers.identifiers import unknown_conversation_id, unknown_user_id


def build_planning_request(msg: str | None = None) -> PlanningRequestDTO:
    """
    Provide a planning request.
    """
    if msg is None:
        msg = "Review this contract and identify contractual risks."
    return PlanningRequestDTO(
        message=msg,
    )


def build_execution_plan_response() -> ExecutionPlanResponseSchema:
    """
    Provide a structured LLM planning response.
    """

    return ExecutionPlanResponseSchema(
        intent=IntentEnum.RISK_ANALYSIS,
        mode=ExecutionModeEnum.SEQUENTIAL,
        steps=(
            ExecutionStepResponseSchema(
                id="identify_risks",
                agent=AgentTypeEnum.CONTRACT,
                instruction="Identify contractual risks.",
                depends_on=(),
                stage=1,
                arguments={
                    "severity": "high",
                },
            ),
        ),
        metadata={
            "source": "llm",
        },
    )


def build_context(
    *,
    message: str,
) -> OrchestrationContext:
    """
    Build an orchestration context for planner tests.
    """

    return OrchestrationContext(
        request=RequestContext(
            message=message,
        ),
        conversation=ConversationContext(
            conversation_id=unknown_conversation_id(),
            history=[],
        ),
        user=UserContext(
            user_id=unknown_user_id(),
        ),
        documents=DocumentContext(),
        runtime=RuntimeContext(),
    )


def build_step(
    step_id: str,
    *,
    depends_on: tuple[str, ...] = (),
    stage: int = 1,
) -> ExecutionStepDTO:
    """
    Build a valid execution step for testing.
    """

    return ExecutionStepDTO(
        id=step_id,
        agent=AgentTypeEnum.LEGAL,
        instruction=f"Execute {step_id}.",
        depends_on=depends_on,
        stage=stage,
    )


def build_plan(
    steps: tuple[ExecutionStepDTO, ...],
    *,
    mode: ExecutionModeEnum = ExecutionModeEnum.SEQUENTIAL,
) -> ExecutionPlanDTO:
    """
    Build a valid execution plan for testing.
    """

    return ExecutionPlanDTO(
        intent=IntentEnum.GENERAL,
        mode=mode,
        steps=steps,
    )
