"""
Default agent policy seeding.

Populates agent_policies on startup so DatabaseAgentPolicyProvider
always has a row to resolve for every registered agent -- without
this, every agent execution raises AgentPolicyNotFoundError (this was
true before this table existed too: AGENT_POLICIES was an empty dict,
so every real request crashed at AgentExecution.start()).

_build_default_agent_policies() is the reviewable source of truth for
what each agent may do -- change it here, not in the database. One
grant (legal's web_research) is settings-gated rather than
hardcoded -- see its inline comment. seed_default_agent_policies() is
idempotent (upsert), safe to call on every startup.
"""

from __future__ import annotations

from adapters.observability.logger import get_logger
from adapters.persistence.sqlalchemy.repositories.agent_policy import (
    AgentPolicyRepository,
)
from adapters.persistence.sqlalchemy.session import session_factory
from config.settings import get_settings

logger = get_logger(__name__)


# Tools that actually exist today (agentic/tools/*, confirmed by each
# Tool subclass's `name` attribute) -- not every tool is granted to
# every agent:
#   retriever        agentic/tools/retrieval.py       RAG search over indexed docs
#   web_research      .../search_engine/web_research.py general web search
#   case_law_search   .../search_engine/case_law_search.py case-law-specific search
#   parser            agentic/tools/library/parser.py   parse an uploaded document
#   library_lookup    agentic/tools/library/file_lookup.py look up a library document
#   slack, email      agentic/tools/messaging/*         send a message/notification
#
# slack/email are deliberately NOT granted to either agent by default:
# sending a message is a different class of capability from read-only
# research/retrieval, and granting it should be a deliberate product
# decision, not a side effect of unblocking the empty-policy crash.
#
# legal's "retriever" + "case_law_search" are unconditional full
# defaults -- both are read-only research tools with real usage behind
# them. "web_research" is deliberately NOT a hardcoded default: it's a
# broad, open-internet capability with no production track record (the
# policy-enforcement path that makes this grant meaningful was only
# fixed this session), so it's gated behind
# settings.agent_policy.ENABLE_WEB_RESEARCH_FOR_LEGAL (default False,
# see config/agent_policy.py) rather than assumed safe by default.
#
# FLAGGED FOR REVIEW: this is a real, first-cut guess at what each
# agent needs, not derived from any specification. Change freely.
def _build_default_agent_policies() -> dict[str, list[str]]:
    settings = get_settings()

    legal_tools = ["retriever", "case_law_search"]
    if settings.agent_policy.ENABLE_WEB_RESEARCH_FOR_LEGAL:
        legal_tools.append("web_research")

    return {
        "legal": legal_tools,
        "contract": ["retriever", "parser", "library_lookup"],
    }


async def seed_default_agent_policies() -> None:
    """
    Upsert the default agent policies. Idempotent -- safe on every
    startup. Recomputed on each call (rather than a module-level
    constant) so it reflects the current
    settings.agent_policy.ENABLE_WEB_RESEARCH_FOR_LEGAL value.
    """

    default_agent_policies = _build_default_agent_policies()

    async with session_factory() as session:
        repository = AgentPolicyRepository(session=session)

        for agent_id, allowed_tools in default_agent_policies.items():
            await repository.upsert(
                agent_id=agent_id,
                allowed_tools=allowed_tools,
            )

        await session.commit()

    logger.info(
        "Seeded default agent policies.",
        extra={"agent_ids": list(default_agent_policies)},
    )
