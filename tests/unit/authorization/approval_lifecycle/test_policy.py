import pytest

from src.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from src.core.dto.action import ActionRequestDTO
from src.core.enums import ActionTypeEnum, ApprovalDecisionEnum


@pytest.fixture
def policy() -> ApprovalLifecyclePolicy:
    return ApprovalLifecyclePolicy()


def create_action(
    action: ActionTypeEnum,
) -> ActionRequestDTO:
    return ActionRequestDTO(
        tool_name="test-tool",
        action=action,
        arguments={},
        reason="Test action.",
    )


def test_send_requires_approval(
    policy: ApprovalLifecyclePolicy,
) -> None:
    result = policy.evaluate(
        create_action(ActionTypeEnum.SEND),
    )

    assert result.decision == (ApprovalDecisionEnum.REQUIRE_APPROVAL)

    assert result.requires_approval is True


@pytest.mark.parametrize(
    "action",
    [
        ActionTypeEnum.READ,
        ActionTypeEnum.ANALYZE,
        ActionTypeEnum.GENERATE,
        ActionTypeEnum.UPDATE,
        ActionTypeEnum.DELETE,
    ],
)
def test_non_send_action_does_not_require_approval(
    policy: ApprovalLifecyclePolicy,
    action: ActionTypeEnum,
) -> None:
    result = policy.evaluate(
        create_action(action),
    )

    assert result.decision == ApprovalDecisionEnum.ALLOW
    assert result.requires_approval is False
