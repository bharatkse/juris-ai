from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest

from application.authorization.approval_lifecycle.policy import ApprovalLifecyclePolicy
from application.authorization.capability.analyzer import DefaultCapabilityAnalyzer
from application.authorization.capability.classifier import TFIDFCapabilityClassifier
from application.authorization.rbac.policy import RBACPolicy
from application.authorization.rbac.resolver import RBACService
from application.authorization.service import AuthorizationService
from core.enums import ActionTypeEnum


@pytest.fixture
def approval_policy() -> ApprovalLifecyclePolicy:
    """
    Create an approval lifecycle policy.
    """

    return ApprovalLifecyclePolicy()


@pytest.fixture
def mock_classifier() -> MagicMock:
    """
    Return a mocked capability classifier.
    """

    return MagicMock()


@pytest.fixture
def analyzer(
    mock_classifier: MagicMock,
) -> DefaultCapabilityAnalyzer:
    """
    Return a capability analyzer with an injected classifier.
    """

    return DefaultCapabilityAnalyzer(
        classifier=mock_classifier,
    )


@pytest.fixture
def examples() -> dict[ActionTypeEnum, tuple[str, ...]]:
    """
    Return capability examples used by the classifier tests.
    """

    return {
        ActionTypeEnum.SEND: (
            "send an email",
            "send a message",
            "email the document",
        ),
        ActionTypeEnum.READ: (
            "read the document",
            "view the document",
            "get document details",
        ),
    }


@pytest.fixture
def classifier(
    examples: dict[ActionTypeEnum, tuple[str, ...]],
) -> TFIDFCapabilityClassifier:
    """
    Create a capability classifier.
    """

    return TFIDFCapabilityClassifier(
        examples=examples,
        threshold=0.35,
    )


@pytest.fixture
def policy() -> RBACPolicy:
    """Return the default RBAC policy."""
    return RBACPolicy.default()


@pytest.fixture
def mock_policy() -> Mock:
    """Return a mocked RBAC policy."""
    return Mock(spec=RBACPolicy)


@pytest.fixture
def rbac_service(mock_policy: Mock) -> RBACService:
    """Return an RBAC service using the mocked policy."""
    return RBACService(policy=mock_policy)


@pytest.fixture
def mock_capability_analyzer() -> MagicMock:
    """
    Provide a mocked capability analyzer.
    """

    return MagicMock()


@pytest.fixture
def mock_rbac() -> MagicMock:
    """
    Provide a mocked RBAC service.
    """

    return MagicMock()


@pytest.fixture
def mock_execute_gate() -> MagicMock:
    """
    Provide a mocked RBAC execute gate.
    """

    return MagicMock()


@pytest.fixture
def authorization_service(
    mock_capability_analyzer: MagicMock,
    mock_rbac: MagicMock,
    mock_execute_gate: MagicMock,
) -> AuthorizationService:
    """
    Build the authorization service.
    """

    return AuthorizationService(
        capability_analyzer=mock_capability_analyzer,
        rbac=mock_rbac,
        execute_gate=mock_execute_gate,
    )
