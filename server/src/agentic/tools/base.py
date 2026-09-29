"""
Tool base class.

Every tool in this package (document/, messaging/, search_engine/,
retrieval.py) subclasses this. Kept deliberately minimal — name,
description, and a single async execute() — matching the project's
"plain, auditable code paths" preference over a heavier tool-calling
framework.

Read-only vs. side-effecting is NOT distinguished by the type system
here on purpose. A side-effecting action is its own tool (e.g.
messaging/email.py's EmailSendTool, separate from the read-only
EmailTool), listed in GATED_TOOLS so an agent's call to it pauses for
human approval, and it refuses to run without an approval token its
verifier accepts for the exact payload (messaging/base.py, GatedMCPTool).
RBACService (check_action) authorizes the resulting action.

All tools in this package are process-lifetime singletons, built
once at startup (see runtime/factories/tools.py). Any per-request
data a tool needs (DB session, RBAC-resolved document ACL) is read at
execute()-time — a session factory opened fresh per call, ACL read
from request_context — never held as instance state, and
never a parameter of execute() itself if it's security-sensitive
(see retrieval.py's docstring for why).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict


class ToolParams(BaseModel):
    """
    Base for a tool's model-facing parameters.

    One schema serves three purposes: it is rendered into the agent's
    prompt (ToolRegistry.describe()), it validates and bounds every call
    before the tool runs (ToolExecutionService), and its validation
    errors become the short, model-readable reason fed back to the agent.
    Unknown parameters are rejected, never ignored.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class Tool(ABC):
    """
    Abstract base for all agent-callable tools.
    """

    name: str
    description: str

    # The parameters an agent may pass to execute(). None means the tool
    # is not callable by an agent at all (it is used server-side only):
    # it is left out of every tool catalog and ToolExecutionService
    # refuses to run it.
    params_model: ClassVar[type[ToolParams] | None] = None

    @abstractmethod
    async def execute(self, *args: Any, **kwargs: Any) -> str:
        """
        Run the tool and return a string result suitable for
        inclusion in an LLM prompt.

        Each tool declares its own keyword arguments; `*args: Any,
        **kwargs: Any` is the signature mypy accepts any override of.
        Tools are always invoked by keyword (ToolExecutionService).

        A gated tool (GATED_TOOLS) also takes an ``approval_token``
        keyword, which only the approval resume path supplies (never the
        model: params_model forbids it); without a valid one it refuses.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
