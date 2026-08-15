"""
Collaboration bus.

Provides mediated communication between agents during a single execution.

Agents never communicate directly with one another. All collaboration
flows through this bus.
"""

from __future__ import annotations

from src.core.enums import AgentTypeEnum
from src.core.exceptions.agent import AgentExecutionError
from src.core.schemas.message import AgentMessageSchema
from src.execution.protocols import AgentMessageHandler


class CollaborationBus:
    """
    Mediates communication between agents.

    The Executor owns the CollaborationBus and injects it into
    participating agents.
    """

    def __init__(
        self,
    ) -> None:
        self._handlers: dict[
            AgentTypeEnum,
            AgentMessageHandler,
        ] = {}

    def register(
        self,
        *,
        agent: AgentTypeEnum,
        handler: AgentMessageHandler,
    ) -> None:
        """
        Register an agent message handler.
        """

        self._handlers[agent] = handler

    async def send(
        self,
        *,
        message: AgentMessageSchema,
    ) -> object:
        """
        Send a message to another agent.

        Raises:
            AgentExecutionError:
                If the recipient is not registered.
        """

        handler = self._handlers.get(
            message.recipient,
        )

        if handler is None:
            raise AgentExecutionError(
                message=(f"No handler registered for agent " f"'{message.recipient.value}'."),
            )

        return await handler.handle_message(
            message=message,
        )
