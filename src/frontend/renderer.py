"""
Frontend template rendering helpers.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(
    directory=Path(__file__).parent / "templates",
)


def render(
    *,
    request: Request,
    template: str,
    **context: object,
) -> HTMLResponse:
    """
    Render a frontend template.
    """

    return templates.TemplateResponse(
        request=request,
        name=template,
        context={
            "request": request,
            **context,
        },
    )
