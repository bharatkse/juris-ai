from __future__ import annotations

from pydantic import Field

from config.base import BaseAppSettings


class AgentPolicySettings(BaseAppSettings):
    """
    Feature flags gating what DEFAULT_AGENT_POLICIES grants by default,
    and the plan size limit.

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

    # Grants the messaging tools (email, slack to read; email_send,
    # slack_post to send) to the legal and contract agents. Default OFF:
    # sending is a different class of capability from research, needs
    # the Gmail/Slack MCP servers configured (config/llm.py), and every
    # send still pauses for the user's own approval (GATED_TOOLS).
    ENABLE_MESSAGING_TOOLS: bool = False

    # Most steps one execution plan may have (review A7). Each step is a
    # full agent turn, so this bounds one request's LLM calls. A plan over
    # the limit isn't run; the user is asked to split the request.
    # Default: agentic/planning/validator.py::DEFAULT_MAX_PLAN_STEPS.
    PLAN_MAX_STEPS: int = Field(default=6, ge=1)
