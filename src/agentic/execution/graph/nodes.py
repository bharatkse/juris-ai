"""
LangGraph execution nodes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from adapters.observability.logger import get_logger
from adapters.observability.tracing import add_span_event, span
from agentic.agents.base import BaseAgent
from agentic.execution.config import ExecutionRetryPolicy
from agentic.execution.graph.state import (
    ExecutionArtifactUpdate,
    ExecutionGraphState,
    ExecutionStepUpdate,
)
from agentic.execution.retry import RetryClassifier
from agentic.registry.agent import AgentRegistry
from core.dto.agent import AgentRequestDTO
from core.dto.planning import ExecutionStepDTO
from core.enums import ExecutionStatusEnum

logger = get_logger(__name__)


class AgentExecutionNode:
    """
    Executes an eligible execution step within LangGraph.

    Agent reasoning is delegated to the resolved agent.

    A concrete action produced by the agent is returned as part of
    the LangGraph state. Action preparation is handled after graph
    execution by the ExecutionSession through ActionWorkflowService.

    This node does not:

    - perform planning,
    - determine dependency eligibility,
    - implement authorization rules,
    - implement approval rules,
    - persist AgentAction,
    - execute concrete actions,
    - wait for human approval,
    - communicate directly with another agent.
    """

    def __init__(
        self,
        *,
        agent_registry: AgentRegistry,
        retry_policy: ExecutionRetryPolicy,
        retry_classifier: RetryClassifier,
    ) -> None:
        self._agent_registry = agent_registry
        self._retry_policy = retry_policy
        self._retry_classifier = retry_classifier

    async def __call__(
        self,
        state: ExecutionGraphState,
        *,
        step: ExecutionStepDTO,
    ) -> dict[str, Any]:
        """
        Execute an eligible agent step.

        Dependency eligibility must already have been established
        by the execution graph before this node is invoked.
        """

        started_at = datetime.now(UTC)
        last_error: Exception | None = None

        for attempt in range(
            1,
            self._retry_policy.max_attempts + 1,
        ):
            try:
                return await self._execute_attempt(
                    state=state,
                    step=step,
                    attempt=attempt,
                    started_at=started_at,
                )

            except Exception as exc:
                last_error = exc

                retryable = self._retry_classifier.is_retryable(
                    error=exc,
                )

                if not retryable or attempt >= self._retry_policy.max_attempts:
                    logger.error(
                        "Execution step failed.",
                        extra={
                            "operation": "execute_step",
                            "request_id": str(state["request_id"]),
                            "step_id": step.id,
                            "agent": step.agent,
                            "attempt": attempt,
                            "retry_count": attempt - 1,
                            "max_attempts": self._retry_policy.max_attempts,
                            "retryable": retryable,
                            "error_type": type(exc).__name__,
                        },
                        exc_info=True,
                    )

                    break

                logger.warning(
                    "Execution step attempt failed; retrying.",
                    extra={
                        "operation": "execute_step_retry",
                        "request_id": str(state["request_id"]),
                        "step_id": step.id,
                        "agent": step.agent,
                        "attempt": attempt,
                        "retry_count": attempt - 1,
                        "max_attempts": self._retry_policy.max_attempts,
                        "error_type": type(exc).__name__,
                    },
                )

        assert last_error is not None

        failed_at = datetime.now(UTC)

        return {
            "execution_state_updates": [
                ExecutionStepUpdate(
                    step_id=step.id,
                    status=ExecutionStatusEnum.FAILED,
                    retry_count=attempt - 1,
                    started_at=started_at,
                    completed_at=failed_at,
                    error=str(last_error),
                ),
            ],
        }

    async def _execute_attempt(
        self,
        *,
        state: ExecutionGraphState,
        step: ExecutionStepDTO,
        attempt: int,
        started_at: datetime,
    ) -> dict[str, Any]:
        """
        Execute one agent attempt.
        """

        agent_key = step.agent

        with span(
            "execution.agent.step",
            attributes={
                "execution.request_id": str(state["request_id"]),
                "execution.step_id": step.id,
                "execution.agent": agent_key,
                "execution.attempt": attempt,
            },
        ) as current_span:
            logger.info(
                "Starting execution step attempt.",
                extra={
                    "operation": "execute_step",
                    "request_id": str(state["request_id"]),
                    "step_id": step.id,
                    "agent": agent_key,
                    "attempt": attempt,
                },
            )

            add_span_event(
                current_span,
                "execution.step.started",
                attributes={
                    "execution.step_id": step.id,
                    "execution.agent": agent_key,
                    "execution.attempt": attempt,
                },
            )

            try:
                agent: BaseAgent = self._agent_registry.resolve(
                    key=agent_key,
                )

                add_span_event(
                    current_span,
                    "execution.agent.resolved",
                    attributes={
                        "execution.step_id": step.id,
                        "execution.agent": agent_key,
                    },
                )

                response = await agent.run(
                    request=AgentRequestDTO(
                        conversation=state["conversation"],
                        instruction=step.instruction,
                        arguments=step.arguments,
                        context=state["context"],
                    ),
                )

                completed_at = datetime.now(UTC)
                retry_count = attempt - 1

                add_span_event(
                    current_span,
                    "execution.step.completed",
                    attributes={
                        "execution.step_id": step.id,
                        "execution.attempt": attempt,
                        "execution.retry_count": retry_count,
                    },
                )

                logger.info(
                    "Execution step completed.",
                    extra={
                        "operation": "execute_step",
                        "request_id": str(state["request_id"]),
                        "step_id": step.id,
                        "agent": agent_key,
                        "attempt": attempt,
                        "retry_count": retry_count,
                        "action_present": response.action is not None,
                    },
                )

                return {
                    "execution_state_updates": [
                        ExecutionStepUpdate(
                            step_id=step.id,
                            status=ExecutionStatusEnum.COMPLETED,
                            retry_count=retry_count,
                            started_at=started_at,
                            completed_at=completed_at,
                            error=None,
                        ),
                    ],
                    "memory_updates": [
                        ExecutionArtifactUpdate(
                            key=f"{step.id}.response",
                            value=response,
                        ),
                    ],
                    "action": response.action,
                }

            except Exception as exc:
                add_span_event(
                    current_span,
                    "execution.step.failed",
                    attributes={
                        "execution.step_id": step.id,
                        "execution.agent": agent_key,
                        "execution.attempt": attempt,
                        "error_type": type(exc).__name__,
                    },
                )

                logger.warning(
                    "Execution step attempt failed.",
                    extra={
                        "operation": "execute_step_attempt_failed",
                        "request_id": str(state["request_id"]),
                        "step_id": step.id,
                        "agent": agent_key,
                        "attempt": attempt,
                        "max_attempts": self._retry_policy.max_attempts,
                        "error_type": type(exc).__name__,
                    },
                )

                raise
