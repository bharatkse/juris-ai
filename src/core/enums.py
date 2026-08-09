"""
All enumerations used across the application.
Using str-based enums keeps JSON serialisation automatic.
"""

from enum import StrEnum


class Environment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class CacheBackend(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"


class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class MessageRole(StrEnum):
    """
    Supported chat message roles.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    TEST = "test"


class EventType(StrEnum):
    USER = "user"

    ASSISTANT = "assistant"

    SYSTEM = "system"

    TOOL_CALL = "tool_call"

    TOOL_RESULT = "tool_result"

    RETRIEVAL = "retrieval"

    RERANK = "rerank"

    PLANNER = "planner"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class LLMProvider(StrEnum):
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class GroqModel(StrEnum):
    LLAMA_3_1_8B = "llama-3.1-8b-instant"
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GPT_OSS_20B = "openai/gpt-oss-20b"


class DocumentStatus(StrEnum):
    """
    Document processing status.
    """

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class StorageType(StrEnum):
    """
    Supported storage providers.
    """

    LOCAL = "local"
    S3 = "s3"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"
    MINIO = "minio"
