"""
Agent decision validation.
"""

from __future__ import annotations

from typing import final

from agentic.decisions.decision import AgentDecisionType
from agentic.decisions.schemas import AgentDecision


class AgentDecisionValidationError(ValueError):
    """
    Raised when an agent decision does not match its declared type.
    """


@final
class AgentDecisionValidator:
    """
    Validate the semantic shape of an AgentDecision.

    The validator is stateless and safe to share across concurrent
    execution requests.
    """

    def validate(
        self,
        decision: AgentDecision,
    ) -> AgentDecision:
        """
        Validate and return the supplied decision.

        Raises:
            AgentDecisionValidationError:
                If the decision is semantically invalid.
        """

        validators = {
            AgentDecisionType.FINAL: self._validate_final,
            AgentDecisionType.TOOL_CALL: self._validate_tool_call,
            AgentDecisionType.DELEGATE: self._validate_delegation,
            AgentDecisionType.NEED_INPUT: self._validate_user_input,
            AgentDecisionType.FAIL: self._validate_failure,
        }

        validator = validators.get(decision.decision_type)

        if validator is None:
            raise AgentDecisionValidationError(
                f"Unsupported decision type: {decision.decision_type}",
            )

        validator(decision)

        return decision

    @staticmethod
    def _validate_final(
        decision: AgentDecision,
    ) -> None:
        if not decision.final_response or not decision.final_response.strip():
            raise AgentDecisionValidationError(
                "FINAL decision requires final_response.",
            )

        AgentDecisionValidator._reject_other_payloads(
            decision=decision,
            allowed="final_response",
        )

    @staticmethod
    def _validate_tool_call(
        decision: AgentDecision,
    ) -> None:
        if decision.tool_call is None:
            raise AgentDecisionValidationError(
                "TOOL_CALL decision requires tool_call.",
            )

        AgentDecisionValidator._reject_other_payloads(
            decision=decision,
            allowed="tool_call",
        )

    @staticmethod
    def _validate_delegation(
        decision: AgentDecision,
    ) -> None:
        if decision.delegation is None:
            raise AgentDecisionValidationError(
                "DELEGATE decision requires delegation.",
            )

        AgentDecisionValidator._reject_other_payloads(
            decision=decision,
            allowed="delegation",
        )

    @staticmethod
    def _validate_user_input(
        decision: AgentDecision,
    ) -> None:
        if decision.user_input is None:
            raise AgentDecisionValidationError(
                "NEED_INPUT decision requires user_input.",
            )

        AgentDecisionValidator._reject_other_payloads(
            decision=decision,
            allowed="user_input",
        )

    @staticmethod
    def _validate_failure(
        decision: AgentDecision,
    ) -> None:
        if decision.failure is None:
            raise AgentDecisionValidationError(
                "FAIL decision requires failure.",
            )

        AgentDecisionValidator._reject_other_payloads(
            decision=decision,
            allowed="failure",
        )

    @staticmethod
    def _reject_other_payloads(
        *,
        decision: AgentDecision,
        allowed: str,
    ) -> None:
        payloads = {
            "final_response": decision.final_response,
            "tool_call": decision.tool_call,
            "delegation": decision.delegation,
            "user_input": decision.user_input,
            "failure": decision.failure,
        }

        unexpected = [
            name for name, value in payloads.items() if name != allowed and value is not None
        ]

        if unexpected:
            raise AgentDecisionValidationError(
                f"{decision.decision_type} decision contains "
                f"unexpected payload(s): {', '.join(unexpected)}.",
            )
