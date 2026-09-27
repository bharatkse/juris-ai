"""
Collaboration bus.

Provides mediated communication between agents during a single execution.

Agents never communicate directly with one another. All collaboration
flows through this bus.
"""

from __future__ import annotations

from agentic.execution.protocols import AgentMessageHandler
from core.exceptions.agent import AgentExecutionError
from core.models.message import AgentMessageSchema


class CollaborationBus:
    """
    Mediates communication between agents.

    Agents never communicate directly with one another. All messages
    are routed through the collaboration bus.
    """

    def __init__(
        self,
    ) -> None:
        self._handlers: dict[
            str,
            AgentMessageHandler,
        ] = {}

    def register(
        self,
        *,
        agent: str,
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
                message=(f"No handler registered for agent " f"'{message.recipient}'."),
            )

        return await handler.handle_message(
            message=message,
        )
