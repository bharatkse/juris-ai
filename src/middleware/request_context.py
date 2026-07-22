"""
Request context middleware.
"""

from starlette.middleware.base import BaseHTTPMiddleware

from src.core.context import RequestContext


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.context = RequestContext()

        response = await call_next(request)

        response.headers["X-Request-ID"] = request.state.context.request_id

        return response
