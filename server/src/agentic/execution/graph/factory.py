"""
LangGraph execution graph factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from agentic.agents.runtime.continuation import AgentContinuationService
from agentic.agents.runtime.execution import AgentExecution
from agentic.agents.runtime.retry import RetryClassifier
from agentic.collaboration.bus import CollaborationBus
from agentic.decisions.validator import AgentDecisionValidator
from agentic.evaluation.answer import AnswerEvaluator, AnswerQualityPolicy
from agentic.execution.config import ExecutionRetryPolicy
from agentic.execution.graph.builder import ExecutionGraphBuilder
from agentic.execution.graph.nodes import AgentExecutionNode
from agentic.policy.agent_policy import AgentPolicyProvider
from agentic.policy.guard import AgentPolicyGuard
from agentic.registry.protocols import AgentRegistryProtocol, ToolRegistryProtocol
from agentic.tools.runtime.invocation import ToolExecutionService
from core.dto.planning import ExecutionPlanDTO

if TYPE_CHECKING:
    # Same deferred-import reasoning as continuation.py -- see its
    # TYPE_CHECKING block.
    from application.services.compliance_log import StandaloneComplianceLogWriter


class ExecutionGraphFactory:
    """
    Creates compiled LangGraph execution workflows.

    The factory owns graph runtime dependency wiring while keeping
    Executor and ExecutionSession independent from LangGraph
    node-construction details.

    The factory itself is stateless and safe to reuse across
    concurrent execution requests.
    """

    def __init__(
        self,
        *,
        builder: ExecutionGraphBuilder,
        agent_registry: AgentRegistryProtocol,
        tool_registry: ToolRegistryProtocol,
        agent_policy_provider: AgentPolicyProvider,
        agent_policy_guard: AgentPolicyGuard,
        retry_policy: ExecutionRetryPolicy,
        retry_classifier: RetryClassifier,
        tool_execution_service: ToolExecutionService,
        collaboration_bus: CollaborationBus,
        answer_evaluator: AnswerEvaluator,
        answer_quality_policy: AnswerQualityPolicy,
        checkpointer: BaseCheckpointSaver,
        compliance_log: StandaloneComplianceLogWriter,
    ) -> None:
        self._builder = builder
        self._agent_registry = agent_registry
        self._tool_registry = tool_registry
        self._agent_policy_provider = agent_policy_provider
        self._agent_policy_guard = agent_policy_guard
        self._retry_policy = retry_policy
        self._retry_classifier = retry_classifier
        self._tool_execution_service = tool_execution_service
        self._collaboration_bus = collaboration_bus
        self._answer_evaluator = answer_evaluator
        self._answer_quality_policy = answer_quality_policy
        self._decision_validator = AgentDecisionValidator()
        self._checkpointer = checkpointer
        self._compliance_log = compliance_log

    def create(
        self,
        *,
        plan: ExecutionPlanDTO,
    ) -> CompiledStateGraph:
        """
        Create a compiled execution graph from a validated plan.

        AgentExecution is created per graph construction and remains
        stateless during graph invocation. Request-scoped mutable
        execution state is owned by AgentExecutionHandle.
        """

        step_node = AgentExecutionNode(
            agent_execution=self.agent_execution(),
            continuation_service=self.continuation_service(),
        )

        return self._builder.compile(
            plan=plan,
            step_node=step_node,
            checkpointer=self._checkpointer,
        )

    def agent_execution(
        self,
    ) -> AgentExecution:
        """
        A stateless AgentExecution (per-request state lives on the handle).
        """

        return AgentExecution(
            agent_registry=self._agent_registry,
            retry_policy=self._retry_policy,
            retry_classifier=self._retry_classifier,
            decision_validator=self._decision_validator,
            agent_policy_provider=self._agent_policy_provider,
            agent_policy_guard=self._agent_policy_guard,
            tool_registry=self._tool_registry,
        )

    def continuation_service(
        self,
    ) -> AgentContinuationService:
        """
        A stateless AgentContinuationService for the same runtime.
        """

        return AgentContinuationService(
            tool_execution_service=self._tool_execution_service,
            collaboration_bus=self._collaboration_bus,
            answer_evaluator=self._answer_evaluator,
            answer_quality_policy=self._answer_quality_policy,
            agent_policy_guard=self._agent_policy_guard,
            compliance_log=self._compliance_log,
        )
