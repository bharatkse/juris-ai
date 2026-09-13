from __future__ import annotations

from config.base import BaseAppSettings


class AgentPolicySettings(BaseAppSettings):
    """
    Feature flags gating what DEFAULT_AGENT_POLICIES grants by default.

    Kept separate from the seed data itself (wiring/factories/
    agent_policies.py) so a capability can be toggled via env var
    without editing/redeploying the seed module.
    """

    # web_research was only wired into the live graph-execution path
    # this session (previously dead code behind an always-crashing
    # policy resolution) -- it has no production track record yet.
    # Default OFF for the legal agent until it's been observed under
    # real traffic; flip to True (or grant per-agent directly in
    # DEFAULT_AGENT_POLICIES) once it has.
    ENABLE_WEB_RESEARCH_FOR_LEGAL: bool = False
