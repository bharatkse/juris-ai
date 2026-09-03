"""
All enumerations used across the application.

Str-based enums provide JSON-friendly serialization while keeping
application state explicit and type-safe.
"""

from enum import StrEnum


class JWTAlgorithmEnum(StrEnum):
    """
    Supported JWT signing algorithms.
    """

    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"

    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"


class EnvironmentEnum(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class CacheBackendEnum(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"


class GenderEnum(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class MessageRoleEnum(StrEnum):
    """
    Supported chat message roles.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    TEST = "test"


class EventTypeEnum(StrEnum):
    """
    Supported conversation event types.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RETRIEVAL = "retrieval"
    RERANK = "rerank"
    PLANNER = "planner"


class SortOrderEnum(StrEnum):
    ASC = "asc"
    DESC = "desc"


class LLMProviderEnum(StrEnum):
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    LOCAL = "local"


class GroqModelEnum(StrEnum):
    LLAMA_3_1_8B = "llama-3.1-8b-instant"
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GPT_OSS_20B = "openai/gpt-oss-20b"


class LLMMODELEnum(StrEnum):
    QWEN3_4B = "qwen3:4b"
    QWEN3_8B = "qwen3:8b"


class AgentTypeEnum(StrEnum):
    """
    Supported agent types.
    """

    LEGAL = "legal"
    CONTRACT = "contract"


class DocumentStatusEnum(StrEnum):
    """
    Document processing status.
    """

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"
    INDEXED = "indexed"


class DocumentSourceEnum(StrEnum):
    FILE = "file"
    WEBSITE = "website"
    TEXT = "text"
    CLOUD_STORAGE = "cloud_storage"


class StorageTypeEnum(StrEnum):
    """
    Supported storage providers.
    """

    LOCAL = "local"
    S3 = "s3"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"
    MINIO = "minio"


class IntentEnum(StrEnum):
    """
    Supported planning intents.
    """

    GENERAL = "general"
    LEGAL_RESEARCH = "legal_research"
    CONTRACT_REVIEW = "contract_review"
    CONTRACT_ANALYSIS = "contract_analysis"
    CLAUSE_EXTRACTION = "clause_extraction"
    RISK_ANALYSIS = "risk_analysis"


class ExecutionModeEnum(StrEnum):
    """
    Supported execution modes.

    The execution mode is part of the planning contract.
    Runtime topology is derived from plan dependencies and
    executed by LangGraph.
    """

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


class ExecutionStatusEnum(StrEnum):
    """
    Runtime execution status.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RetrievalSourceEnum(StrEnum):
    """
    Sources of retrieved content.
    """

    WEB = "web"
    DOCUMENT = "document"
    VECTOR = "vector"
    DATABASE = "database"
    MEMORY = "memory"


class AttachmentTypeEnum(StrEnum):
    """
    Supported attachment types.
    """

    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"
    TEXT = "text"
    OTHER = "other"


class RequestSourceEnum(StrEnum):
    """
    Sources of orchestration requests.
    """

    CHAT = "chat"
    API = "api"
    TOOL = "tool"


# ============================================================================
# Authorization
# ============================================================================


class AuthorizationDecisionEnum(StrEnum):
    """
    Result of an authorization evaluation.

    This represents whether an actor is permitted to perform
    a requested operation.
    """

    ALLOW = "allow"
    DENY = "deny"


class ApprovalPolicyDecisionEnum(StrEnum):
    """
    Result of evaluating whether an authorized action requires
    human approval.

    This is a policy decision, not the lifecycle state of an
    approval request.
    """

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"


# ============================================================================
# Agent Actions
# ============================================================================


class ActionTypeEnum(StrEnum):
    """
    Categories of executable actions.

    AGENT_CALL represents agent-to-agent execution and allows
    the same action authorization path to be used for both
    tool actions and agent interactions.
    """

    GENERAL = "general"
    READ = "read"
    ANALYZE = "analyze"
    GENERATE = "generate"
    UPDATE = "update"
    DELETE = "delete"
    SEND = "send"
    SUBMIT = "submit"
    EXTERNAL = "external"
    AGENT_CALL = "agent_call"
    TOOL_CALL = "tool"


class AgentActionStatusEnum(StrEnum):
    """
    Lifecycle state of a persisted executable agent action.
    """

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


# ============================================================================
# Human Approval
# ============================================================================


class ApprovalStatusEnum(StrEnum):
    """
    Lifecycle state of a persisted human approval request.

    An Approval record exists only when human approval is required.
    """

    WAITING = "waiting"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    EXPIRED = "expired"


class ApprovalDecisionEnum(StrEnum):
    """
    Decision submitted by a human for an approval request.

    This is intentionally separate from ApprovalStatusEnum:
    a decision is an input, while status is persisted state.
    """

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


# ============================================================================
# Actors
# ============================================================================


class ActorTypeEnum(StrEnum):
    """
    Actor responsible for initiating an executable action.
    """

    USER = "user"
    AGENT = "agent"
