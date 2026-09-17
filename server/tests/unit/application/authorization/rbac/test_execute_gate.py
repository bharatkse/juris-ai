"""
Unit tests for execute-time RBAC authorization gate.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from application.authorization.rbac.execute_gate import RBACExecuteGate
from core.dto.authorization import AuthorizationResultDTO
from core.enums import ActionTypeEnum, AuthorizationDecisionEnum
from tests.builders.application.authorization import build_authorization_request


def test_authorize_returns_allow_when_rbac_allows_action() -> None:
    """
    It should return ALLOW when RBAC permits the action.
    """

    request = build_authorization_request()

    rbac = MagicMock()
    rbac.check_action.return_value = True

    gate = RBACExecuteGate(
        rbac=rbac,
    )

    result = gate.authorize(
        request,
    )

    assert isinstance(
        result,
        AuthorizationResultDTO,
    )

    assert result.decision == AuthorizationDecisionEnum.ALLOW
    assert result.reason == "Action is authorized."

    rbac.check_action.assert_called_once_with(
        request,
    )


def test_authorize_returns_deny_when_rbac_denies_action() -> None:
    """
    It should return DENY when RBAC rejects the action.
    """

    request = build_authorization_request()

    rbac = MagicMock()
    rbac.check_action.return_value = False

    gate = RBACExecuteGate(
        rbac=rbac,
    )

    result = gate.authorize(
        request,
    )

    assert isinstance(
        result,
        AuthorizationResultDTO,
    )

    assert result.decision == AuthorizationDecisionEnum.DENY
    assert result.reason == "Action is not authorized."

    rbac.check_action.assert_called_once_with(
        request,
    )


def test_authorize_passes_exact_request_to_rbac() -> None:
    """
    It should pass the exact authorization request to RBAC.
    """

    request = build_authorization_request()

    rbac = MagicMock()
    rbac.check_action.return_value = True

    gate = RBACExecuteGate(
        rbac=rbac,
    )

    gate.authorize(
        request,
    )

    called_request = rbac.check_action.call_args.args[0]

    assert called_request is request


def test_authorize_calls_rbac_only_once() -> None:
    """
    It should evaluate RBAC exactly once per authorization request.
    """

    request = build_authorization_request()

    rbac = MagicMock()
    rbac.check_action.return_value = True

    gate = RBACExecuteGate(
        rbac=rbac,
    )

    gate.authorize(
        request,
    )

    rbac.check_action.assert_called_once()


def test_authorize_returns_allow_without_modifying_request() -> None:
    """
    It should not modify the authorization request when access is allowed.
    """

    request = build_authorization_request()

    rbac = MagicMock()
    rbac.check_action.return_value = True

    gate = RBACExecuteGate(
        rbac=rbac,
    )

    gate.authorize(
        request,
    )

    assert request.user_id == "user_" + "a" * 32
    assert request.agent_id == "agent_" + "b" * 32
    assert request.tool_name == "send_email"
    assert request.action_type == ActionTypeEnum.SEND
    assert request.resource_id == "resource_" + "c" * 32


def test_authorize_returns_deny_without_modifying_request() -> None:
    """
    It should not modify the authorization request when access is denied.
    """

    request = build_authorization_request()

    rbac = MagicMock()
    rbac.check_action.return_value = False

    gate = RBACExecuteGate(
        rbac=rbac,
    )

    gate.authorize(
        request,
    )

    assert request.user_id == "user_" + "a" * 32
    assert request.agent_id == "agent_" + "b" * 32
    assert request.tool_name == "send_email"
    assert request.action_type == ActionTypeEnum.SEND
    assert request.resource_id == "resource_" + "c" * 32
