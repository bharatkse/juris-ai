"""
Authorization facade.

Provides the application-facing authorization boundary for
request-level capability authorization and concrete action
authorization.

Authorization is intentionally separated from:
- approval policy,
- approval persistence,
- approval lifecycle,
- action execution.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from adapters.persistence.sqlalchemy.repositories.library import LibraryRepository
from application.authorization.capability.protocols import CapabilityAnalyzerProtocol
from application.authorization.rbac.execute_gate import RBACExecuteGate
from application.authorization.rbac.resolver import RBACService
from core.dto.agent_action import AgentActionResponseDTO
from core.dto.authorization import (
    ApplicationAuthorizationRequestDTO,
    AuthorizationResultDTO,
)
from core.dto.capability import CapabilityAnalysisDTO
from core.exceptions.authorization import AuthorizationError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class AuthorizationService:
    """
    Application-facing authorization facade.

    Responsibilities:
    - analyze requested capabilities,
    - authorize application-level capabilities,
    - authorize concrete persisted AgentActions.

    This service does not:
    - create AgentActions,
    - evaluate approval policy,
    - create approvals,
    - validate approvals,
    - manage approval lifecycle,
    - execute actions.
    """

    def __init__(
        self,
        *,
        capability_analyzer: CapabilityAnalyzerProtocol,
        rbac: RBACService,
        execute_gate: RBACExecuteGate,
        session_factory: Callable[[], AsyncSession],
    ) -> None:
        self._capability_analyzer = capability_analyzer
        self._rbac = rbac
        self._execute_gate = execute_gate
        # Takes a session FACTORY, not a bound session: this service is
        # a process-lifetime singleton (wiring/factories/authorization.py),
        # reused across every concurrent request, so it cannot hold one
        # AsyncSession for its whole lifetime -- same reasoning, same
        # pattern as DatabaseAgentPolicyProvider (agentic/policy/
        # agent_policy.py) and the library/case-law tools.
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Request-level authorization
    # ------------------------------------------------------------------

    def authorize_request(
        self,
        *,
        user_id: str,
        message: str,
    ) -> CapabilityAnalysisDTO:
        """
        Analyze and authorize the capabilities requested by the user.

        This happens before planning.

        It answers:

            "Is this user allowed to request these capabilities?"

        It does not create or execute an action.
        """

        analysis = self._capability_analyzer.analyze(
            message,
        )

        if not analysis.has_capabilities:
            return analysis

        request = ApplicationAuthorizationRequestDTO(
            user_id=user_id,
            capabilities=analysis.action_types,
        )

        if not self._rbac.check_intent(
            request,
        ):
            raise AuthorizationError(
                "User is not authorized for the requested capabilities.",
            )

        return analysis

    # ------------------------------------------------------------------
    # Concrete action authorization
    # ------------------------------------------------------------------

    def authorize_action(
        self,
        *,
        user_id: str,
        action: AgentActionResponseDTO,
    ) -> AuthorizationResultDTO:
        """
        Authorize a concrete persisted AgentAction.

        This is the final RBAC authorization boundary before
        action execution.

        Approval decisions are intentionally not handled here.

        Returns:
            AuthorizationResultDTO containing the authorization
            decision and reason.
        """

        request = action.to_authorization_request(
            user_id=user_id,
        )

        return self._execute_gate.authorize(
            request,
        )

    async def get_allowed_library_ids(
        self,
        *,
        user_id: str,
    ) -> set[str] | None:
        """
        Resolve the current user's allowed Library (uploaded-file) IDs
        for the request -- real per-user ownership, not a placeholder.

        Ownership is transitive: Library has no direct user_id column,
        only conversation_id -> Conversation.user_id (see Library's
        model docstring and LibraryRepository.list_owned_ids(), the
        actual query). No new tenant table or column was needed --
        Conversation.user_id already exists and is already NOT NULL.

        Returns the set of Library ids this user owns. An empty set
        (not None) when the user owns none -- that is a real,
        meaningful "nothing," never treated as "no restriction."
        Returning None here would mean unrestricted access and is
        reserved for a genuine future admin/superuser bypass, which
        does not exist yet -- this method never returns it today.
        """

        async with self._session_factory() as session:
            repository = LibraryRepository(session=session)

            return await repository.list_owned_ids(user_id=user_id)
