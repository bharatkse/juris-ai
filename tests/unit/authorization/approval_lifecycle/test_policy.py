"""
Unit tests for human approval policy.
"""

from __future__ import annotations

import pytest

from src.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from src.core.dto.approval import ApprovalPolicyResultDTO
from src.core.enums import ActionTypeEnum, ApprovalPolicyDecisionEnum
from tests.builders.dto import build_agent_action_response_dto


def test_evaluate_requires_approval_for_send_action(
    approval_policy: ApprovalLifecyclePolicy,
) -> None:
    """
    It should require human approval for SEND actions.
    """

    action = build_agent_action_response_dto(
        action_type=ActionTypeEnum.SEND,
    )

    result = approval_policy.evaluate(
        action,
    )

    assert isinstance(
        result,
        ApprovalPolicyResultDTO,
    )

    assert result.decision == ApprovalPolicyDecisionEnum.REQUIRE_APPROVAL

    assert result.reason == ("Action 'send' requires human approval.")


@pytest.mark.parametrize(
    "action_type",
    [action_type for action_type in ActionTypeEnum if action_type != ActionTypeEnum.SEND],
)
def test_evaluate_allows_actions_that_do_not_require_approval(
    approval_policy: ApprovalLifecyclePolicy,
    action_type: ActionTypeEnum,
) -> None:
    """
    It should allow actions that are not configured
    as requiring human approval.
    """

    action = build_agent_action_response_dto(
        action_type=action_type,
    )

    result = approval_policy.evaluate(
        action,
    )

    assert result.decision == ApprovalPolicyDecisionEnum.ALLOW

    assert result.reason == (f"Action '{action_type.value}' " "does not require human approval.")


def test_evaluate_returns_require_approval_only_for_send(
    approval_policy: ApprovalLifecyclePolicy,
) -> None:
    """
    It should restrict approval-required actions to
    the configured approval policy set.
    """

    send_action = build_agent_action_response_dto(
        action_type=ActionTypeEnum.SEND,
    )

    result = approval_policy.evaluate(
        send_action,
    )

    assert result.decision == ApprovalPolicyDecisionEnum.REQUIRE_APPROVAL

    for action_type in ActionTypeEnum:
        if action_type == ActionTypeEnum.SEND:
            continue

        action = build_agent_action_response_dto(
            action_type=action_type,
        )

        result = approval_policy.evaluate(
            action,
        )

        assert result.decision == ApprovalPolicyDecisionEnum.ALLOW
