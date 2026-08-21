from src.core.dto.action import ActionRequestDTO
from src.core.dto.authorization import AuthorizationRequestDTO
from src.core.enums import ActionTypeEnum


def test_action_request_defaults_arguments_and_reason() -> None:
    request = ActionRequestDTO(
        tool_name="email",
        action=ActionTypeEnum.SEND,
    )

    assert request.arguments == {}
    assert request.reason == ""


def test_action_request_contains_concrete_action() -> None:
    request = ActionRequestDTO(
        tool_name="email",
        action=ActionTypeEnum.SEND,
        arguments={
            "to": "client@example.com",
            "subject": "Contract",
        },
        reason="Send the contract to the client.",
    )

    assert request.tool_name == "email"
    assert request.action == ActionTypeEnum.SEND
    assert request.arguments["to"] == "client@example.com"
    assert request.reason == "Send the contract to the client."


def test_action_request_is_immutable() -> None:
    request = ActionRequestDTO(
        tool_name="email",
        action=ActionTypeEnum.SEND,
    )

    try:
        request.tool_name = "other"
    except AttributeError:
        pass
    else:
        raise AssertionError("ActionRequestDTO must be immutable")


def test_action_request_creates_authorization_request() -> None:
    request = ActionRequestDTO(
        tool_name="email",
        action=ActionTypeEnum.SEND,
        arguments={
            "to": "client@example.com",
        },
    )

    authorization_request = request.to_authorization_request(
        user_id="user-123",
    )

    assert authorization_request == AuthorizationRequestDTO(
        user_id="user-123",
        action=ActionTypeEnum.SEND,
    )
