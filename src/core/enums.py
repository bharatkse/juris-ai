"""
All enumerations used across the application.
Using str-based enums keeps JSON serialisation automatic.
"""

from enum import StrEnum


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


class GroqModelEnum(StrEnum):
    LLAMA_3_1_8B = "llama-3.1-8b-instant"
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GPT_OSS_20B = "openai/gpt-oss-20b"


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
    Supported execution strategies.

    SEQUENTIAL:
        Steps execute according to their dependency order.

    PARALLEL:
        Independent steps may execute concurrently.

    HYBRID:
        Dependency groups may execute sequentially while
        independent branches execute concurrently.
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
    Source of retrieved content.
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
    Source of the orchestration request.
    """

    CHAT = "chat"
    API = "api"
    TOOL = "tool"
