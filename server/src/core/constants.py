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
ERROR_PLAN_GENERATION = "PLAN_GENERATION_ERROR"
ERROR_PLAN_VALIDATION = "PLAN_VALIDATION_ERROR"

# Execution and orchestration errors
ERROR_EXECUTION = "EXECUTION_ERROR"
ERROR_STEP_EXECUTION = "STEP_EXECUTION_ERROR"
ERROR_COLLABORATION = "COLLABORATION_ERROR"

# Rate limiting / usage quota errors
ERROR_RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
ERROR_TOKEN_QUOTA_EXCEEDED = "TOKEN_QUOTA_EXCEEDED"

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
HTTP_429_TOO_MANY_REQUESTS = HTTPStatus.TOO_MANY_REQUESTS

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
API_TITLE: str = "Juris AI"
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

# ── User memory ───────────────────────────────────────────────────────────────
# Sliding retention window: a memory expires this many days after it was
# last used (see UserMemoryRepository -- expired rows are treated as
# inactive at query time). PLACEHOLDER, not a legal determination.
#
# TODO(legal): replace with the confirmed retention period for this
# product's jurisdiction and matter types before this ships to real
# users. This is the only place the window is defined -- everything
# else derives expires_at from it.
USER_MEMORY_RETENTION_DAYS: int = 120

# One atomic fact, not a paragraph. Mirrored as the user_memories.content
# column width in migration a4c1e7d92b35 -- widening it needs a new migration.
USER_MEMORY_MAX_CONTENT_CHARS: int = 300

# Hard ceiling on stored memories per user. Extraction is best-effort and
# there is no consolidation job yet (Phase 2), so this bounds growth.
USER_MEMORY_MAX_PER_USER: int = 200

# Read-path selection (see UserMemoryService.retrieve_for_prompt).
USER_MEMORY_RETRIEVAL_TOP_K: int = 5
USER_MEMORY_MAX_PROFILE_ITEMS: int = 3

# Cosine-similarity floor for a non-profile memory to be injected.
# UNCALIBRATED placeholder: BGE-style embeddings score even unrelated short
# texts well above zero, so this must be tuned against real memories before
# it can be trusted. Profile-kind items bypass it by design.
USER_MEMORY_MIN_SIMILARITY: float = 0.5

# Recency tie-breaker added to similarity: a memory used today gets the
# full bonus, decaying linearly to zero over the window. Deliberately small
# so it reorders near-ties without letting a stale-but-recent fact outrank
# a genuinely relevant one.
USER_MEMORY_RECENCY_BONUS_MAX: float = 0.05
USER_MEMORY_RECENCY_WINDOW_DAYS: int = 30

# Token cap for the whole <user_memory> block, enforced at retrieval time
# because fit_to_budget never truncates the system side of a prompt.
USER_MEMORY_MAX_PROMPT_TOKENS: int = 400

# Write path (see UserMemoryExtractor). Extraction runs once at least
# this many new USER messages have accumulated since the conversation's
# extraction watermark.
USER_MEMORY_EXTRACTION_TURN_INTERVAL: int = 6

# Bounds on a single extraction call: how many pending USER messages are
# considered (oldest first, the rest wait for the next pass), how much of
# each is sent (a pasted document must not become the prompt), and how
# many existing memories are shown to the model for dedupe/supersede.
USER_MEMORY_EXTRACTION_MAX_EVENTS: int = 30
USER_MEMORY_EXTRACTION_EVENT_MAX_CHARS: int = 2000
USER_MEMORY_EXTRACTION_CONTEXT_K: int = 8
USER_MEMORY_EXTRACTION_MAX_OUTPUT_TOKENS: int = 700
USER_MEMORY_EXTRACTION_MAX_OPERATIONS: int = 8

# Operations the model reports below this confidence are dropped.
# UNCALIBRATED placeholder, like USER_MEMORY_MIN_SIMILARITY: model-stated
# confidence is not a measured probability.
USER_MEMORY_MIN_EXTRACTION_CONFIDENCE: float = 0.6

# Test DB Configuration
TEST_DB_URL = "sqlite+aiosqlite:///./pytests.db"


# Default Auth Configuration
DEFAULT_JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60


API_DESCRIPTION = """
## Juris-AI

Juris-AI is an AI-powered legal assistant API supporting:

- User authentication and authorization
- Conversation management
- AI-powered chat
- Document management
- Agent orchestration
- Human-in-the-loop approval workflows
- Agent action authorization and execution
- Long-term user memory (opt-in, cross-conversation preference/profile facts)

### Authentication

Protected endpoints use JWT Bearer authentication.

Authenticate using:

`POST /api/v1/auth/login`

Then click **Authorize** in Swagger UI and provide the issued
Bearer token.

### API Version

Current API version: `v1`
"""
