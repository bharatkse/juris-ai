"""
Tests for AgentDecisionValidator.

These tests intentionally construct AgentDecision with Pydantic's
model_construct() so the validator can be tested independently from the
nested payload schemas.

The validator's responsibility is:
    1. dispatch by decision type
    2. require the correct payload
    3. reject unexpected payloads
    4. return the same decision instance

Nested payload validation belongs to AgentDecision/Pydantic and is therefore
not exercised by these tests.
"""

from __future__ import annotations

import pytest

from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision
from agentic.decisions.validator import (
    AgentDecisionValidationError,
    AgentDecisionValidator,
)


@pytest.fixture
def validator() -> AgentDecisionValidator:
    return AgentDecisionValidator()


def make_decision(
    decision_type: AgentDecisionType,
    **payloads: object,
) -> AgentDecision:
    """
    Construct an AgentDecision without invoking nested Pydantic validation.

    The validator tests need arbitrary sentinel payload objects. Passing
    object() through normal AgentDecision(...) is invalid because fields such
    as tool_call/delegation/user_input/failure have concrete Pydantic models.
    """
    return AgentDecision.model_construct(
        decision_type=decision_type,
        final_response=payloads.get("final_response"),
        tool_call=payloads.get("tool_call"),
        delegation=payloads.get("delegation"),
        user_input=payloads.get("user_input"),
        failure=payloads.get("failure"),
    )


class TestAgentDecisionValidator:
    """Tests for AgentDecisionValidator."""

    @pytest.mark.parametrize(
        ("decision_type", "payload"),
        [
            (
                AgentDecisionType.FINAL,
                {"final_response": "The answer is ready."},
            ),
            (
                AgentDecisionType.TOOL_CALL,
                {"tool_call": object()},
            ),
            (
                AgentDecisionType.DELEGATE,
                {"delegation": object()},
            ),
            (
                AgentDecisionType.NEED_INPUT,
                {"user_input": object()},
            ),
            (
                AgentDecisionType.FAIL,
                {"failure": object()},
            ),
        ],
    )
    def test_valid_decision_is_returned_unchanged(
        self,
        validator: AgentDecisionValidator,
        decision_type: AgentDecisionType,
        payload: dict[str, object],
    ) -> None:
        decision = make_decision(decision_type, **payload)

        result = validator.validate(decision)

        assert result is decision

    @pytest.mark.parametrize(
        "value",
        [None, "", " ", "   \t\n"],
    )
    def test_final_requires_non_blank_response(
        self,
        validator: AgentDecisionValidator,
        value: str | None,
    ) -> None:
        decision = make_decision(
            AgentDecisionType.FINAL,
            final_response=value,
        )

        with pytest.raises(
            AgentDecisionValidationError,
            match="FINAL decision requires final_response",
        ):
            validator.validate(decision)

    @pytest.mark.parametrize(
        ("decision_type", "payload_name", "message"),
        [
            (
                AgentDecisionType.TOOL_CALL,
                "tool_call",
                "TOOL_CALL decision requires tool_call",
            ),
            (
                AgentDecisionType.DELEGATE,
                "delegation",
                "DELEGATE decision requires delegation",
            ),
            (
                AgentDecisionType.NEED_INPUT,
                "user_input",
                "NEED_INPUT decision requires user_input",
            ),
            (
                AgentDecisionType.FAIL,
                "failure",
                "FAIL decision requires failure",
            ),
        ],
    )
    def test_payload_decisions_require_payload(
        self,
        validator: AgentDecisionValidator,
        decision_type: AgentDecisionType,
        payload_name: str,
        message: str,
    ) -> None:
        decision = make_decision(
            decision_type,
            **{payload_name: None},
        )

        with pytest.raises(
            AgentDecisionValidationError,
            match=message,
        ):
            validator.validate(decision)

    @pytest.mark.parametrize(
        ("decision_type", "allowed", "unexpected"),
        [
            (
                AgentDecisionType.FINAL,
                "final_response",
                "tool_call",
            ),
            (
                AgentDecisionType.TOOL_CALL,
                "tool_call",
                "final_response",
            ),
            (
                AgentDecisionType.DELEGATE,
                "delegation",
                "tool_call",
            ),
            (
                AgentDecisionType.NEED_INPUT,
                "user_input",
                "delegation",
            ),
            (
                AgentDecisionType.FAIL,
                "failure",
                "final_response",
            ),
        ],
    )
    def test_rejects_unexpected_payload(
        self,
        validator: AgentDecisionValidator,
        decision_type: AgentDecisionType,
        allowed: str,
        unexpected: str,
    ) -> None:
        payload = {
            allowed: ("valid response" if allowed == "final_response" else object()),
            unexpected: ("unexpected response" if unexpected == "final_response" else object()),
        }

        decision = make_decision(decision_type, **payload)

        with pytest.raises(
            AgentDecisionValidationError,
            match=rf"{decision_type} decision contains unexpected payload",
        ):
            validator.validate(decision)

    @pytest.mark.parametrize(
        "decision_type",
        list(AgentDecisionType),
    )
    def test_rejects_decision_with_multiple_payloads(
        self,
        validator: AgentDecisionValidator,
        decision_type: AgentDecisionType,
    ) -> None:
        decision = make_decision(
            decision_type,
            final_response="response",
            tool_call=object(),
            delegation=object(),
            user_input=object(),
            failure=object(),
        )

        with pytest.raises(
            AgentDecisionValidationError,
            match="contains unexpected payload",
        ):
            validator.validate(decision)

    def test_final_rejects_all_other_payloads(
        self,
        validator: AgentDecisionValidator,
    ) -> None:
        decision = make_decision(
            AgentDecisionType.FINAL,
            final_response="valid response",
            tool_call=object(),
            delegation=object(),
            user_input=object(),
            failure=object(),
        )

        with pytest.raises(AgentDecisionValidationError) as exc_info:
            validator.validate(decision)

        message = str(exc_info.value)

        assert "tool_call" in message
        assert "delegation" in message
        assert "user_input" in message
        assert "failure" in message

    def test_tool_call_rejects_all_other_payloads(
        self,
        validator: AgentDecisionValidator,
    ) -> None:
        decision = make_decision(
            AgentDecisionType.TOOL_CALL,
            tool_call=object(),
            final_response="unexpected",
            delegation=object(),
            user_input=object(),
            failure=object(),
        )

        with pytest.raises(AgentDecisionValidationError) as exc_info:
            validator.validate(decision)

        message = str(exc_info.value)

        assert "final_response" in message
        assert "delegation" in message
        assert "user_input" in message
        assert "failure" in message

    def test_delegation_rejects_all_other_payloads(
        self,
        validator: AgentDecisionValidator,
    ) -> None:
        decision = make_decision(
            AgentDecisionType.DELEGATE,
            delegation=object(),
            final_response="unexpected",
            tool_call=object(),
            user_input=object(),
            failure=object(),
        )

        with pytest.raises(AgentDecisionValidationError) as exc_info:
            validator.validate(decision)

        message = str(exc_info.value)

        assert "final_response" in message
        assert "tool_call" in message
        assert "user_input" in message
        assert "failure" in message

    def test_user_input_rejects_all_other_payloads(
        self,
        validator: AgentDecisionValidator,
    ) -> None:
        decision = make_decision(
            AgentDecisionType.NEED_INPUT,
            user_input=object(),
            final_response="unexpected",
            tool_call=object(),
            delegation=object(),
            failure=object(),
        )

        with pytest.raises(AgentDecisionValidationError) as exc_info:
            validator.validate(decision)

        message = str(exc_info.value)

        assert "final_response" in message
        assert "tool_call" in message
        assert "delegation" in message
        assert "failure" in message

    def test_failure_rejects_all_other_payloads(
        self,
        validator: AgentDecisionValidator,
    ) -> None:
        decision = make_decision(
            AgentDecisionType.FAIL,
            failure=object(),
            final_response="unexpected",
            tool_call=object(),
            delegation=object(),
            user_input=object(),
        )

        with pytest.raises(AgentDecisionValidationError) as exc_info:
            validator.validate(decision)

        message = str(exc_info.value)

        assert "final_response" in message
        assert "tool_call" in message
        assert "delegation" in message
        assert "user_input" in message

    def test_validator_is_stateless(
        self,
        validator: AgentDecisionValidator,
    ) -> None:
        first = make_decision(
            AgentDecisionType.FINAL,
            final_response="first",
        )
        second = make_decision(
            AgentDecisionType.FINAL,
            final_response="second",
        )

        assert validator.validate(first) is first
        assert validator.validate(second) is second

    def test_validator_can_be_shared_between_calls(
        self,
        validator: AgentDecisionValidator,
    ) -> None:
        valid = make_decision(
            AgentDecisionType.FINAL,
            final_response="valid",
        )
        invalid = make_decision(
            AgentDecisionType.FINAL,
            final_response="",
        )

        assert validator.validate(valid) is valid

        with pytest.raises(AgentDecisionValidationError):
            validator.validate(invalid)

        assert validator.validate(valid) is valid
