"""
Unit tests for RBACService.

A user's permissions come from their role (RolePermissionProvider, the
database in production); an agent's from RBACPolicy.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from application.authorization.rbac.resolver import RBACService
from core.dto.authorization import (
    ApplicationAuthorizationRequestDTO,
    AuthorizationRequestDTO,
)
from core.enums import ActionTypeEnum

USER = "user_" + "a" * 32
RESEARCH = frozenset({ActionTypeEnum.READ, ActionTypeEnum.ANALYZE, ActionTypeEnum.GENERATE})


def _intent(*capabilities: ActionTypeEnum) -> ApplicationAuthorizationRequestDTO:
    return ApplicationAuthorizationRequestDTO(user_id=USER, capabilities=list(capabilities))


class TestCheckIntent:
    async def test_allowed_when_the_role_grants_every_capability(
        self, rbac_service: RBACService, mock_role_permissions: MagicMock
    ) -> None:
        mock_role_permissions.permissions_for.return_value = RESEARCH

        assert await rbac_service.check_intent(_intent(ActionTypeEnum.READ, ActionTypeEnum.ANALYZE))

        mock_role_permissions.permissions_for.assert_awaited_once_with(user_id=USER)

    async def test_denied_when_any_capability_is_missing(
        self, rbac_service: RBACService, mock_role_permissions: MagicMock
    ) -> None:
        mock_role_permissions.permissions_for.return_value = RESEARCH

        assert not await rbac_service.check_intent(
            _intent(ActionTypeEnum.READ, ActionTypeEnum.SEND)
        )

    async def test_denied_when_the_role_grants_nothing(
        self, rbac_service: RBACService, mock_role_permissions: MagicMock
    ) -> None:
        mock_role_permissions.permissions_for.return_value = frozenset()

        assert not await rbac_service.check_intent(_intent(ActionTypeEnum.READ))

    async def test_empty_capabilities_are_allowed_without_a_lookup(
        self, rbac_service: RBACService, mock_role_permissions: MagicMock
    ) -> None:
        assert await rbac_service.check_intent(_intent())

        mock_role_permissions.permissions_for.assert_not_awaited()


class TestCheckAction:
    @pytest.fixture
    def send_request(self) -> AuthorizationRequestDTO:
        return AuthorizationRequestDTO(
            user_id=USER,
            agent_id="legal",
            tool_name="email_send",
            action_type=ActionTypeEnum.SEND,
        )

    async def test_allowed_when_role_and_agent_both_permit(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
        mock_role_permissions: MagicMock,
        send_request: AuthorizationRequestDTO,
    ) -> None:
        mock_role_permissions.permissions_for.return_value = RESEARCH | {ActionTypeEnum.SEND}
        mock_policy.agent_action_allowed.return_value = True

        assert await rbac_service.check_action(send_request)

        mock_policy.agent_action_allowed.assert_called_once_with(
            agent_id="legal",
            tool_name="email_send",
            action=ActionTypeEnum.SEND,
        )

    async def test_denied_when_the_role_lacks_the_action(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
        mock_role_permissions: MagicMock,
        send_request: AuthorizationRequestDTO,
    ) -> None:
        mock_role_permissions.permissions_for.return_value = RESEARCH

        assert not await rbac_service.check_action(send_request)

        mock_policy.agent_action_allowed.assert_not_called()

    async def test_denied_when_the_agent_lacks_the_action(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
        mock_role_permissions: MagicMock,
        send_request: AuthorizationRequestDTO,
    ) -> None:
        mock_role_permissions.permissions_for.return_value = RESEARCH | {ActionTypeEnum.SEND}
        mock_policy.agent_action_allowed.return_value = False

        assert not await rbac_service.check_action(send_request)
