"""
Unit tests for RBACService.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from application.authorization.rbac.resolver import RBACService
from core.dto.authorization import (
    ApplicationAuthorizationRequestDTO,
    AuthorizationRequestDTO,
)
from core.enums import ActionTypeEnum


class TestRBACServiceInit:
    """Tests for RBACService initialization."""

    def test_service_stores_policy(
        self,
        policy: Mock,
    ) -> None:
        """Service should store the supplied policy."""
        service = RBACService(policy=policy)

        assert service._policy is policy


class TestCheckIntent:
    """Tests for RBACService.check_intent."""

    def test_all_capabilities_allowed(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
    ) -> None:
        """Intent should be allowed when every capability is permitted."""
        request = ApplicationAuthorizationRequestDTO(
            user_id="user-1",
            capabilities=[
                ActionTypeEnum.READ,
                ActionTypeEnum.ANALYZE,
            ],
        )

        mock_policy.capability_allowed.return_value = True

        result = rbac_service.check_intent(request)

        assert result is True

        assert mock_policy.capability_allowed.call_count == 2
        mock_policy.capability_allowed.assert_any_call(
            user_id="user-1",
            capability=ActionTypeEnum.READ,
        )
        mock_policy.capability_allowed.assert_any_call(
            user_id="user-1",
            capability=ActionTypeEnum.ANALYZE,
        )

    def test_denied_capability_denies_intent(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
    ) -> None:
        """Intent should be denied when any capability is not permitted."""
        request = ApplicationAuthorizationRequestDTO(
            user_id="user-1",
            capabilities=[
                ActionTypeEnum.READ,
                ActionTypeEnum.ANALYZE,
            ],
        )

        mock_policy.capability_allowed.side_effect = [
            True,
            False,
        ]

        result = rbac_service.check_intent(request)

        assert result is False

    def test_check_intent_stops_after_first_denied_capability(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
    ) -> None:
        """Intent checking should short-circuit after a denied capability."""
        request = ApplicationAuthorizationRequestDTO(
            user_id="user-1",
            capabilities=[
                ActionTypeEnum.READ,
                ActionTypeEnum.ANALYZE,
                ActionTypeEnum.GENERATE,
            ],
        )

        mock_policy.capability_allowed.side_effect = [
            True,
            False,
            True,
        ]

        result = rbac_service.check_intent(request)

        assert result is False

        assert mock_policy.capability_allowed.call_count == 2

    def test_first_denied_capability_is_denied(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
    ) -> None:
        """Intent should immediately fail when the first capability is denied."""
        request = ApplicationAuthorizationRequestDTO(
            user_id="user-1",
            capabilities=[
                ActionTypeEnum.ANALYZE,
                ActionTypeEnum.READ,
            ],
        )

        mock_policy.capability_allowed.return_value = False

        result = rbac_service.check_intent(request)

        assert result is False

        mock_policy.capability_allowed.assert_called_once_with(
            user_id="user-1",
            capability=ActionTypeEnum.ANALYZE,
        )

    def test_empty_capabilities_are_allowed(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
    ) -> None:
        """An empty capability list results in all() returning True."""
        request = ApplicationAuthorizationRequestDTO(
            user_id="user-1",
            capabilities=[],
        )

        result = rbac_service.check_intent(request)

        assert result is True

        mock_policy.capability_allowed.assert_not_called()


class TestCheckAction:
    """Tests for RBACService.check_action."""

    @pytest.fixture
    def authorization_request(self) -> AuthorizationRequestDTO:
        """Return a representative authorization request."""
        return AuthorizationRequestDTO(
            user_id="user-1",
            agent_id="legal",
            tool_name="retriever",
            action_type=ActionTypeEnum.READ,
        )

    def test_action_allowed_when_user_and_agent_are_authorized(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
        authorization_request: AuthorizationRequestDTO,
    ) -> None:
        """Action should be allowed when both checks succeed."""
        mock_policy.user_action_allowed.return_value = True
        mock_policy.agent_action_allowed.return_value = True

        result = rbac_service.check_action(authorization_request)

        assert result is True

        mock_policy.user_action_allowed.assert_called_once_with(
            user_id="user-1",
            action=ActionTypeEnum.READ,
        )

        mock_policy.agent_action_allowed.assert_called_once_with(
            agent_id="legal",
            tool_name="retriever",
            action=ActionTypeEnum.READ,
        )

    def test_action_denied_when_user_is_not_authorized(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
        authorization_request: AuthorizationRequestDTO,
    ) -> None:
        """Action should be denied when the user lacks permission."""
        mock_policy.user_action_allowed.return_value = False

        result = rbac_service.check_action(authorization_request)

        assert result is False

        mock_policy.user_action_allowed.assert_called_once_with(
            user_id="user-1",
            action=ActionTypeEnum.READ,
        )

        # Agent permission must not be evaluated when user permission fails.
        mock_policy.agent_action_allowed.assert_not_called()

    def test_action_denied_when_agent_is_not_authorized(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
        authorization_request: AuthorizationRequestDTO,
    ) -> None:
        """Action should be denied when the agent/tool lacks permission."""
        mock_policy.user_action_allowed.return_value = True
        mock_policy.agent_action_allowed.return_value = False

        result = rbac_service.check_action(authorization_request)

        assert result is False

        mock_policy.user_action_allowed.assert_called_once_with(
            user_id="user-1",
            action=ActionTypeEnum.READ,
        )

        mock_policy.agent_action_allowed.assert_called_once_with(
            agent_id="legal",
            tool_name="retriever",
            action=ActionTypeEnum.READ,
        )

    def test_user_permission_is_checked_before_agent_permission(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
        authorization_request: AuthorizationRequestDTO,
    ) -> None:
        """User authorization should be evaluated before agent authorization."""
        mock_policy.user_action_allowed.return_value = True
        mock_policy.agent_action_allowed.return_value = True

        rbac_service.check_action(authorization_request)

        assert mock_policy.method_calls[0][0] == "user_action_allowed"
        assert mock_policy.method_calls[1][0] == "agent_action_allowed"

    @pytest.mark.parametrize(
        "action_type",
        [
            ActionTypeEnum.READ,
            ActionTypeEnum.ANALYZE,
            ActionTypeEnum.GENERATE,
        ],
    )
    def test_action_type_is_forwarded_to_both_checks(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
        action_type: ActionTypeEnum,
    ) -> None:
        """The requested action type should be used for both authorization checks."""
        request = AuthorizationRequestDTO(
            user_id="user-1",
            agent_id="legal",
            tool_name="retriever",
            action_type=action_type,
        )

        mock_policy.user_action_allowed.return_value = True
        mock_policy.agent_action_allowed.return_value = True

        result = rbac_service.check_action(request)

        assert result is True

        mock_policy.user_action_allowed.assert_called_once_with(
            user_id="user-1",
            action=action_type,
        )

        mock_policy.agent_action_allowed.assert_called_once_with(
            agent_id="legal",
            tool_name="retriever",
            action=action_type,
        )

    def test_tool_name_is_forwarded_to_agent_permission_check(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
    ) -> None:
        """The request tool name should be forwarded unchanged."""
        request = AuthorizationRequestDTO(
            user_id="user-1",
            agent_id="legal",
            tool_name="document_search",
            action_type=ActionTypeEnum.READ,
        )

        mock_policy.user_action_allowed.return_value = True
        mock_policy.agent_action_allowed.return_value = True

        result = rbac_service.check_action(request)

        assert result is True

        mock_policy.agent_action_allowed.assert_called_once_with(
            agent_id="legal",
            tool_name="document_search",
            action=ActionTypeEnum.READ,
        )

    def test_none_tool_name_is_forwarded_to_policy(
        self,
        rbac_service: RBACService,
        mock_policy: Mock,
    ) -> None:
        """A missing tool name should be delegated to the policy."""
        request = AuthorizationRequestDTO(
            user_id="user-1",
            agent_id="legal",
            tool_name=None,
            action_type=ActionTypeEnum.READ,
        )

        mock_policy.user_action_allowed.return_value = True
        mock_policy.agent_action_allowed.return_value = False

        result = rbac_service.check_action(request)

        assert result is False

        mock_policy.agent_action_allowed.assert_called_once_with(
            agent_id="legal",
            tool_name=None,
            action=ActionTypeEnum.READ,
        )
