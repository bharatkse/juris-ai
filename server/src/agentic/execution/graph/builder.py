"""
LangGraph execution graph builder.
"""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Protocol

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agentic.execution.graph.state import (
    ExecutionGraphState,
    ExecutionStepUpdate,
)
from agentic.execution.protocols import StepNode
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import ExecutionStatusEnum


class _GraphStepNode(Protocol):
    """
    A graph node. Declared as a Protocol, not Callable[[...], ...]:
    LangGraph's node protocol takes a parameter *named* ``state``,
    which a positional-only Callable type cannot satisfy.
    """

    def __call__(self, state: ExecutionGraphState) -> Awaitable[dict[str, Any]]: ...


class ExecutionGraphBuilder:
    """
    Builds a LangGraph workflow from a validated execution plan.

    Execution dependencies declared by ExecutionPlanDTO determine
    graph topology.

    LangGraph owns runtime scheduling. Step wrappers determine whether
    an individual step is eligible for agent execution.

    This builder is stateless and safe to reuse across graph invocations.
    """

    def build(
        self,
        *,
        plan: ExecutionPlanDTO,
        step_node: StepNode,
    ) -> StateGraph:
        """
        Build a StateGraph from a validated execution plan.
        """

        graph = StateGraph(
            ExecutionGraphState,
        )

        for step in plan.steps:
            graph.add_node(
                step.id,
                self._create_step_node(
                    step=step,
                    step_node=step_node,
                ),
            )

        self._add_edges(
            graph=graph,
            plan=plan,
        )

        return graph

    def compile(
        self,
        *,
        plan: ExecutionPlanDTO,
        step_node: StepNode,
        checkpointer: BaseCheckpointSaver,
    ) -> CompiledStateGraph:
        """
        Build and compile the execution graph.

        The checkpointer is attached at the LangGraph compilation
        boundary so the compiled graph can persist and resume
        execution state.
        """

        graph = self.build(
            plan=plan,
            step_node=step_node,
        )

        return graph.compile(
            checkpointer=checkpointer,
        )

    @staticmethod
    def _create_step_node(
        *,
        step: ExecutionStepDTO,
        step_node: StepNode,
    ) -> _GraphStepNode:
        """
        Bind an execution step to the runtime callback.

        A step is executed only when all of its dependencies have
        completed successfully. Otherwise, the step is marked skipped.
        """

        async def execute_step(
            state: ExecutionGraphState,
        ) -> dict[str, Any]:
            if not ExecutionGraphBuilder._dependencies_completed(
                state=state,
                step=step,
            ):
                return ExecutionGraphBuilder._build_skipped_update(
                    step=step,
                )

            return await step_node(
                state,
                step=step,
            )

        return execute_step

    @staticmethod
    def _dependencies_completed(
        *,
        state: ExecutionGraphState,
        step: ExecutionStepDTO,
    ) -> bool:
        """
        Determine whether all step dependencies completed successfully.

        Execution state updates are append-only history. Therefore, the
        latest update for each dependency is used when determining
        eligibility.

        A dependency is considered successful only when its latest status
        is COMPLETED. PARTIAL, FAILED, and SKIPPED dependencies do not
        satisfy the dependency requirement.
        """

        if not step.depends_on:
            return True

        statuses = ExecutionGraphBuilder._latest_step_statuses(
            state=state,
        )

        return all(
            statuses.get(dependency) is ExecutionStatusEnum.COMPLETED
            for dependency in step.depends_on
        )

    @staticmethod
    def _latest_step_statuses(
        *,
        state: ExecutionGraphState,
    ) -> dict[str, ExecutionStatusEnum]:
        """
        Resolve the latest known status for each execution step.

        ExecutionStepUpdate records are retained as append-only execution
        history. Iterating in reverse ensures the most recent update wins
        without mutating the underlying LangGraph state.
        """

        statuses: dict[str, ExecutionStatusEnum] = {}

        for update in reversed(state["execution_state_updates"]):
            step_id = update["step_id"]

            if step_id in statuses:
                continue

            statuses[step_id] = update["status"]

        return statuses

    @staticmethod
    def _build_skipped_update(
        *,
        step: ExecutionStepDTO,
    ) -> dict[str, Any]:
        """
        Build the execution-state update for a skipped step.

        A step is skipped when one or more dependencies did not complete
        successfully.

        Skipping is a workflow decision rather than an execution failure,
        so error and termination_reason are both unset.
        """

        return {
            "execution_state_updates": [
                ExecutionStepUpdate(
                    step_id=step.id,
                    status=ExecutionStatusEnum.SKIPPED,
                    retry_count=0,
                    started_at=None,
                    completed_at=None,
                    error=None,
                    termination_reason=None,
                ),
            ],
        }

    @staticmethod
    def _add_edges(
        *,
        graph: StateGraph,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Translate execution dependencies into LangGraph edges.

        Steps without dependencies start from START.

        Steps with one dependency wait for that dependency.

        Steps with multiple dependencies wait for all dependencies.
        """

        dependent_step_ids = {dependency for step in plan.steps for dependency in step.depends_on}

        for step in plan.steps:
            if not step.depends_on:
                graph.add_edge(
                    START,
                    step.id,
                )
                continue

            if len(step.depends_on) == 1:
                graph.add_edge(
                    step.depends_on[0],
                    step.id,
                )
                continue

            graph.add_edge(
                list(step.depends_on),
                step.id,
            )

        for step in plan.steps:
            if step.id not in dependent_step_ids:
                graph.add_edge(
                    step.id,
                    END,
                )
