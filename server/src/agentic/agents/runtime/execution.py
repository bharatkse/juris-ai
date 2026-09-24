"""
Agent execution service.

This module contains the runtime logic for executing one agent request.

AgentExecution is intentionally independent of LangGraph.

Responsibilities:
    - resolve the agent
    - resolve the agent policy
    - create request-scoped execution state
    - enforce lifecycle budgets
    - execute bounded reasoning
    - validate agent decisions
    - enforce agent policy
    - translate decisions into actions/results
    - apply retry policy
    - return AgentExecutionResult

This class does not:
    - build or modify LangGraph graphs
    - execute tools
    - invoke another agent directly
    - perform planning
    - mutate global execution state

AgentExecutionHandle owns one request-scoped continuation lifecycle.
It is never stored by AgentExecution and must not be shared between
concurrent executions.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

from adapters.observability.logger import get_logger
from agentic.agents.base import BaseAgent
from agentic.agents.runtime.lifecycle.budget import AgentExecutionBudget
from agentic.agents.runtime.lifecycle.guard import BudgetGuard
from agentic.agents.runtime.lifecycle.lifecycle import AgentLifecycle
from agentic.agents.runtime.lifecycle.state import AgentExecutionStatus, AgentState
from agentic.agents.runtime.lifecycle.termination import (
    AgentTerminator,
    TerminationReason,
)
from agentic.agents.runtime.retry import RetryClassifier
from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.decisions.validator import (
    AgentDecisionValidationError,
    AgentDecisionValidator,
)
from agentic.execution.config import ExecutionRetryPolicy
from agentic.policy.agent_policy import AgentPolicyProvider
from agentic.policy.guard import AgentPolicyGuard
from agentic.policy.schemas import AgentPolicy
from agentic.registry.protocols import AgentRegistryProtocol
from agentic.tools.constants import GATED_TOOLS
from core.dto.agent import AgentRequestDTO, AgentStreamChunkDTO
from core.dto.agent_action import AgentActionRequestDTO
from core.dto.tool import RetrievedContentDTO
from core.enums import (
    ActionTypeEnum,
    ExecutionStatusEnum,
)

logger = get_logger(__name__)


@dataclass(slots=True, frozen=True)
class AgentExecutionResult:
    """
    Result produced by one bounded agent execution slice.

    This object is independent of LangGraph.

    The LangGraph adapter is responsible for converting this result
    into graph-state updates.

    A COMPLETED result with an action means that the agent has completed
    a reasoning decision and produced an action request. It does not mean
    that the requested action has been executed.
    """

    status: ExecutionStatusEnum
    retry_count: int
    started_at: datetime
    completed_at: datetime
    termination_reason: str | None = None
    error: str | None = None
    partial_response: str | None = None
    decision: AgentDecision | None = None
    action: AgentActionRequestDTO | None = None


class _AgentReasoningFailure(Exception):
    """Internal marker that identifies failures from the LLM reasoning call."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(str(cause))
        self.cause = cause


class AgentExecutionHandle:
    """
    Request-scoped continuation handle for one agent execution.

    This object owns all mutable state associated with one agent
    execution lifecycle.

    It must:
        - belong to exactly one execution
        - never be stored globally
        - never be shared between concurrent requests

    AgentExecution creates the handle and remains stateless.

    The handle does not:
        - execute tools
        - invoke another agent directly
        - build LangGraph graphs
        - perform planning
    """

    def __init__(
        self,
        *,
        agent: BaseAgent,
        agent_id: str,
        request: AgentRequestDTO,
        policy: AgentPolicy,
        lifecycle: AgentLifecycle,
        retry_classifier: RetryClassifier,
        retry_policy: ExecutionRetryPolicy,
        max_attempts: int,
        decision_validator: AgentDecisionValidator,
        agent_policy_guard: AgentPolicyGuard,
        reasoning_context: tuple[
            RetrievedContentDTO,
            ...,
        ] = (),
    ) -> None:
        self._agent = agent
        self._agent_id = agent_id
        self._request = request
        self._policy = policy
        self._lifecycle = lifecycle
        self._retry_classifier = retry_classifier
        self._retry_policy = retry_policy
        self._max_attempts = max_attempts
        self._decision_validator = decision_validator
        self._agent_policy_guard = agent_policy_guard

        self._attempt_count = 0
        self._last_decision: AgentDecision | None = None
        self._closed = False
        self._reasoning_context = reasoning_context

    @property
    def state(self) -> AgentState:
        """Return the request-scoped agent state."""

        return self._lifecycle.state

    @property
    def lifecycle(self) -> AgentLifecycle:
        """Return the request-scoped lifecycle controller."""

        return self._lifecycle

    @property
    def request(self) -> AgentRequestDTO:
        """Return the original agent request."""

        return self._request

    @property
    def policy(self) -> AgentPolicy:
        """Return the resolved policy for this agent execution."""

        return self._policy

    @property
    def agent_id(self) -> str:
        """Return the agent identifier."""

        return self._agent_id

    @property
    def last_decision(self) -> AgentDecision | None:
        """Return the most recently produced decision."""

        return self._last_decision

    @property
    def reasoning_context(
        self,
    ) -> tuple[
        RetrievedContentDTO,
        ...,
    ]:
        """Return the evidence supplied to the current reasoning slice."""

        return self._reasoning_context

    def stream_final_answer(self) -> AsyncIterator[AgentStreamChunkDTO]:
        """
        Stream the freeform final-answer text for this execution's
        FINAL decision, using the request and accumulated
        reasoning_context this handle already owns.

        Thin delegation to BaseAgent.stream_final_answer(), matching
        this handle's existing convention (reason() similarly wraps
        agent-level reasoning together with handle-owned state) rather
        than exposing the private agent reference directly. No retry/
        lifecycle wrapping the way reason() has -- by the time a
        caller reaches this, the decision is already confirmed FINAL;
        this is a second, separate generation of the answer text, not
        another reasoning attempt.

        Callers (AgentExecutionNode, gated to streaming sessions only)
        are responsible for confirming last_decision.decision_type is
        FINAL before calling this -- it does not check itself.
        """

        return self._agent.stream_final_answer(
            request=self._request,
            context=self._reasoning_context,
        )

    def extend_reasoning_context(
        self,
        *,
        context: tuple[
            RetrievedContentDTO,
            ...,
        ],
    ) -> None:
        """
        Extend the reasoning context for a future continuation slice.

        The context belongs exclusively to this request-scoped handle.

        A new tuple is created rather than mutating an externally supplied
        collection, preserving isolation between concurrent executions.
        """

        if self._closed:
            raise RuntimeError(
                "Agent execution handle is already closed.",
            )

        if self._lifecycle.state.status is not AgentExecutionStatus.RUNNING:
            raise RuntimeError(
                "Agent execution handle is not running.",
            )

        if not context:
            return

        self._reasoning_context = (
            *self._reasoning_context,
            *context,
        )

    def partial_result(self) -> AgentExecutionResult:
        """
        Return the current request-scoped state as a PARTIAL result.

        Continuation services use this when a downstream action consumes
        the remaining lifecycle budget.
        """

        return self._build_partial_result(
            decision=self._last_decision,
        )

    def terminal_result(self) -> AgentExecutionResult:
        """
        Return the current terminal state as an execution result.

        Continuation services use this after explicitly transitioning
        the request-scoped lifecycle to a terminal state.
        """

        return self._build_terminal_result()

    async def reason(self) -> AgentExecutionResult:
        """
        Execute one bounded reasoning cycle using the same lifecycle.

        This method may be called again in a future continuation slice,
        provided the execution has not reached a terminal state.

        It does not execute TOOL_CALL or DELEGATE actions.
        """

        if self._closed:
            raise RuntimeError(
                "Agent execution handle is already closed.",
            )

        if self._lifecycle.state.status is not AgentExecutionStatus.RUNNING:
            return self._build_terminal_result()

        self._attempt_count += 1

        try:
            return await self._execute_reasoning_attempt()

        except _AgentReasoningFailure as failure:
            exc = failure.cause
            retryable = self._retry_classifier.is_retryable(
                error=exc,
            )

            if retryable and self._attempt_count < self._max_attempts:
                retry_count = self._attempt_count - 1
                retry_delay = self._retry_policy.delay_seconds(
                    retry_count=retry_count,
                )

                logger.warning(
                    "Agent reasoning attempt failed; retrying.",
                    extra={
                        "operation": "agent_execution_retry",
                        "execution_id": self._request.context.execution_id,
                        "thread_id": self._request.context.thread_id,
                        "agent_id": self._agent_id,
                        "attempt": self._attempt_count,
                        "retry_count": retry_count,
                        "max_attempts": self._max_attempts,
                        "retry_delay_seconds": retry_delay,
                        "error_type": type(exc).__name__,
                    },
                )

                await asyncio.sleep(retry_delay)

                return await self.reason()

            logger.error(
                "Agent reasoning failed.",
                extra={
                    "operation": "agent_reasoning",
                    "execution_id": self._request.context.execution_id,
                    "thread_id": self._request.context.thread_id,
                    "agent_id": self._agent_id,
                    "attempt": self._attempt_count,
                    "retry_count": max(self._attempt_count - 1, 0),
                    "max_attempts": self._max_attempts,
                    "retryable": retryable,
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )

            self._lifecycle.fail(
                TerminationReason.FAILED_LLM,
            )

            self._closed = True

            return AgentExecutionResult(
                status=ExecutionStatusEnum.FAILED,
                termination_reason=TerminationReason.FAILED_LLM.value,
                error=str(exc),
                partial_response=self.state.partial_response,
                decision=self._last_decision,
                action=None,
                retry_count=max(self._attempt_count - 1, 0),
                started_at=self._started_at,
                completed_at=datetime.now(UTC),
            )

        except Exception as exc:
            # Validation, policy, lifecycle, and action-construction failures
            # are not LLM failures and must never enter the retry classifier.
            logger.error(
                "Agent execution failed outside the LLM reasoning boundary.",
                extra={
                    "operation": "agent_execution",
                    "execution_id": self._request.context.execution_id,
                    "thread_id": self._request.context.thread_id,
                    "agent_id": self._agent_id,
                    "attempt": self._attempt_count,
                    "retry_count": max(self._attempt_count - 1, 0),
                    "max_attempts": self._max_attempts,
                    "retryable": False,
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )

            self._lifecycle.fail(
                TerminationReason.FAILED_LLM,
            )

            self._closed = True

            return AgentExecutionResult(
                status=ExecutionStatusEnum.FAILED,
                termination_reason=TerminationReason.FAILED_LLM.value,
                error=str(exc),
                partial_response=self.state.partial_response,
                decision=self._last_decision,
                action=None,
                retry_count=max(self._attempt_count - 1, 0),
                started_at=self._started_at,
                completed_at=datetime.now(UTC),
            )

    async def _execute_reasoning_attempt(
        self,
    ) -> AgentExecutionResult:
        """Execute one reasoning/validation/decision cycle."""

        started_at = self._started_at

        # --------------------------------------------------------------
        # 1. Total execution-step budget
        # --------------------------------------------------------------

        step_budget = self._lifecycle.begin_step()

        if not step_budget.allowed:
            self._closed = True

            return self._build_partial_result()

        # --------------------------------------------------------------
        # 2. Agent iteration budget
        # --------------------------------------------------------------

        iteration_budget = self._lifecycle.begin_iteration()

        if not iteration_budget.allowed:
            self._closed = True

            return self._build_partial_result()

        # --------------------------------------------------------------
        # 3. Agent reasoning
        # --------------------------------------------------------------

        try:
            decision = await self._agent._reason(
                request=self._request,
                context=self._reasoning_context,
            )
        except Exception as exc:
            # Only failures originating from the actual agent/LLM reasoning
            # call are eligible for RetryClassifier evaluation.
            raise _AgentReasoningFailure(exc) from exc

        self._last_decision = decision

        # --------------------------------------------------------------
        # 4. Validation budget
        # --------------------------------------------------------------

        validation_budget = self._lifecycle.begin_validation()

        if not validation_budget.allowed:
            self._closed = True

            return self._build_partial_result(
                decision=decision,
            )

        # --------------------------------------------------------------
        # 5. Validate structured decision
        # --------------------------------------------------------------

        try:
            decision = self._decision_validator.validate(
                decision,
            )

        except AgentDecisionValidationError as exc:
            self._lifecycle.fail(
                TerminationReason.FAILED_VALIDATION,
            )

            self._closed = True

            return AgentExecutionResult(
                status=ExecutionStatusEnum.FAILED,
                termination_reason=TerminationReason.FAILED_VALIDATION.value,
                error=str(exc),
                partial_response=self.state.partial_response,
                decision=decision,
                action=None,
                retry_count=max(self._attempt_count - 1, 0),
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        self._last_decision = decision

        # --------------------------------------------------------------
        # 6. Decision retention budget
        # --------------------------------------------------------------

        decision_budget = self._lifecycle.begin_decision()

        if not decision_budget.allowed:
            self._closed = True

            return self._build_partial_result(
                decision=decision,
            )

        # --------------------------------------------------------------
        # 7. Decision handling
        # --------------------------------------------------------------

        result = self._handle_decision(
            decision=decision,
        )

        # Agent lifecycle state, not the externally mapped
        # ExecutionStatusEnum, determines whether this handle is closed.
        #
        # TOOL_CALL and DELEGATE intentionally leave the lifecycle RUNNING
        # because their requested work has not yet been executed and the
        # agent may need to reason again after the executor supplies the
        # resulting information.
        if self.state.status in {
            AgentExecutionStatus.COMPLETED,
            AgentExecutionStatus.FAILED,
            AgentExecutionStatus.PARTIAL,
        }:
            self._closed = True

        return result

    def _handle_decision(
        self,
        *,
        decision: AgentDecision,
    ) -> AgentExecutionResult:
        """Convert one validated decision into an execution result."""

        completed_at = datetime.now(UTC)
        retry_count = max(self._attempt_count - 1, 0)

        # ==============================================================
        # FINAL
        # ==============================================================

        if decision.decision_type is AgentDecisionType.FINAL:
            self._lifecycle.set_partial_response(
                decision.final_response,
            )

            return AgentExecutionResult(
                status=ExecutionStatusEnum.COMPLETED,
                termination_reason=None,
                error=None,
                partial_response=self.state.partial_response,
                decision=decision,
                action=None,
                retry_count=retry_count,
                started_at=self._started_at,
                completed_at=completed_at,
            )

        # ==============================================================
        # NEED_INPUT
        # ==============================================================

        if decision.decision_type is AgentDecisionType.NEED_INPUT:
            question = decision.user_input.question if decision.user_input is not None else ""

            self._lifecycle.set_partial_response(
                question,
            )

            self._lifecycle.user_input_required()

            return AgentExecutionResult(
                status=ExecutionStatusEnum.COMPLETED,
                termination_reason=TerminationReason.USER_INPUT_REQUIRED.value,
                error=None,
                partial_response=self.state.partial_response,
                decision=decision,
                action=None,
                retry_count=retry_count,
                started_at=self._started_at,
                completed_at=completed_at,
            )

        # ==============================================================
        # FAIL
        # ==============================================================

        if decision.decision_type is AgentDecisionType.FAIL:
            message = (
                decision.failure.message
                if decision.failure is not None
                else "Agent execution failed."
            )

            self._lifecycle.set_partial_response(
                message,
            )

            self._lifecycle.fail(
                TerminationReason.FAILED_LLM,
            )

            return AgentExecutionResult(
                status=ExecutionStatusEnum.FAILED,
                termination_reason=TerminationReason.FAILED_LLM.value,
                error=message,
                partial_response=self.state.partial_response,
                decision=decision,
                action=None,
                retry_count=retry_count,
                started_at=self._started_at,
                completed_at=completed_at,
            )

        # ==============================================================
        # TOOL_CALL
        # ==============================================================

        if decision.decision_type is AgentDecisionType.TOOL_CALL:
            tool_call = decision.tool_call

            if tool_call is None:
                self._lifecycle.fail(
                    TerminationReason.FAILED_VALIDATION,
                )

                return AgentExecutionResult(
                    status=ExecutionStatusEnum.FAILED,
                    termination_reason=TerminationReason.FAILED_VALIDATION.value,
                    error="TOOL_CALL decision is missing tool_call.",
                    partial_response=self.state.partial_response,
                    decision=decision,
                    action=None,
                    retry_count=retry_count,
                    started_at=self._started_at,
                    completed_at=completed_at,
                )

            permission = self._agent_policy_guard.check_tool(
                policy=self._policy,
                tool_name=tool_call.tool_name,
            )

            if not permission.allowed:
                self._lifecycle.fail(
                    TerminationReason.FAILED_POLICY,
                )

                return AgentExecutionResult(
                    status=ExecutionStatusEnum.FAILED,
                    termination_reason=TerminationReason.FAILED_POLICY.value,
                    error=permission.reason,
                    partial_response=self.state.partial_response,
                    decision=decision,
                    action=None,
                    retry_count=retry_count,
                    started_at=self._started_at,
                    completed_at=completed_at,
                )

            # GATED_TOOLS (email/slack sends) are tagged SEND instead of
            # the usual TOOL_CALL -- AgentContinuationService reads this
            # to decide whether to execute immediately or pause for
            # human approval. Every other tool keeps TOOL_CALL, executed
            # immediately as before.
            action = AgentActionRequestDTO(
                execution_id=self._request.context.execution_id,
                thread_id=self._request.context.thread_id,
                conversation_event_id=self._request.context.conversation_event_id,
                agent_id=self._agent_id,
                action_type=(
                    ActionTypeEnum.SEND
                    if tool_call.tool_name in GATED_TOOLS
                    else ActionTypeEnum.TOOL_CALL
                ),
                tool_name=tool_call.tool_name,
                parameters=tool_call.parameters,
                reason=decision.reason or "",
            )

            action_budget = self._lifecycle.record_action(
                self._build_action_key(action),
            )

            if not action_budget.allowed:
                self._closed = True

                return self._build_partial_result(
                    decision=decision,
                )

            return AgentExecutionResult(
                status=ExecutionStatusEnum.COMPLETED,
                termination_reason=None,
                error=None,
                partial_response=self.state.partial_response,
                decision=decision,
                action=action,
                retry_count=retry_count,
                started_at=self._started_at,
                completed_at=completed_at,
            )

        # ==============================================================
        # DELEGATE
        # ==============================================================

        if decision.decision_type is AgentDecisionType.DELEGATE:
            delegation = decision.delegation

            if delegation is None:
                self._lifecycle.fail(
                    TerminationReason.FAILED_VALIDATION,
                )

                return AgentExecutionResult(
                    status=ExecutionStatusEnum.FAILED,
                    termination_reason=TerminationReason.FAILED_VALIDATION.value,
                    error="DELEGATE decision is missing delegation.",
                    partial_response=self.state.partial_response,
                    decision=decision,
                    action=None,
                    retry_count=retry_count,
                    started_at=self._started_at,
                    completed_at=datetime.now(UTC),
                )

            permission = self._agent_policy_guard.check_delegation(
                policy=self._policy,
                target_agent_id=delegation.target_agent_id,
            )

            if not permission.allowed:
                self._lifecycle.fail(
                    TerminationReason.FAILED_POLICY,
                )

                return AgentExecutionResult(
                    status=ExecutionStatusEnum.FAILED,
                    termination_reason=TerminationReason.FAILED_POLICY.value,
                    error=permission.reason,
                    partial_response=self.state.partial_response,
                    decision=decision,
                    action=None,
                    retry_count=max(self._attempt_count - 1, 0),
                    started_at=self._started_at,
                    completed_at=datetime.now(UTC),
                )

            action = AgentActionRequestDTO(
                execution_id=self._request.context.execution_id,
                thread_id=self._request.context.thread_id,
                conversation_event_id=self._request.context.conversation_event_id,
                agent_id=self._agent_id,
                action_type=ActionTypeEnum.AGENT_CALL,
                target_agent_id=delegation.target_agent_id,
                parameters=delegation.parameters,
                reason=decision.reason or "",
            )

            action_budget = self._lifecycle.record_action(
                self._build_action_key(action),
            )

            if not action_budget.allowed:
                self._closed = True

                return self._build_partial_result(
                    decision=decision,
                )

            return AgentExecutionResult(
                status=ExecutionStatusEnum.COMPLETED,
                termination_reason=None,
                error=None,
                partial_response=self.state.partial_response,
                decision=decision,
                action=action,
                retry_count=retry_count,
                started_at=self._started_at,
                completed_at=completed_at,
            )

        # ==============================================================
        # Unsupported decision
        # ==============================================================

        self._lifecycle.fail(
            TerminationReason.FAILED_VALIDATION,
        )

        return AgentExecutionResult(
            status=ExecutionStatusEnum.FAILED,
            termination_reason=TerminationReason.FAILED_VALIDATION.value,
            error="Unsupported agent decision.",
            partial_response=self.state.partial_response,
            decision=decision,
            action=None,
            retry_count=retry_count,
            started_at=self._started_at,
            completed_at=datetime.now(UTC),
        )

    @staticmethod
    def _build_action_key(
        action: AgentActionRequestDTO,
    ) -> str:
        """
        Build a deterministic identity for repeated internal actions.

        The key intentionally excludes the human-readable reason because
        repeated-action protection is concerned with repeating the same
        executable operation, not changes in model wording.
        """

        parameters = action.parameters or {}

        try:
            serialized_parameters = json.dumps(
                parameters,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except (TypeError, ValueError):
            serialized_parameters = repr(parameters)

        return "|".join(
            (
                action.action_type.value,
                action.tool_name or "",
                action.target_agent_id or "",
                serialized_parameters,
            ),
        )

    def _build_partial_result(
        self,
        *,
        decision: AgentDecision | None = None,
    ) -> AgentExecutionResult:
        """Build a partial result from the current request-scoped state."""

        reason = self.state.termination_reason

        return AgentExecutionResult(
            status=ExecutionStatusEnum.PARTIAL,
            termination_reason=(reason.value if reason is not None else None),
            error=None,
            partial_response=self.state.partial_response,
            decision=decision or self._last_decision,
            action=None,
            retry_count=max(self._attempt_count - 1, 0),
            started_at=self._started_at,
            completed_at=datetime.now(UTC),
        )

    def _build_terminal_result(self) -> AgentExecutionResult:
        """Return the current terminal state without starting new work."""

        status = self.state.status

        if status is AgentExecutionStatus.COMPLETED:
            execution_status = ExecutionStatusEnum.COMPLETED
        elif status is AgentExecutionStatus.FAILED:
            execution_status = ExecutionStatusEnum.FAILED
        else:
            execution_status = ExecutionStatusEnum.PARTIAL

        reason = self.state.termination_reason

        return AgentExecutionResult(
            status=execution_status,
            termination_reason=(reason.value if reason is not None else None),
            error=None,
            partial_response=self.state.partial_response,
            decision=self._last_decision,
            action=None,
            retry_count=max(self._attempt_count - 1, 0),
            started_at=self._started_at,
            completed_at=datetime.now(UTC),
        )

    @property
    def _started_at(self) -> datetime:
        """Return the lifecycle start timestamp."""

        return self.state.started_at


class AgentExecution:
    """
    Coordinates bounded execution of one agent.

    AgentExecution itself is stateless.

    Each call to start() creates an independent
    AgentExecutionHandle containing its own request-scoped state.

    It does not execute tools or delegated agents.
    """

    def __init__(
        self,
        *,
        agent_registry: AgentRegistryProtocol,
        retry_policy: ExecutionRetryPolicy,
        retry_classifier: RetryClassifier,
        decision_validator: AgentDecisionValidator,
        agent_policy_provider: AgentPolicyProvider,
        agent_policy_guard: AgentPolicyGuard,
        agent_budget: AgentExecutionBudget | None = None,
    ) -> None:
        self._agent_registry = agent_registry
        self._retry_policy = retry_policy
        self._retry_classifier = retry_classifier
        self._decision_validator = decision_validator
        self._agent_policy_provider = agent_policy_provider
        self._agent_policy_guard = agent_policy_guard

        self._agent_budget = agent_budget or AgentExecutionBudget()

        self._budget_guard = BudgetGuard(
            self._agent_budget,
        )
        self._terminator = AgentTerminator()

    async def start(
        self,
        *,
        agent_id: str,
        request: AgentRequestDTO,
        reasoning_context: tuple[
            RetrievedContentDTO,
            ...,
        ] = (),
    ) -> AgentExecutionHandle:
        """
        Create a request-scoped agent execution handle.

        No mutable execution state is stored on AgentExecution.
        """

        agent = self._agent_registry.resolve(
            key=agent_id,
        )

        policy = await self._agent_policy_provider.get_policy(
            agent_id=agent_id,
        )

        started_at = datetime.now(UTC)

        state = AgentState(
            budget=self._agent_budget,
            started_at=started_at,
        )

        lifecycle = AgentLifecycle(
            state=state,
            guard=self._budget_guard,
            terminator=self._terminator,
        )

        return AgentExecutionHandle(
            agent=agent,
            agent_id=agent_id,
            request=request,
            policy=policy,
            lifecycle=lifecycle,
            retry_classifier=self._retry_classifier,
            retry_policy=self._retry_policy,
            max_attempts=self._retry_policy.max_attempts,
            decision_validator=self._decision_validator,
            agent_policy_guard=self._agent_policy_guard,
            reasoning_context=reasoning_context,
        )

    async def execute(
        self,
        *,
        agent_id: str,
        request: AgentRequestDTO,
        reasoning_context: tuple[
            RetrievedContentDTO,
            ...,
        ] = (),
    ) -> AgentExecutionResult:
        """
        Execute one bounded agent request.

        This compatibility API creates a request-scoped handle and
        performs exactly one reasoning cycle.
        """

        execution = await self.start(
            agent_id=agent_id,
            request=request,
            reasoning_context=reasoning_context,
        )

        return await execution.reason()
