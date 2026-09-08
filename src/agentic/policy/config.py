"""
Static agent policy configuration.

This module contains declarative agent-policy configuration only.

Policy evaluation is implemented by:
    - AgentPolicyProvider
    - AgentPolicyGuard
    - ToolPermissionGuard

This module must not contain runtime execution logic.
"""

from __future__ import annotations

from agentic.policy.schemas import AgentPolicy

AGENT_POLICIES: dict[str, AgentPolicy] = {}
"""
Configured policies keyed by agent ID.

Policies are intentionally immutable at the value level through the
frozen AgentPolicy dataclass.

Agents without an explicitly configured policy are rejected by
StaticAgentPolicyProvider rather than receiving implicit permissions.
"""
