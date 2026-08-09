"""
Application-wide constants.
Never put secrets here — those belong in config.py / .env.
"""

from __future__ import annotations

from http import HTTPStatus

# ------------------------------------------------------------------
# Error codes (API-level, stable contracts)
# ------------------------------------------------------------------
ERROR_INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
ERROR_DOMAIN = "DOMAIN_ERROR"
ERROR_PERSISTENCE = "PERSISTENCE_ERROR"
ERROR_UNHANDLED = "UNHANDLED_EXCEPTION"
ERROR_BAD_REQUEST = "BAD_REQUEST"
ERROR_UNPROCESSABLE_ENTITY = "UNPROCESSABLE_ENTITY"
ERROR_UNAUTHORIZED = "UNAUTHORIZED"
ERROR_FORBIDDEN = "FORBIDDEN"
ERROR_VALIDATION = "VALIDATION_ERROR"
ERROR_NOT_FOUND = "RESOURCE_NOT_FOUND"
ERROR_CONFLICT = "RESOURCE_CONFLICT"
ERROR_CONFIGURATION = "CONFIGURATION_ERROR"
ERROR_EXTERNAL_SERVICE = "EXTERNAL_SERVICE_ERROR"
ERROR_CACHE = "CACHE_ERROR"
ERROR_STORAGE = "STORAGE_ERROR"
ERROR_MESSAGE_QUEUE = "MESSAGE_QUEUE_ERROR"
ERROR_AI = "AI_ERROR"
ERROR_INFRASTRUCTURE = "INFRASTRUCTURE_ERROR"


# Planning and AI-related errors
ERROR_PLANNING = "PLANNING_ERROR"
ERROR_INTENT_ANALYSIS = "INTENT_ANALYSIS_ERROR"
ERROR_PLAN_GENERATION = "PLAN_GENERATION_ERROR"
ERROR_PLAN_VALIDATION = "PLAN_VALIDATION_ERROR"

# Execution and orchestration errors
ERROR_EXECUTION = "EXECUTION_ERROR"
ERROR_STRATEGY = "STRATEGY_ERROR"
ERROR_STEP_EXECUTION = "STEP_EXECUTION_ERROR"
ERROR_COLLABORATION = "COLLABORATION_ERROR"

# Registry and agent/tool errors
ERROR_REGISTRY = "REGISTRY_ERROR"
ERROR_AGENT_REGISTRATION = "AGENT_REGISTRATION_ERROR"
ERROR_AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
ERROR_TOOL_REGISTRATION = "TOOL_REGISTRATION_ERROR"
ERROR_TOOL_NOT_FOUND = "TOOL_NOT_FOUND"

# Agent-specific errors
ERROR_AGENT = "AGENT_ERROR"
ERROR_AGENT_EXECUTION = "AGENT_EXECUTION_ERROR"
ERROR_AGENT_CAPABILITY = "AGENT_CAPABILITY_ERROR"
ERROR_AGENT_COLLABORATION = "AGENT_COLLABORATION_ERROR"

# Tool-specific errors
ERROR_TOOL = "TOOL_ERROR"
ERROR_TOOL_EXECUTION = "TOOL_EXECUTION_ERROR"
ERROR_TOOL_VALIDATION = "TOOL_VALIDATION_ERROR"
ERROR_TOOL_CONFIGURATION = "TOOL_CONFIGURATION_ERROR"

# LLM-specific errors
ERROR_LLM = "LLM_ERROR"
ERROR_LLM_PROVIDER = "LLM_PROVIDER_ERROR"
ERROR_LLM_TIMEOUT = "LLM_TIMEOUT"
ERROR_LLM_RESPONSE = "LLM_RESPONSE_ERROR"
ERROR_LLM_STRUCTURED_OUTPUT = "LLM_STRUCTURED_OUTPUT_ERROR"

# Orchestration errors
ERROR_ORCHESTRATION = "ORCHESTRATION_ERROR"

# Aggregation errors
ERROR_AGGREGATION_FAILED = "AGGREGATION_FAILED"

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

# Test DB Configuration
TEST_DB_URL = "sqlite+aiosqlite:///./pytests.db"
