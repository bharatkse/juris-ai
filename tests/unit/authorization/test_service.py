from unittest.mock import Mock

import pytest

from src.authorization.rbac.policy import RBACPolicy
from src.authorization.service import AuthorizationService
from src.core.dto.action import ActionRequestDTO
from src.core.dto.authorization import AuthorizationResultDTO
from src.core.enums import ActionTypeEnum, AuthorizationDecisionEnum
from src.core.exceptions.authorization import AuthorizationError


def test_authorize_allows_authorized_action() -> None:
    policy = Mock(spec=RBACPolicy)
    policy.evaluate.return_value = AuthorizationResultDTO(
        decision=AuthorizationDecisionEnum.ALLOW,
        reason="Application and agent authorization granted.",
    )

    service = AuthorizationService(policy=policy)

    action = ActionRequestDTO(
        tool_name="email",
        action=ActionTypeEnum.SEND,
        agent_id="agent-123",
        agent_name="Legal Agent",
        arguments={"to": "client@example.com"},
    )

    service.authorize(
        user_id="user-123",
        action=action,
    )

    policy.evaluate.assert_called_once()


def test_authorize_raises_error_when_action_is_denied() -> None:
    policy = Mock(spec=RBACPolicy)
    policy.evaluate.return_value = AuthorizationResultDTO(
        decision=AuthorizationDecisionEnum.DENY,
        reason="User is not authorized to perform this operation.",
    )

    service = AuthorizationService(policy=policy)

    action = ActionRequestDTO(
        tool_name="email",
        action=ActionTypeEnum.SEND,
        agent_id="agent-123",
        agent_name="Legal Agent",
        arguments={"to": "client@example.com"},
    )
    with pytest.raises(
        AuthorizationError,
        match="User is not authorized to perform this operation.",
    ):
        service.authorize(
            user_id="user-123",
            action=action,
        )

    policy.evaluate.assert_called_once()


def test_authorize_builds_authorization_request() -> None:
    policy = Mock(spec=RBACPolicy)
    policy.evaluate.return_value = AuthorizationResultDTO(
        decision=AuthorizationDecisionEnum.ALLOW,
        reason="Application and agent authorization granted.",
    )

    service = AuthorizationService(policy=policy)

    action = ActionRequestDTO(
        tool_name="email",
        action=ActionTypeEnum.SEND,
        arguments={"to": "client@example.com"},
        reason="Send approved client communication.",
        resource_id="client-123",
        agent_id="agent-123",
        agent_name="Legal Agent",
    )

    service.authorize(
        user_id="user-123",
        action=action,
    )

    request = policy.evaluate.call_args.args[0]

    assert request.user_id == "user-123"
    assert request.agent_id == "agent-123"
    assert request.agent_name == "Legal Agent"
    assert request.tool_name == "email"
    assert request.action == ActionTypeEnum.SEND
    assert request.resource_id == "client-123"
