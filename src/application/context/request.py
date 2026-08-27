"""
Application request context.

Carries request-scoped values that may be needed across the application
and agentic execution flow.

The context is stored in a ContextVar because application components and
tools are created once and reused across requests. Request-specific values
must therefore never be captured in constructors.

ContextVar is asyncio-task-scoped, so concurrent requests receive their
own context without leaking values between requests.

Typical usage:

    with bind_request_context(
        request_id=request_id,
        conversation_id=conversation_id,
        trace_id=trace_id,
        allowed_document_ids=allowed_document_ids,
    ):
        await agent.run(...)

ACL-scoped tools can then call:

    context = get_request_context()
    allowed_document_ids = context.allowed_document_ids
"""

from __future__ import annotations

from collections.abc import Iterator
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from uuid import uuid4

from core.models.response import AIUsageModel, MetadataModel


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

    # AuthorizationService resolves these IDs for the current user.
    # None means that no document restriction was supplied.
    allowed_document_ids: set[str] | None = None

    # Mutable during a request so LLM/tool usage can be accumulated.
    ai: AIUsageModel | None = None

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


def bind_request_context(
    *,
    request_id: str | None = None,
    conversation_id: str | None = None,
    trace_id: str | None = None,
    allowed_document_ids: set[str] | None = None,
    ai: AIUsageModel | None = None,
) -> Iterator[RequestContext]:
    """
    Bind a request context for the duration of a block.

    The previous context is restored automatically when the block exits,
    including when an exception is raised.

    Example:

        allowed_document_ids = (
            await authorization_service.get_allowed_document_ids(
                user_id=current_user.id,
            )
        )

        with bind_request_context(
            request_id=request_id,
            conversation_id=conversation_id,
            trace_id=trace_id,
            allowed_document_ids=allowed_document_ids,
        ) as context:
            await agent.run(...)
    """

    context = RequestContext(
        request_id=request_id or str(uuid4()),
        conversation_id=conversation_id,
        trace_id=trace_id,
        allowed_document_ids=allowed_document_ids,
        ai=ai,
    )

    token: Token[RequestContext | None] = _request_context.set(context)

    try:
        yield context

    finally:
        _request_context.reset(token)
