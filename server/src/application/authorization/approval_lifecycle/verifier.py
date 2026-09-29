"""
Approval-token verification for gated tools.

A gated tool (email_send, slack_post) receives the approval id as its
approval token and asks ApprovalRecordVerifier whether that approval
covers the exact payload it is about to send. This is the last check
before an external side effect, independent of the resume path that
called the tool: even a caller that reaches the tool some other way
cannot send without a decided approval for that exact payload.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.agent_action import (
    AgentActionRepository,
)
from adapters.persistence.sqlalchemy.repositories.approval import ApprovalRepository
from core.enums import AgentActionStatusEnum, ApprovalStatusEnum

logger = get_logger(__name__)

# Key on AgentAction.result under which the resume path stores the result
# of an approved gated call (HitlResumeService). Its presence means the
# call already ran, so the token is spent.
TOOL_RESULT_KEY = "tool_result"

_APPROVED_STATUSES = frozenset({ApprovalStatusEnum.APPROVED, ApprovalStatusEnum.EDITED})

_SPENT_ACTION_STATUSES = frozenset(
    {
        AgentActionStatusEnum.COMPLETED,
        AgentActionStatusEnum.REJECTED,
        AgentActionStatusEnum.EXPIRED,
    }
)


def approved_parameters(
    *,
    proposed: Mapping[str, Any],
    edited_payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """
    The parameters a human approved: the agent's proposal with the
    reviewer's edits applied on top (an edit may change any subset of the
    fields). Used both to run the approved call and to verify it.
    """

    return {**proposed, **(edited_payload or {})}


class ApprovalRecordVerifier:
    """
    ApprovalTokenVerifier backed by the approvals and agent_actions tables.

    A token is accepted only when all of these hold:
    - it is the id of an approval that was approved or edited,
    - that approval's action is a call to this tool,
    - the payload equals the approved parameters exactly,
    - the action hasn't already run (no stored tool result, not
      completed/rejected/expired) -- a token is single-use.

    Approval expiry is not checked here: it bounds the time to decide
    (ApprovalLifecycleService refuses late decisions), not the time to
    carry out a decision already made, which a retried resume may do
    later.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        # A factory, not a session: gated tools are process-lifetime
        # singletons shared across requests (wiring/factories/tools.py).
        self._session_factory = session_factory

    async def is_approved(
        self,
        *,
        token: str,
        action: str,
        payload: dict[str, object],
    ) -> bool:
        if not token:
            return False

        async with self._session_factory() as session:
            approval = await ApprovalRepository(session=session).get(token)

            if approval is None or approval.status not in _APPROVED_STATUSES:
                return self._deny(token=token, action=action, reason="not an approved approval")

            agent_action = await AgentActionRepository(session=session).get(
                approval.agent_action_id,
            )

            if agent_action is None or agent_action.tool_name != action:
                return self._deny(
                    token=token, action=action, reason="approval is for another action"
                )

            if agent_action.status in _SPENT_ACTION_STATUSES or TOOL_RESULT_KEY in (
                agent_action.result or {}
            ):
                return self._deny(token=token, action=action, reason="approval already used")

            expected = approved_parameters(
                proposed=agent_action.parameters,
                edited_payload=approval.edited_payload,
            )

            if expected != payload:
                return self._deny(
                    token=token, action=action, reason="payload differs from approval"
                )

        return True

    @staticmethod
    def _deny(*, token: str, action: str, reason: str) -> bool:
        logger.warning(
            "Approval token refused for a gated tool.",
            extra={"approval_id": token, "tool_name": action, "reason": reason},
        )
        return False
