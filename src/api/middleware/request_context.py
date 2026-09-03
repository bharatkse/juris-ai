"""
Request context middleware.
"""

from starlette.middleware.base import BaseHTTPMiddleware

from application.context.request import bind_request_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request,
        call_next,
    ):
        with bind_request_context(
            request_id=str(
                getattr(request.state, "request_id", None)
                or request.scope.get("x-request-id")
                or "",
            ),
            conversation_id=getattr(request.state, "conversation_id", None),
            trace_id=getattr(request.state, "trace_id", None),
        ) as context:
            request.state.context = context
            response = await call_next(request)

        response.headers["X-Request-ID"] = str(
            request.state.context.request_id,
        )

        return response
