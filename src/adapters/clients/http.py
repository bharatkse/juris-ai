"""
Shared asynchronous HTTP client.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, NoReturn

import httpx

from adapters.observability.logger import get_logger
from core.exceptions.client import (
    ClientAuthenticationError,
    ClientAuthorizationError,
    ClientConnectionError,
    ClientProviderError,
    ClientRateLimitError,
    ClientResponseError,
    ClientTimeoutError,
)

log = get_logger(__name__)


class AsyncHTTPClient:
    """
    Shared asynchronous HTTP client.

    Provides common HTTP operations and translates transport-level
    exceptions into application exceptions.
    """

    _DEFAULT_TIMEOUT: Final = httpx.Timeout(
        connect=5.0,
        read=30.0,
        write=30.0,
        pool=5.0,
    )

    _DEFAULT_LIMITS: Final = httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
    )

    def __init__(
        self,
        *,
        base_url: str,
        headers: Mapping[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=dict(headers or {}),
            timeout=timeout or self._DEFAULT_TIMEOUT,
            limits=self._DEFAULT_LIMITS,
            http2=True,
        )

    async def request(
        self,
        method: str,
        path: str = "",
        *,
        params: Mapping[str, object] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        """
        Perform an HTTP request.
        """

        log.debug(
            "Sending %s request to '%s'.",
            method,
            path,
        )

        try:
            response = await self._client.request(
                method=method,
                url=path,
                params=params,
                json=json,
            )

            response.raise_for_status()

            log.debug(
                "%s request to '%s' completed with status %d.",
                method,
                path,
                response.status_code,
            )

            return response

        except Exception as exc:
            log.exception(
                "%s request to '%s' failed.",
                method,
                path,
            )

            self._raise_client_exception(exc)

    async def get(
        self,
        path: str = "",
        *,
        params: Mapping[str, object] | None = None,
    ) -> httpx.Response:
        """
        Perform an HTTP GET request.
        """

        return await self.request("GET", path, params=params)

    async def post(
        self,
        path: str = "",
        *,
        json: Mapping[str, Any] | None = None,
    ) -> httpx.Response:
        """
        Perform an HTTP POST request.
        """

        return await self.request("POST", path, json=json)

    async def get_json(
        self,
        path: str = "",
        *,
        params: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        """
        Perform an HTTP GET request and return JSON.
        """

        response = await self.get(path, params=params)

        try:
            payload = response.json()

        except ValueError as exc:
            log.exception(
                "Invalid JSON response from '%s'.",
                path,
            )

            raise ClientResponseError(
                message="The provider returned an invalid JSON response.",
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ClientResponseError(
                message="Expected a JSON object response.",
            )

        return payload

    async def post_json(
        self,
        path: str = "",
        *,
        json: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Perform an HTTP POST request and return JSON.
        """

        response = await self.post(path, json=json)

        try:
            payload = response.json()

        except ValueError as exc:
            log.exception(
                "Invalid JSON response from '%s'.",
                path,
            )

            raise ClientResponseError(
                message="The provider returned an invalid JSON response.",
            ) from exc

        if not isinstance(
            payload,
            dict,
        ):
            raise ClientResponseError(
                message="Expected a JSON object response.",
            )

        return payload

    async def close(
        self,
    ) -> None:
        """
        Close the underlying HTTP client.
        """

        log.debug(
            "Closing HTTP client.",
        )

        await self._client.aclose()

    async def __aenter__(
        self,
    ) -> AsyncHTTPClient:
        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        tb,
    ) -> None:
        await self.close()

    @staticmethod
    def _raise_client_exception(
        exc: Exception,
    ) -> NoReturn:
        """
        Translate HTTP exceptions into application exceptions.
        """

        if isinstance(
            exc,
            httpx.TimeoutException,
        ):
            raise ClientTimeoutError(
                message="The request timed out.",
            ) from exc

        if isinstance(
            exc,
            httpx.ConnectError,
        ):
            raise ClientConnectionError(
                message="Unable to connect to the external service.",
            ) from exc

        if isinstance(
            exc,
            httpx.HTTPStatusError,
        ):
            status = exc.response.status_code

            if status == 401:
                raise ClientAuthenticationError(
                    message="Authentication failed.",
                ) from exc

            if status == 403:
                raise ClientAuthorizationError(
                    message="Authorization failed.",
                ) from exc

            if status == 429:
                raise ClientRateLimitError(
                    message="Rate limit exceeded.",
                ) from exc

            raise ClientProviderError(
                message=f"Provider returned HTTP {status}.",
            ) from exc

        if isinstance(
            exc,
            httpx.HTTPError,
        ):
            raise ClientProviderError(
                message="HTTP request failed.",
            ) from exc

        raise ClientResponseError(
            message="Unexpected response received from the external service.",
        ) from exc
