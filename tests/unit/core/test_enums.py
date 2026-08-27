"""
Unit tests for application enums.
"""

from __future__ import annotations

from core.enums import (
    CacheBackendEnum,
    EnvironmentEnum,
    EventTypeEnum,
    GenderEnum,
    GroqModelEnum,
    LLMProviderEnum,
    MessageRoleEnum,
    SortOrderEnum,
)


def test_environment_values() -> None:
    """
    It should expose the supported environments.
    """

    assert EnvironmentEnum.DEVELOPMENT == "development"
    assert EnvironmentEnum.STAGING == "staging"
    assert EnvironmentEnum.PRODUCTION == "production"
    assert EnvironmentEnum.TESTING == "testing"


def test_cache_backend_values() -> None:
    """
    It should expose the supported cache backends.
    """

    assert CacheBackendEnum.MEMORY == "memory"
    assert CacheBackendEnum.REDIS == "redis"


def test_gender_values() -> None:
    """
    It should expose the supported genders.
    """

    assert GenderEnum.MALE == "male"
    assert GenderEnum.FEMALE == "female"
    assert GenderEnum.OTHER == "other"


def test_message_role_values() -> None:
    """
    It should expose the supported message roles.
    """

    assert MessageRoleEnum.USER == "user"
    assert MessageRoleEnum.ASSISTANT == "assistant"
    assert MessageRoleEnum.SYSTEM == "system"
    assert MessageRoleEnum.TOOL == "tool"


def test_event_type_values() -> None:
    """
    It should expose the supported event types.
    """

    assert EventTypeEnum.USER == "user"
    assert EventTypeEnum.ASSISTANT == "assistant"
    assert EventTypeEnum.SYSTEM == "system"
    assert EventTypeEnum.TOOL_CALL == "tool_call"
    assert EventTypeEnum.TOOL_RESULT == "tool_result"
    assert EventTypeEnum.RETRIEVAL == "retrieval"
    assert EventTypeEnum.RERANK == "rerank"
    assert EventTypeEnum.PLANNER == "planner"


def test_sort_order_values() -> None:
    """
    It should expose the supported sort orders.
    """

    assert SortOrderEnum.ASC == "asc"
    assert SortOrderEnum.DESC == "desc"


def test_llm_provider_values() -> None:
    """
    It should expose the supported LLM providers.
    """

    assert LLMProviderEnum.GROQ == "groq"
    assert LLMProviderEnum.OPENAI == "openai"
    assert LLMProviderEnum.ANTHROPIC == "anthropic"
    assert LLMProviderEnum.OLLAMA == "ollama"


def test_groq_model_values() -> None:
    """
    It should expose the supported Groq models.
    """

    assert GroqModelEnum.LLAMA_3_1_8B == "llama-3.1-8b-instant"
    assert GroqModelEnum.LLAMA_3_3_70B == "llama-3.3-70b-versatile"
    assert GroqModelEnum.GPT_OSS_120B == "openai/gpt-oss-120b"
    assert GroqModelEnum.GPT_OSS_20B == "openai/gpt-oss-20b"


def test_enums_are_strings() -> None:
    """
    It should serialize enum members as strings.
    """

    assert isinstance(
        MessageRoleEnum.USER,
        str,
    )

    assert isinstance(
        LLMProviderEnum.GROQ,
        str,
    )

    assert isinstance(
        EnvironmentEnum.DEVELOPMENT,
        str,
    )
