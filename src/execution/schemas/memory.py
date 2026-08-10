"""
Execution memory.

Shared mutable memory for a single execution.

Acts as the runtime blackboard that enables agents to exchange
intermediate artifacts during execution.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExecutionMemorySchema(BaseModel):
    """
    Shared execution memory.

    The Executor creates one ExecutionMemory instance per request
    and shares it with all participating agents.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    artifacts: dict[str, Any] = Field(
        default_factory=dict,
    )

    entities: dict[str, Any] = Field(
        default_factory=dict,
    )

    def put_artifact(
        self,
        *,
        key: str,
        value: Any,
    ) -> None:
        """
        Store an execution artifact.
        """

        self.artifacts[key] = value

    def get_artifact(
        self,
        *,
        key: str,
    ) -> Any | None:
        """
        Retrieve an execution artifact.
        """

        return self.artifacts.get(
            key,
        )

    def put_entity(
        self,
        *,
        key: str,
        value: Any,
    ) -> None:
        """
        Store an extracted entity.
        """

        self.entities[key] = value

    def get_entity(
        self,
        *,
        key: str,
    ) -> Any | None:
        """
        Retrieve an extracted entity.
        """

        return self.entities.get(
            key,
        )

    def has_artifact(
        self,
        *,
        key: str,
    ) -> bool:
        """
        Determine whether an artifact exists.
        """

        return key in self.artifacts

    def has_entity(
        self,
        *,
        key: str,
    ) -> bool:
        """
        Determine whether an entity exists.
        """

        return key in self.entities

    def clear(self) -> None:
        """
        Remove all stored execution data.
        """

        self.artifacts.clear()
        self.entities.clear()
