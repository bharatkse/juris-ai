"""
LangGraph execution graph builder.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agentic.execution.graph.state import ExecutionGraphState, ExecutionStepUpdate
from agentic.execution.protocols import StepNode
from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import ExecutionStatusEnum


class ExecutionGraphBuilder:
    """
    Builds a LangGraph workflow from a validated execution plan.

    Execution dependencies declared by ExecutionPlanDTO determine
    graph topology.

    LangGraph owns runtime scheduling. Step wrappers determine whether
    an individual step is eligible for agent execution.
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
    ) -> Callable[
        [ExecutionGraphState],
        Awaitable[dict[str, Any]],
    ]:
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
        """

        if not step.depends_on:
            return True

        statuses = {
            update["step_id"]: update["status"] for update in state["execution_state_updates"]
        }

        return all(
            statuses.get(dependency) is ExecutionStatusEnum.COMPLETED
            for dependency in step.depends_on
        )

    @staticmethod
    def _build_skipped_update(
        *,
        step: ExecutionStepDTO,
    ) -> dict[str, Any]:
        """
        Build the execution-state update for a skipped step.
        """

        return {
            "execution_state_updates": [
                ExecutionStepUpdate(
                    step_id=step.id,
                    status=ExecutionStatusEnum.SKIPPED,
                    retry_count=0,
                    started_at=None,
                    completed_at=None,
                    error=(
                        "Step skipped because one or more "
                        "dependencies did not complete successfully."
                    ),
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
