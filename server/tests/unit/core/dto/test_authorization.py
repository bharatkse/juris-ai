from core.dto.authorization import AuthorizationRequestDTO, AuthorizationResultDTO
from core.enums import ActionTypeEnum, AuthorizationDecisionEnum


def test_authorization_request() -> None:
    request = AuthorizationRequestDTO(
        user_id="user-123",
        action_type=ActionTypeEnum.SEND,
        agent_id="agent-123",
    )

    assert request.user_id == "user-123"
    assert request.action_type == ActionTypeEnum.SEND


def test_authorization_result_allow() -> None:
    result = AuthorizationResultDTO(
        decision=AuthorizationDecisionEnum.ALLOW,
        reason="User is authorized to send emails.",
    )

    assert result.decision == AuthorizationDecisionEnum.ALLOW
    assert result.reason == "User is authorized to send emails."


def test_authorization_result_deny() -> None:
    result = AuthorizationResultDTO(
        decision=AuthorizationDecisionEnum.DENY,
        reason="User is not authorized to send emails.",
    )

    assert result.decision == AuthorizationDecisionEnum.DENY
    assert result.reason == "User is not authorized to send emails."
