from __future__ import annotations

from typing import Literal

from pydantic import SecretStr

from config.base import BaseAppSettings
from core.enums import GroqModelEnum, LLMMODELEnum, LLMProviderEnum


class LLMSettings(BaseAppSettings):
    """AI Providers, Local Models, Search Engines, and Observability."""

    # Local LLM
    LLM_LOCAL: str = LLMProviderEnum.LOCAL
    LLM_LOCAL_BASE_URL: str | None = None
    LLM_LOCAL_MODEL: str = LLMMODELEnum.QWEN3_8B

    # Provider-independent inference defaults
    LLM_TEMPERATURE: float = 0.2
    LLM_TOP_P: float | None = None
    LLM_MAX_OUTPUT_TOKENS: int | None = None

    # Search & RAG
    SEARXNG_BASE_URL: str
    mcp_rag_server_url: str = "http://searxng:8080"
    web_research_max_concurrency: int = 10
    web_research_fetch_timeout_seconds: int = 10
    web_research_max_chars_per_page: int = 2000
    rag_min_rerank_score: float = 0.3
    # RRF (Reciprocal Rank Fusion) smoothing constant for hybrid
    # retrieval merge — distinct from rag_min_rerank_score above.
    rag_rrf_k: int = 60
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 100
    # Single switch point between the two FaithfulnessBackend
    # implementations (see rag/evaluation/faithfulness_backend.py) --
    # "legacy" is the proven hand-rolled judge (RAGEvaluator.faithfulness()),
    # "ragas" is the ragas-library-backed one. Default stays "legacy"
    # until "ragas" is validated; both FaithfulnessMetric and
    # OnlineEvalSampler get their backend from the same factory
    # (wiring/factories/evaluation.py's build_faithfulness_backend), so
    # flipping this one value changes both at once.
    faithfulness_backend: Literal["legacy", "ragas"] = "legacy"

    # External APIs
    GROQ_API_KEY: SecretStr | None = None
    GROQ_MODEL: GroqModelEnum = GroqModelEnum.GPT_OSS_120B
    # Separate, cheaper model for LLM-judge calls only (faithfulness/
    # relevancy/precision/recall -- wiring/factories/evaluation.py::
    # build_llm_judge()). Validated empirically before switching:
    # scripts/python/calibrate_answer_quality_thresholds.py re-run with
    # this model reproduced the SAME perfect groundedness separation
    # (1.000 accuracy at the same t=0.50 threshold) as GROQ_MODEL
    # (gpt-oss-120b) on the golden dataset -- see claude.md's Step 2
    # trace. Agent reasoning/planning/summarization are unaffected by
    # this setting; they still resolve to GROQ_MODEL.
    JUDGE_MODEL: GroqModelEnum = GroqModelEnum.GPT_OSS_20B
    # Cheaper model for conversation summarization only (application/
    # services/conversation_summarization.py). Lower-confidence than
    # JUDGE_MODEL above: based on a single real side-by-side spot-check
    # (same conversation, both models, manually compared), NOT a
    # calibration -- there's no automated quality harness for
    # summarization output the way calibrate_answer_quality_thresholds.py
    # provides for the answer-quality gate. One config point, deliberately
    # easy to revert (set back to GroqModelEnum.GPT_OSS_120B) if real
    # traffic surfaces a quality complaint -- see the INFO log
    # ("Conversation summarized.") each summarization call emits with
    # its model and output token count, which exists specifically to
    # give a real signal if that happens without having built a full
    # harness today.
    SUMMARIZATION_MODEL: GroqModelEnum = GroqModelEnum.GPT_OSS_20B
    # Model for extracting durable user facts from conversations
    # (application/services/user_memory_extraction.py). UNVALIDATED for
    # this task: it defaults to the same cheaper model as summarization
    # only because extraction is a low-stakes, temperature-0, structured
    # JSON call, not because extraction quality was measured. There is no
    # extraction-precision eval yet (deferred to Phase 2) -- see
    # docs/server/architecture/user-memory.md. One config point, easy to
    # move up to GPT_OSS_120B if extracted facts turn out noisy.
    MEMORY_EXTRACTION_MODEL: GroqModelEnum = GroqModelEnum.GPT_OSS_20B
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
