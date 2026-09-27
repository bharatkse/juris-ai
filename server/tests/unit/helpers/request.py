from types import SimpleNamespace
from uuid import uuid4

from starlette.requests import Request


def build_http_request() -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [],
            "query_string": b"",
            "server": ("testserver", 80),
            "client": ("testclient", 50000),
            "scheme": "http",
        },
    )

    request.state.context = SimpleNamespace(
        request_id=str(uuid4()),
    )

    return request
