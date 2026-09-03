"""
Authorization dependencies.

bind_document_acl runs AFTER get_current_user (api/dependencies/auth.py)
in FastAPI's dependency graph — it depends on it directly, so it's only
reachable once the JWT has been decoded and the user resolved. This is
why ACL resolution can't happen in RequestContextMiddleware: middleware
runs before any Depends() chain, this dependency runs after
get_current_user specifically.

Must be declared explicitly on every route whose handler eventually
invokes an ACL-scoped tool (retriever, document_lookup,
case_law_search's contracts scope) — e.g.:

    @router.post("/chat")
    async def chat(
        current_user: User = Depends(get_current_user),
        _: None = Depends(bind_document_acl),
        ...
    ):
        ...

There is no way to enforce "this route must include bind_document_acl"
at the type-checker level — FastAPI dependencies are opt-in per route.
The failure mode this guards against (a route someone forgot to add
this to) is caught at RUNTIME instead, loudly: any ACL-scoped tool that
executes without this having run raises RuntimeError the moment it
reads allowed_document_ids (see application/context/request.py), rather
than silently proceeding as if unrestricted. Missing the dependency is
still a bug to fix, but it fails safe (500, logged, visible) instead of
failing open (a real information-disclosure incident).
"""

from __future__ import annotations

from fastapi import Depends

from adapters.persistence.sqlalchemy.models.user import User
from api.dependencies.auth import get_current_user
from application.authorization.service import AuthorizationService
from application.context.request import get_request_context
from runtime.factories.authorization import create_authorization


def get_authorization_service() -> AuthorizationService:
    """
    Build the application authorization service.

    This resolves the real AuthorizationService created by the existing runtime
    authorization factory rather than accidentally returning an AuthenticationService.
    """

    return create_authorization()


async def bind_document_acl(
    current_user: User = Depends(get_current_user),
    authorization_service: AuthorizationService = Depends(get_authorization_service),
) -> None:
    """
    Resolve the current user's document ACL and write it onto the
    already-bound request context (from RequestContextMiddleware).

    This dependency exists for its side effect; routes depend on it with
    `_: None = Depends(...)`.
    """

    allowed_document_ids = authorization_service.get_allowed_document_ids(
        user_id=current_user.id,
    )

    get_request_context().allowed_document_ids = allowed_document_ids
