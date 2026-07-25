"""
Unit tests for application enums.
"""

from __future__ import annotations

from src.core.enums import (
    CacheBackend,
    Environment,
    EventType,
    Gender,
    GroqModel,
    LLMProvider,
    MessageRole,
    SortOrder,
)


def test_environment_values() -> None:
    """
    It should expose the supported environments.
    """

    assert Environment.DEVELOPMENT == "development"
    assert Environment.STAGING == "staging"
    assert Environment.PRODUCTION == "production"
    assert Environment.TESTING == "testing"


def test_cache_backend_values() -> None:
    """
    It should expose the supported cache backends.
    """

    assert CacheBackend.MEMORY == "memory"
    assert CacheBackend.REDIS == "redis"


def test_gender_values() -> None:
    """
    It should expose the supported genders.
    """

    assert Gender.MALE == "male"
    assert Gender.FEMALE == "female"
    assert Gender.OTHER == "other"


def test_message_role_values() -> None:
    """
    It should expose the supported message roles.
    """

    assert MessageRole.USER == "user"
    assert MessageRole.ASSISTANT == "assistant"
    assert MessageRole.SYSTEM == "system"
    assert MessageRole.TOOL == "tool"


def test_event_type_values() -> None:
    """
    It should expose the supported event types.
    """

    assert EventType.USER == "user"
    assert EventType.ASSISTANT == "assistant"
    assert EventType.SYSTEM == "system"
    assert EventType.TOOL_CALL == "tool_call"
    assert EventType.TOOL_RESULT == "tool_result"
    assert EventType.RETRIEVAL == "retrieval"
    assert EventType.RERANK == "rerank"
    assert EventType.PLANNER == "planner"


def test_sort_order_values() -> None:
    """
    It should expose the supported sort orders.
    """

    assert SortOrder.ASC == "asc"
    assert SortOrder.DESC == "desc"


def test_llm_provider_values() -> None:
    """
    It should expose the supported LLM providers.
    """

    assert LLMProvider.GROQ == "groq"
    assert LLMProvider.OPENAI == "openai"
    assert LLMProvider.ANTHROPIC == "anthropic"
    assert LLMProvider.OLLAMA == "ollama"


def test_groq_model_values() -> None:
    """
    It should expose the supported Groq models.
    """

    assert GroqModel.LLAMA_3_1_8B == "llama-3.1-8b-instant"
    assert GroqModel.LLAMA_3_3_70B == "llama-3.3-70b-versatile"
    assert GroqModel.GPT_OSS_120B == "openai/gpt-oss-120b"
    assert GroqModel.GPT_OSS_20B == "openai/gpt-oss-20b"


def test_enums_are_strings() -> None:
    """
    It should serialize enum members as strings.
    """

    assert isinstance(
        MessageRole.USER,
        str,
    )

    assert isinstance(
        LLMProvider.GROQ,
        str,
    )

    assert isinstance(
        Environment.DEVELOPMENT,
        str,
    )
