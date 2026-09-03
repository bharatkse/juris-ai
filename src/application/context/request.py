"""
Application request context.

Carries request-scoped values that may be needed across the application
and agentic execution flow.

The context is stored in a ContextVar because application components and
tools are created once and reused across requests. Request-specific values
must therefore never be captured in constructors.

ContextVar is asyncio-task-scoped, so concurrent requests receive their
own context without leaking values between requests.

allowed_document_ids has two independent states, not one:

  - Explicitly None: AuthorizationService resolved this user's access
    and determined they have no document restriction (e.g. an
    admin/superuser). Legitimately unrestricted.
  - Never resolved: no authorization step has run yet for this
    request — e.g. RequestContextMiddleware bound the base context
    (request_id/trace_id) before FastAPI even decoded the JWT, and the
    ACL-resolving dependency hasn't run because a route forgot to
    declare it.

Collapsing these into one "None means unrestricted" value would make
a missing `Depends(bind_document_acl)` on some route fail OPEN —
silently exposing every document to every user, with no error,
because the untouched default happens to mean "no restriction". That
is the one failure mode this whole ACL design exists to prevent, so
it must not be reachable by omission. Reading allowed_document_ids
before it has been explicitly set raises, rather than silently
returning None.

Typical usage:

    # Early — request_id/trace_id only, before auth has run:
    with bind_request_context(
        request_id=request_id,
        conversation_id=conversation_id,
        trace_id=trace_id,
    ):
        ...

    # Later — after get_current_user resolves, in a route dependency:
    get_request_context().allowed_document_ids = await (
        authorization_service.get_allowed_document_ids(user_id=current_user.id)
    )

ACL-scoped tools then read:

    allowed_document_ids = get_request_context().allowed_document_ids
    # raises RuntimeError if the line above never ran for this request
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from core.models.response import AIUsageModel, MetadataModel


class _Unset:
    """Sentinel type distinguishing 'never resolved' from 'resolved to None'."""

    def __repr__(self) -> str:
        return "<UNSET>"


_UNSET = _Unset()


@dataclass(slots=True)
class RequestContext:
    """
    Request-scoped application context.

    This object must contain only data belonging to the current request.
    It must never be stored on long-lived singleton services or tools.
    """

    request_id: str = field(
        default_factory=lambda: str(uuid4()),
    )

    conversation_id: str | None = None

    trace_id: str | None = None

    # Mutable during a request so LLM/tool usage can be accumulated.
    ai: AIUsageModel | None = None

    # Private, sentinel-backed — see module docstring for why this
    # isn't a plain `set[str] | None = None` field. Access via the
    # allowed_document_ids property below, not this attribute
    # directly.
    _allowed_document_ids: set[str] | None | Literal[_Unset] = field(default=_UNSET, repr=False)

    @property
    def allowed_document_ids(self) -> set[str] | None:
        if self._allowed_document_ids is _UNSET:
            raise RuntimeError(
                "allowed_document_ids was never resolved for this request. "
                "An ACL-scoped tool executed before the authorization "
                "dependency ran — this is a route wiring bug (a missing "
                "Depends() for ACL resolution), not a runtime condition to "
                "handle gracefully. It must not be treated as 'no "
                "restriction'."
            )

        return self._allowed_document_ids

    @allowed_document_ids.setter
    def allowed_document_ids(self, value: set[str] | None) -> None:
        self._allowed_document_ids = value

    def to_metadata(self) -> dict[str, object]:
        """
        Convert request context into metadata suitable for API responses
        and observability.
        """
        return MetadataModel(
            request_id=self.request_id,
            trace_id=self.trace_id,
            ai=self.ai,
        )


_request_context: ContextVar[RequestContext | None] = ContextVar(
    "request_context",
    default=None,
)


def get_request_context() -> RequestContext:
    """
    Return the current request context.

    Raises:
        RuntimeError:
            If called outside a bound request context.

    Failing loudly is intentional. In particular, an ACL-scoped tool must
    never silently interpret a missing context as unrestricted access.
    """

    context = _request_context.get()

    if context is None:
        raise RuntimeError(
            "No request context is bound. "
            "bind_request_context() must be called before accessing "
            "request-scoped context."
        )

    return context


@contextmanager
def bind_request_context(
    *,
    request_id: str | None = None,
    conversation_id: str | None = None,
    trace_id: str | None = None,
    ai: AIUsageModel | None = None,
) -> Iterator[RequestContext]:
    """
    Bind a request context for the duration of a block.

    Deliberately does NOT accept allowed_document_ids as a parameter —
    it's resolved separately, later in the request lifecycle (after
    authentication), by mutating the yielded/current context's
    allowed_document_ids property. See api/dependencies/authorization.py.

    The previous context is restored automatically when the block exits,
    including when an exception is raised.

    Example (middleware — early, no auth resolved yet):

        with bind_request_context(
            request_id=request_id,
            trace_id=trace_id,
        ) as context:
            response = await call_next(request)
    """

    context = RequestContext(
        request_id=request_id or str(uuid4()),
        conversation_id=conversation_id,
        trace_id=trace_id,
        ai=ai,
    )

    token: Token[RequestContext | None] = _request_context.set(context)

    try:
        yield context

    finally:
        _request_context.reset(token)
