"""
Unit tests for action fingerprint generation.
"""

from __future__ import annotations

from dataclasses import replace

from application.authorization.approval_lifecycle.fingerprint import (
    create_action_fingerprint,
)
from tests.builders.core.dto import build_agent_action_response_dto


def test_create_action_fingerprint_is_deterministic() -> None:
    """
    It should generate the same fingerprint for the same action.
    """

    action = build_agent_action_response_dto()

    first = create_action_fingerprint(action)
    second = create_action_fingerprint(action)

    assert first == second


def test_create_action_fingerprint_returns_sha256_hex() -> None:
    """
    It should return a SHA-256 hexadecimal fingerprint.
    """

    action = build_agent_action_response_dto()

    fingerprint = create_action_fingerprint(action)

    assert len(fingerprint) == 64
    assert all(character in "0123456789abcdef" for character in fingerprint)


def test_create_action_fingerprint_changes_when_agent_changes() -> None:
    """
    It should generate a different fingerprint when the agent changes.
    """

    action = build_agent_action_response_dto()

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        agent_id="agent_different",
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_changes_when_action_type_changes() -> None:
    """
    It should generate a different fingerprint when the action type changes.
    """

    action = build_agent_action_response_dto()

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        action_type=action.action_type.__class__.AGENT_CALL,
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_changes_when_tool_name_changes() -> None:
    """
    It should generate a different fingerprint when the tool name changes.
    """

    action = build_agent_action_response_dto()

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        tool_name="different_tool",
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_changes_when_target_agent_changes() -> None:
    """
    It should generate a different fingerprint when the target agent changes.
    """

    action = build_agent_action_response_dto(
        target_agent_id="agent-target-1",
    )

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        target_agent_id="agent-target-2",
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_changes_when_resource_type_changes() -> None:
    """
    It should generate a different fingerprint when the resource type changes.
    """

    action = build_agent_action_response_dto(
        resource_type="document",
    )

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        resource_type="conversation",
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_changes_when_resource_id_changes() -> None:
    """
    It should generate a different fingerprint when the resource ID changes.
    """

    action = build_agent_action_response_dto(
        resource_id="document-1",
    )

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        resource_id="document-2",
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_changes_when_parameters_change() -> None:
    """
    It should generate a different fingerprint when parameters change.
    """

    action = build_agent_action_response_dto(
        parameters={
            "recipient": "user@example.com",
        },
    )

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        parameters={
            "recipient": "other@example.com",
        },
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_changes_when_reason_changes() -> None:
    """
    It should generate a different fingerprint when the reason changes.
    """

    action = build_agent_action_response_dto(
        reason="Original reason",
    )

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        reason="Different reason",
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_distinguishes_none_from_value() -> None:
    """
    It should distinguish a missing target agent from a concrete target agent.
    """

    action = build_agent_action_response_dto(
        target_agent_id=None,
    )

    original = create_action_fingerprint(action)

    modified = replace(
        action,
        target_agent_id="agent-target-1",
    )

    changed = create_action_fingerprint(modified)

    assert changed != original


def test_create_action_fingerprint_is_independent_of_parameter_order() -> None:
    """
    It should generate the same fingerprint when parameter
    dictionary ordering differs.
    """

    first = build_agent_action_response_dto(
        parameters={
            "subject": "Hello",
            "recipient": "user@example.com",
        },
    )

    second = build_agent_action_response_dto(
        parameters={
            "recipient": "user@example.com",
            "subject": "Hello",
        },
    )

    assert create_action_fingerprint(first) == create_action_fingerprint(
        second,
    )
