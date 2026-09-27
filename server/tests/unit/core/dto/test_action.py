from core.dto.authorization import AuthorizationRequestDTO
from core.enums import ActionTypeEnum
from tests.builders.agentic.agent import build_agent_action_request_dto


def test_action_request_defaults_arguments_and_reason() -> None:
    request = build_agent_action_request_dto(
        tool_name="email",
        action_type=ActionTypeEnum.SEND,
    )

    assert request.parameters == {}
    assert request.reason == ""


def test_action_request_contains_concrete_action() -> None:
    request = build_agent_action_request_dto(
        tool_name="email",
        action_type=ActionTypeEnum.SEND,
        parameters={
            "to": "client@example.com",
            "subject": "Contract",
        },
        reason="Send the contract to the client.",
    )

    assert request.tool_name == "email"
    assert request.action_type == ActionTypeEnum.SEND
    assert request.parameters["to"] == "client@example.com"
    assert request.reason == "Send the contract to the client."


def test_action_request_is_immutable() -> None:
    request = build_agent_action_request_dto(
        tool_name="email",
        action_type=ActionTypeEnum.SEND,
    )

    try:
        request.tool_name = "other"
    except AttributeError:
        pass
    else:
        raise AssertionError("AgentActionRequestDTO must be immutable")


def test_action_request_creates_authorization_request() -> None:
    request = build_agent_action_request_dto(
        tool_name="email",
        action_type=ActionTypeEnum.SEND,
        parameters={
            "to": "client@example.com",
        },
    )

    authorization_request = request.to_authorization_request(
        user_id="user-123",
    )

    assert authorization_request == AuthorizationRequestDTO(
        user_id="user-123",
        action_type=ActionTypeEnum.SEND,
        agent_id="agent-123",
        tool_name="email",
    )
