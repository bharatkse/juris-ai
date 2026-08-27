"""
Unit tests for the authorization service.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from application.authorization.service import AuthorizationService
from core.dto.authorization import AuthorizationResultDTO
from core.dto.capability import CapabilityAnalysisDTO
from core.enums import ActionTypeEnum
from core.exceptions.authorization import AuthorizationError
from tests.builders.core.dto import build_agent_action_response_dto


def test_authorize_request_returns_analysis_when_no_capabilities_detected(
    authorization_service: AuthorizationService,
    mock_capability_analyzer: MagicMock,
    mock_rbac: MagicMock,
) -> None:
    """
    It should return the capability analysis without invoking RBAC
    when no capabilities are detected.
    """

    analysis = CapabilityAnalysisDTO(
        action_types=(),
        reason="No supported capability was identified.",
    )

    mock_capability_analyzer.analyze.return_value = analysis

    result = authorization_service.authorize_request(
        user_id="user_123",
        message="Hello, how are you?",
    )

    assert result is analysis
    assert result.action_types == ()
    assert result.has_capabilities is False

    mock_capability_analyzer.analyze.assert_called_once_with(
        "Hello, how are you?",
    )

    mock_rbac.check_intent.assert_not_called()


def test_authorize_request_returns_analysis_when_user_is_authorized(
    authorization_service: AuthorizationService,
    mock_capability_analyzer: MagicMock,
    mock_rbac: MagicMock,
) -> None:
    """
    It should return the capability analysis when RBAC authorizes
    the requested capabilities.
    """

    analysis = CapabilityAnalysisDTO(
        action_types=(ActionTypeEnum.SEND,),
        reason="Detected requested capabilities: send.",
    )

    mock_capability_analyzer.analyze.return_value = analysis
    mock_rbac.check_intent.return_value = True

    result = authorization_service.authorize_request(
        user_id="user_123",
        message="Send the document.",
    )

    assert result is analysis

    mock_capability_analyzer.analyze.assert_called_once_with(
        "Send the document.",
    )

    request = mock_rbac.check_intent.call_args.args[0]

    assert request.user_id == "user_123"
    assert request.capabilities == (ActionTypeEnum.SEND,)


def test_authorize_request_raises_when_user_is_not_authorized(
    authorization_service: AuthorizationService,
    mock_capability_analyzer: MagicMock,
    mock_rbac: MagicMock,
) -> None:
    """
    It should raise AuthorizationError when RBAC denies
    the requested capabilities.
    """

    analysis = CapabilityAnalysisDTO(
        action_types=(ActionTypeEnum.SEND,),
        reason="Detected requested capabilities: send.",
    )

    mock_capability_analyzer.analyze.return_value = analysis
    mock_rbac.check_intent.return_value = False

    with pytest.raises(
        AuthorizationError,
        match="User is not authorized for the requested capabilities.",
    ):
        authorization_service.authorize_request(
            user_id="user_123",
            message="Send the document.",
        )

    mock_capability_analyzer.analyze.assert_called_once_with(
        "Send the document.",
    )

    mock_rbac.check_intent.assert_called_once()


def test_authorize_request_preserves_multiple_capabilities(
    authorization_service: AuthorizationService,
    mock_capability_analyzer: MagicMock,
    mock_rbac: MagicMock,
) -> None:
    """
    It should pass all detected capabilities to the RBAC layer
    in classifier order.
    """

    action_types = (
        ActionTypeEnum.SEND,
        ActionTypeEnum.READ,
    )

    analysis = CapabilityAnalysisDTO(
        action_types=action_types,
        reason="Detected requested capabilities: send, read.",
    )

    mock_capability_analyzer.analyze.return_value = analysis
    mock_rbac.check_intent.return_value = True

    result = authorization_service.authorize_request(
        user_id="user_123",
        message="Read and send the document.",
    )

    assert result.action_types == action_types

    request = mock_rbac.check_intent.call_args.args[0]

    assert request.user_id == "user_123"
    assert request.capabilities == action_types


def test_authorize_action_returns_execute_gate_result(
    authorization_service: AuthorizationService,
    mock_execute_gate: MagicMock,
) -> None:
    """
    It should return the authorization result produced by the
    execute gate.
    """

    action = build_agent_action_response_dto()

    expected_result = MagicMock(
        spec=AuthorizationResultDTO,
    )

    mock_execute_gate.authorize.return_value = expected_result

    result = authorization_service.authorize_action(
        user_id="user_123",
        action=action,
    )

    assert result is expected_result

    mock_execute_gate.authorize.assert_called_once()

    request = mock_execute_gate.authorize.call_args.args[0]

    assert request.user_id == "user_123"
    assert request.agent_id == action.agent_id
    assert request.tool_name == action.tool_name
    assert request.action_type == action.action_type
    assert request.resource_id == action.resource_id


def test_authorize_action_builds_authorization_request_from_action(
    authorization_service: AuthorizationService,
    mock_execute_gate: MagicMock,
) -> None:
    """
    It should derive the authorization request from the concrete
    persisted action.
    """

    action = build_agent_action_response_dto(
        agent_id="agent_123",
        tool_name="send_email",
        resource_type="email",
        resource_id="resource_123",
        action_type=ActionTypeEnum.SEND,
    )

    mock_execute_gate.authorize.return_value = MagicMock(
        spec=AuthorizationResultDTO,
    )

    authorization_service.authorize_action(
        user_id="user_123",
        action=action,
    )

    request = mock_execute_gate.authorize.call_args.args[0]

    assert request.user_id == "user_123"
    assert request.agent_id == "agent_123"
    assert request.tool_name == "send_email"
    assert request.action_type == ActionTypeEnum.SEND
    assert request.resource_id == "resource_123"


def test_authorize_action_propagates_execute_gate_result(
    authorization_service: AuthorizationService,
    mock_execute_gate: MagicMock,
) -> None:
    """
    It should not transform or replace the execute-gate result.
    """

    action = build_agent_action_response_dto()

    expected_result = MagicMock(
        spec=AuthorizationResultDTO,
    )

    mock_execute_gate.authorize.return_value = expected_result

    result = authorization_service.authorize_action(
        user_id="user_123",
        action=action,
    )

    assert result is expected_result


def test_authorize_action_does_not_invoke_capability_analyzer(
    authorization_service: AuthorizationService,
    mock_capability_analyzer: MagicMock,
    mock_execute_gate: MagicMock,
) -> None:
    """
    Concrete action authorization should not perform capability analysis.
    """

    action = build_agent_action_response_dto()

    mock_execute_gate.authorize.return_value = MagicMock(
        spec=AuthorizationResultDTO,
    )

    authorization_service.authorize_action(
        user_id="user_123",
        action=action,
    )

    mock_capability_analyzer.analyze.assert_not_called()


def test_authorize_request_does_not_invoke_execute_gate(
    authorization_service: AuthorizationService,
    mock_capability_analyzer: MagicMock,
    mock_rbac: MagicMock,
    mock_execute_gate: MagicMock,
) -> None:
    """
    Request-level authorization should not authorize a concrete
    executable action.
    """

    analysis = CapabilityAnalysisDTO(
        action_types=(ActionTypeEnum.SEND,),
        reason="Detected requested capabilities: send.",
    )

    mock_capability_analyzer.analyze.return_value = analysis
    mock_rbac.check_intent.return_value = True

    authorization_service.authorize_request(
        user_id="user_123",
        message="Send the document.",
    )

    mock_execute_gate.authorize.assert_not_called()
