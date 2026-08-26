"""
Request context.

Carries per-request values that tools need at execute()-time but that
must NEVER be part of a tool's LLM-facing function-calling schema —
currently just allowed_document_ids (RBAC-resolved document ACL).

Why a ContextVar instead of binding into each tool at construction:
tools are built ONCE at application startup (see composition.py /
factories/tools.py) and reused for the lifetime of the process. A
value baked into a tool's __init__ would be frozen at whichever
request happened to be active when the tool was built — wrong for
every subsequent request, and actively dangerous if it's an ACL,
since it would leak the first requester's permissions onto every
later request's queries.

set_request_context() must be called once per request, before the
agent/tool-calling loop runs (e.g. FastAPI middleware or a dependency
that wraps AuthorizationService.get_allowed_document_ids()). ContextVar
is asyncio-task-scoped, so concurrent requests each see their own
value even though every tool instance is shared.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequestContext:
    allowed_document_ids: set[str] | None


_request_context: ContextVar[RequestContext | None] = ContextVar("_request_context", default=None)


def get_request_context() -> RequestContext:
    """
    Raises if no context has been set — this is intentional. A tool
    reading ACL data with no request context bound is a bug that
    should fail loudly (missing middleware, called outside a request)
    rather than silently defaulting to "no restriction."
    """

    context = _request_context.get()

    if context is None:
        raise RuntimeError(
            "No request context is bound. set_request_context() must be "
            "called before any ACL-scoped tool executes — this is a "
            "wiring bug (missing middleware/dependency), not a runtime "
            "condition to handle gracefully."
        )

    return context


@contextmanager
def bind_request_context(*, allowed_document_ids: set[str] | None):
    """
    Bind request context for the duration of the `with` block. Use in
    middleware/a FastAPI dependency wrapping each request:

        allowed_document_ids = await authorization_service.get_allowed_document_ids(
            user_id=current_user.id,
        )
        with bind_request_context(allowed_document_ids=allowed_document_ids):
            await agent.run(...)
    """

    token = _request_context.set(RequestContext(allowed_document_ids=allowed_document_ids))

    try:
        yield

    finally:
        _request_context.reset(token)
