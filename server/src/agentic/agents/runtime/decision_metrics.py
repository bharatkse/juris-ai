"""
Decision-rejection measurement (review M1).

Counts every agent decision by type and every rejected one by cause, so
the open design questions on the decision schema (A20, A19) and the
planner's step arguments (A17 part 2) can be decided from data. Counts and
names only: no prompt, answer or parameter value is recorded.

Causes:
- invalid_decision: the decision failed AgentDecisionValidator.
- policy_denied_unlisted: a tool the agent's catalog doesn't list (the
  model invented or guessed it).
- policy_denied_listed: a tool the catalog lists but the policy denied
  (should be ~0; anything else is a catalog/policy mismatch).
- parse_failure: the reply couldn't be parsed as a decision (or was empty).
- tool_params_rejected: the tool's params_model rejected the parameters.
- planner_argument: counted in addition to a policy denial or a parameter
  rejection when the rejected tool name or parameter name appears in the
  plan step's arguments (a heuristic attribution to the planner).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from adapters.observability.logger import get_logger
from adapters.observability.metrics import metrics

logger = get_logger(__name__)

RejectionCause = Literal[
    "invalid_decision",
    "policy_denied_unlisted",
    "policy_denied_listed",
    "parse_failure",
    "tool_params_rejected",
]

_PLANNER_ATTRIBUTABLE = frozenset(
    {"policy_denied_unlisted", "policy_denied_listed", "tool_params_rejected"}
)

# Tool names come from the model; log one only if it looks like a name.
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,63}$")


def planner_argument_involved(
    *,
    plan_arguments: Mapping[str, Any] | None,
    tool_name: str | None,
    rejected_parameters: Iterable[str] = (),
) -> bool:
    """
    Whether the rejected tool or parameter came from the plan step's
    arguments: a rejected parameter name is one of their keys, or the
    tool name is one of their (string) values.
    """

    if not plan_arguments:
        return False

    if any(name in plan_arguments for name in rejected_parameters):
        return True

    values = {value for value in plan_arguments.values() if isinstance(value, str)}
    return tool_name is not None and tool_name in values


def record_rejection(
    *,
    agent_id: str,
    execution_id: str,
    attempt: int,
    cause: RejectionCause,
    tool_name: str | None = None,
    rejected_parameters: Iterable[str] = (),
    plan_arguments: Mapping[str, Any] | None = None,
) -> None:
    """Count one rejected decision and log it (names only, never values)."""

    parameters = [name for name in rejected_parameters if _IDENTIFIER.match(name)]
    from_plan = cause in _PLANNER_ATTRIBUTABLE and planner_argument_involved(
        plan_arguments=plan_arguments,
        tool_name=tool_name,
        rejected_parameters=parameters,
    )

    metrics.record_rejected_decision(agent=agent_id, cause=cause)
    if from_plan:
        metrics.record_rejected_decision(agent=agent_id, cause="planner_argument")

    logger.info(
        "Agent decision rejected.",
        extra={
            "operation": "agent_decision_rejected",
            "agent_id": agent_id,
            "execution_id": execution_id,
            "attempt": attempt,
            "cause": cause,
            "tool_name": tool_name if tool_name and _IDENTIFIER.match(tool_name) else None,
            "rejected_parameters": parameters,
            "planner_argument": from_plan,
        },
    )
