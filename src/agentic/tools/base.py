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
from typing import Any


class Tool(ABC):
    """
    Abstract base for all agent-callable tools.
    """

    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs: Any) -> str:
        """
        Run the tool and return a string result suitable for
        inclusion in an LLM prompt.

        Tools with additional gated methods (e.g. EmailTool.send,
        SlackTool.post) intentionally do NOT route those through
        execute() — execute() is the surface reachable from an
        ordinary agent tool-loop; gated actions require an explicit,
        separate call with an approval token.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
