"""
Tool base class.

Every tool in this package (document/, messaging/, search_engine/,
retrieval.py) subclasses this. Kept deliberately minimal — name,
description, and a single async execute() — matching the project's
"plain, auditable code paths" preference over a heavier tool-calling
framework.

Read-only vs. side-effecting is NOT distinguished by the type system
here on purpose: that distinction is enforced by RBACService
(check_action) and, for side-effecting actions, by the approval
lifecycle — not by the Tool class itself. See messaging/email.py and
messaging/slack.py for how send/post methods sit outside execute()
and require an approval_token, precisely so a plain agent tool-loop
can't reach them unchecked.

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

        Tools with additional gated methods (e.g. EmailTool.send,
        SlackTool.post) intentionally do NOT route those through
        execute() — execute() is the surface reachable from an
        ordinary agent tool-loop; gated actions require an explicit,
        separate call with an approval token.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
