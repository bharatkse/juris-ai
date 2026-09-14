"""
Execution runtime factory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.checkpoint.base import BaseCheckpointSaver

from adapters.persistence.sqlalchemy.session import session_factory
from agentic.agents.runtime.retry import RetryClassifier
from agentic.collaboration.bus import CollaborationBus
from agentic.evaluation.answer import AnswerEvaluator, AnswerQualityPolicy
from agentic.evaluation.similarity import EmbeddingSimilarity
from agentic.execution.config import (
    ExecutionRetryPolicy,
    ExecutionTimeoutPolicy,
)
from agentic.execution.executor import Executor
from agentic.execution.graph.builder import ExecutionGraphBuilder
from agentic.execution.graph.factory import ExecutionGraphFactory
from agentic.execution.state import ExecutionStateAssembler
from agentic.policy.agent_policy import DatabaseAgentPolicyProvider
from agentic.policy.guard import AgentPolicyGuard
from agentic.policy.tool_permission import ToolPermissionGuard
from agentic.tools.runtime.invocation import ToolExecutionService
from wiring.containers import ClientContainer, RegistryContainer
from wiring.factories.evaluation import build_faithfulness_backend

if TYPE_CHECKING:
    from config.settings import Settings


def create_executor(
    *,
    registries: RegistryContainer,
    clients: ClientContainer,
    settings: Settings,
    collaboration_bus: CollaborationBus,
    checkpointer: BaseCheckpointSaver,
) -> Executor:
    """
    Create the configured execution runtime.
    """
    policy_provider = DatabaseAgentPolicyProvider(
        session_factory=session_factory,
    )

    policy_guard = AgentPolicyGuard(
        tool_permission_guard=ToolPermissionGuard(),
    )

    retry_policy = ExecutionRetryPolicy()
    retry_classifier = RetryClassifier()
    timeout_policy = ExecutionTimeoutPolicy()

    graph_builder = ExecutionGraphBuilder()

    tool_execution_service = ToolExecutionService(
        tool_registry=registries.tool_registry,
    )

    # Reuses the process-lifetime embedding provider already loaded for
    # RAG retrieval (clients.embedding_provider) rather than loading a
    # second copy of the model. Groundedness goes through the same
    # legacy/ragas FaithfulnessBackend switch RAG evaluation uses
    # (settings.llm.faithfulness_backend, default "legacy") -- this
    # factory doesn't choose or hardcode either implementation.
    answer_evaluator = AnswerEvaluator(
        similarity=EmbeddingSimilarity(
            embedding_provider=clients.embedding_provider,
        ),
        faithfulness_backend=build_faithfulness_backend(
            settings=settings,
            cache=clients.cache,
        ),
    )
    answer_quality_policy = AnswerQualityPolicy()

    graph_factory = ExecutionGraphFactory(
        builder=graph_builder,
        agent_registry=registries.agent_registry,
        agent_policy_provider=policy_provider,
        agent_policy_guard=policy_guard,
        retry_policy=retry_policy,
        retry_classifier=retry_classifier,
        tool_execution_service=tool_execution_service,
        collaboration_bus=collaboration_bus,
        answer_evaluator=answer_evaluator,
        answer_quality_policy=answer_quality_policy,
        checkpointer=checkpointer,
    )

    state_assembler = ExecutionStateAssembler()

    return Executor(
        graph_factory=graph_factory,
        state_assembler=state_assembler,
        timeout_policy=timeout_policy,
        tool_execution_service=tool_execution_service,
    )
