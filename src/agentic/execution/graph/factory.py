"""
LangGraph execution graph factory.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from agentic.execution.config import ExecutionRetryPolicy
from agentic.execution.graph.builder import ExecutionGraphBuilder
from agentic.execution.graph.nodes import AgentExecutionNode
from agentic.execution.retry import RetryClassifier
from agentic.registry.agent import AgentRegistry
from core.dto.planning import ExecutionPlanDTO


class ExecutionGraphFactory:
    """
    Creates compiled LangGraph execution workflows.

    The factory owns graph runtime dependency wiring while keeping
    the Executor and ExecutionSession independent from LangGraph
    node construction details.
    """

    def __init__(
        self,
        *,
        builder: ExecutionGraphBuilder,
        agent_registry: AgentRegistry,
        retry_policy: ExecutionRetryPolicy,
        retry_classifier: RetryClassifier,
        checkpointer: BaseCheckpointSaver,
    ) -> None:
        self._builder = builder
        self._agent_registry = agent_registry
        self._retry_policy = retry_policy
        self._retry_classifier = retry_classifier
        self._checkpointer = checkpointer

    def create(
        self,
        *,
        plan: ExecutionPlanDTO,
    ) -> CompiledStateGraph:
        """
        Create a compiled execution graph from a validated plan.
        """

        step_node = AgentExecutionNode(
            agent_registry=self._agent_registry,
            retry_policy=self._retry_policy,
            retry_classifier=self._retry_classifier,
        )

        return self._builder.compile(
            plan=plan,
            step_node=step_node,
            checkpointer=self._checkpointer,
        )
