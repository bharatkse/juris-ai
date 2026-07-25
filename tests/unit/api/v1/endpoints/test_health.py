"""
Unit tests for health API endpoint.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.api.v1.endpoints.health import health
from src.core.context import RequestContext
from src.core.response import ApiResponse


@pytest.mark.asyncio
async def test_health_returns_application_health() -> None:
    """
    It should return application health information.
    """

    context = RequestContext()

    response = await health(
        context=context,
    )

    assert isinstance(
        response,
        ApiResponse,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
@patch("src.api.v1.endpoints.health.ApiResponse")
async def test_health_builds_expected_response(
    mock_api_response: MagicMock,
) -> None:
    """
    It should build the expected API response.
    """

    context = RequestContext()

    expected_metadata = context.to_metadata()

    with patch.object(
        RequestContext,
        "to_metadata",
        return_value=expected_metadata,
    ) as mock_to_metadata:
        await health(
            context=context,
        )

    from src.api.v1.endpoints.health import settings

    mock_api_response.assert_called_once_with(
        success=True,
        status_code=200,
        data={
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
        },
        metadata=expected_metadata,
    )

    mock_to_metadata.assert_called_once_with()
