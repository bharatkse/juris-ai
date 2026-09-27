"""
AI orchestrator composition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.checkpoint.base import BaseCheckpointSaver

from adapters.observability.langsmith import configure_langsmith
from adapters.persistence.sqlalchemy.session import session_factory
from agentic.collaboration.bus import CollaborationBus
from agentic.execution.aggregation.response import ResponseAggregator
from agentic.execution.validation.response import ResponseValidator
from agentic.orchestration.orchestrator import AIOrchestrator
from agentic.tools.messaging.base import DenyAllApprovalVerifier
from application.services.compliance_log import StandaloneComplianceLogWriter
from config.settings import get_settings
from wiring.factories.agents import register_agents
from wiring.factories.authorization import create_authorization
from wiring.factories.clients import create_clients
from wiring.factories.executor import create_executor
from wiring.factories.guardrails import create_output_guardrail_service
from wiring.factories.planner import create_planner
from wiring.factories.registries import create_registries
from wiring.factories.tools import register_tools

if TYPE_CHECKING:
    from wiring.containers import ClientContainer


def create_ai_orchestrator(
    *,
    checkpointer: BaseCheckpointSaver,
    clients: ClientContainer | None = None,
) -> AIOrchestrator:
    """
    Create the AI orchestrator with its runtime dependencies.

    ``clients`` lets the caller build the ClientContainer once and share
    it (main.py's lifespan exposes clients.embedding_provider on
    app.state for user memory, which must reuse the same loaded model
    rather than build a second one). Built here when omitted.
    """

    settings = get_settings()
    configure_langsmith(settings=settings)

    authorization = create_authorization()

    clients = clients or create_clients(settings=settings)
    registries = create_registries()

    collaboration_bus = CollaborationBus()

    register_tools(
        clients=clients,
        registries=registries,
        approval_service=DenyAllApprovalVerifier(),
    )

    register_agents(
        settings=settings,
        clients=clients,
        registries=registries,
        collaboration_bus=collaboration_bus,
    )

    # AIOrchestrator, Executor, and the LangGraph nodes underneath it
    # are all composed once here at process startup and shared across
    # every request (see api/dependencies/chat.py's
    # get_ai_orchestrator: request.app.state.ai_orchestrator) -- none
    # of them has a request-scoped AsyncSession to write compliance
    # log entries through, so every compliance write from this whole
    # tree goes through one shared, self-contained-session writer
    # (same session_factory pattern DatabaseAgentPolicyProvider already
    # uses in agentic/policy/agent_policy.py), not the request session
    # ChatService writes through.
    compliance_log = StandaloneComplianceLogWriter(
        session_factory=session_factory,
    )

    return AIOrchestrator(
        planner=create_planner(clients=clients),
        executor=create_executor(
            registries=registries,
            clients=clients,
            settings=settings,
            checkpointer=checkpointer,
            collaboration_bus=collaboration_bus,
            compliance_log=compliance_log,
        ),
        validator=ResponseValidator(),
        aggregator=ResponseAggregator(),
        authorization=authorization,
        guardrails=create_output_guardrail_service(
            settings=settings,
            cache=clients.cache,
        ),
        compliance_log=compliance_log,
    )
