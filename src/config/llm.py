from __future__ import annotations

from pydantic import SecretStr

from config.base import BaseAppSettings
from core.enums import GroqModelEnum, LLMMODELEnum, LLMProviderEnum


class LLMSettings(BaseAppSettings):
    """AI Providers, Local Models, Search Engines, and Observability."""

    # Local LLM
    LLM_LOCAL: str = LLMProviderEnum.LOCAL
    LLM_LOCAL_BASE_URL: str | None = None
    LLM_LOCAL_MODEL: str = LLMMODELEnum.QWEN3_8B

    # Search & RAG
    SEARXNG_BASE_URL: str
    mcp_rag_server_url: str = "http://searxng:8080"
    web_research_max_concurrency: int = 10
    web_research_fetch_timeout_seconds: int = 10
    web_research_max_chars_per_page: int = 2000
    rag_min_rerank_score: float = 0.5

    # External APIs
    GROQ_API_KEY: SecretStr | None = None
    GROQ_MODEL: GroqModelEnum = GroqModelEnum.GPT_OSS_120B
    BRAVE_API_KEY: SecretStr | None = None

    # LangSmith Observability
    LANGSMITH_TRACING: bool = False
    LANGSMITH_TRACING_V2: bool = False
    LANGSMITH_API_KEY: SecretStr | None = None
    LANGSMITH_PROJECT: str = "juris-ai"
    LANGSMITH_ENDPOINT: str = "https://api.smith.langchain.com"

    @property
    def groq_api_key(self) -> str | None:
        return self.GROQ_API_KEY.get_secret_value() if self.GROQ_API_KEY else None

    @property
    def brave_api_key(self) -> str | None:
        return self.BRAVE_API_KEY.get_secret_value() if self.BRAVE_API_KEY else None

    @property
    def langsmith_key(self) -> str | None:
        return self.LANGSMITH_API_KEY.get_secret_value() if self.LANGSMITH_API_KEY else None
