"""
Application-wide constants.
Never put secrets here — those belong in config.py / .env.
"""

from __future__ import annotations

from http import HTTPStatus

# ------------------------------------------------------------------
# Error codes (API-level, stable contracts)
# ------------------------------------------------------------------
ERROR_INTERVAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
ERROR_DOMAIN = "DOMAIN_ERROR"
ERROR_NOT_FOUND = "NOT_FOUND"
ERROR_PERSISTENCE = "PERSISTENCE_ERROR"
ERROR_UNHANDLED = "UNHANDLED_EXCEPTION"
ERROR_BAD_REQUEST = "BAD_REQUEST"
ERROR_UNPROCESSABLE_ENTITY = "UNPROCESSABLE_ENTITY"
ERROR_CONFLICT = "CONFLICT"
ERROR_UNAUTHORIZED = "UNAUTHORIZED"
ERROR_FORBIDDEN = "FORBIDDEN"

# ------------------------------------------------------------------
# Common HTTP statuses (optional but explicit)
# ------------------------------------------------------------------

HTTP_400_BAD_REQUEST = HTTPStatus.BAD_REQUEST
HTTP_404_NOT_FOUND = HTTPStatus.NOT_FOUND
HTTP_500_INTERNAL_SERVER_ERROR = HTTPStatus.INTERNAL_SERVER_ERROR
HTTP_200_OK = HTTPStatus.OK
HTTP_201_CREATED = HTTPStatus.CREATED
HTTP_202_ACCEPTED = HTTPStatus.ACCEPTED
HTTP_204_NO_CONTENT = HTTPStatus.NO_CONTENT
HTTP_422_UNPROCESSABLE_ENTITY = HTTPStatus.UNPROCESSABLE_ENTITY
HTTP_409_CONFLICT = HTTPStatus.CONFLICT
HTTP_401_UNAUTHORIZED = HTTPStatus.UNAUTHORIZED
HTTP_403_FORBIDDEN = HTTPStatus.FORBIDDEN

# ------------------------------------------------------------------
# API
# ------------------------------------------------------------------
API_V1_PREFIX = "/api/v1"


# ------------------------------------------------------------------
# Pagination defaults
# ------------------------------------------------------------------
DEFAULT_PAGE_SIZE: int = 10
MAX_PAGE_SIZE: int = 100
MIN_PAGE_SIZE: int = 1
DEFAULT_PAGE = 1

# ------------------------------------------------------------------
# Application defaults
# ------------------------------------------------------------------
DEFAULT_APP_NAME = "Legal AI Assistant"
DEFAULT_APP_VERSION = "1.0.0"

# ── API ───────────────────────────────────────────────────────────────────────
API_VERSION: str = "v1"
API_TITLE: str = "Legal AI API"
API_DESCRIPTION: str = "Juris AI is a modern backend service for AI-powered legal assistance"
HEALTH_ENDPOINT: str = "/health"

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_REQUEST_BODY_MAX_CHARS: int = 500
LOG_RESPONSE_BODY_MAX_CHARS: int = 500

# ── Cache key prefixes ────────────────────────────────────────────────────────
CACHE_PREFIX_SEARCH: str = "search:"
CACHE_PREFIX_GENERATE: str = "generate:"
CACHE_PREFIX_EMBEDDING: str = "embedding:"
CACHE_PREFIX_DOCUMENT: str = "document:"

DEFAULT_CONVERSATION_TITLE: str = "New Conversation"
