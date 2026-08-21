"""
Execution state assembler.
"""

from __future__ import annotations

from src.core.dto.action import ActionRequestDTO
from src.core.enums import ExecutionStatusEnum
from src.execution.graph.state import ExecutionGraphState
from src.execution.schemas.memory import ExecutionMemorySchema
from src.execution.schemas.state import ExecutionStateSchema


class ExecutionStateAssembler:
    """
    Converts LangGraph runtime state into execution-domain state.

    The assembler is the boundary between LangGraph's immutable
    update-oriented state and the execution runtime's mutable state.
    """

    def assemble_state(
        self,
        *,
        graph_state: ExecutionGraphState,
    ) -> ExecutionStateSchema:
        """
        Assemble execution state from graph updates.
        """

        state = ExecutionStateSchema(
            request_id=graph_state["request_id"],
        )

        for step in graph_state["plan"].steps:
            state.register_step(
                step_id=step.id,
            )

        for update in graph_state["execution_state_updates"]:
            step_state = state.steps[update["step_id"]]

            step_state.status = update["status"]
            step_state.retry_count = update["retry_count"]
            step_state.started_at = update["started_at"]
            step_state.completed_at = update["completed_at"]
            step_state.error = update["error"]

        statuses = [step.status for step in state.steps.values()]

        if any(status is ExecutionStatusEnum.FAILED for status in statuses):
            state.status = ExecutionStatusEnum.FAILED

        elif statuses and all(
            status
            in {
                ExecutionStatusEnum.COMPLETED,
                ExecutionStatusEnum.SKIPPED,
            }
            for status in statuses
        ):
            state.status = ExecutionStatusEnum.COMPLETED

        return state

    def assemble_memory(
        self,
        *,
        graph_state: ExecutionGraphState,
    ) -> ExecutionMemorySchema:
        """
        Assemble execution memory from graph updates.
        """

        memory = ExecutionMemorySchema()

        for update in graph_state["memory_updates"]:
            memory.put_artifact(
                key=update["key"],
                value=update["value"],
            )

        return memory

    def assemble_action(
        self,
        *,
        graph_state: ExecutionGraphState,
    ) -> ActionRequestDTO | None:
        """
        Assemble the proposed action from graph state.
        """

        return graph_state.get("action")
