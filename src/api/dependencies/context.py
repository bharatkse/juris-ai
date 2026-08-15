"""
Request Context dependencies.
"""

from typing import cast

from fastapi import Request

from src.core.context import RequestContext


def get_request_context(request: Request) -> RequestContext:
    return cast(RequestContext, request.state.context)
