"""
Centralized provider-independent LLM inference configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class LLMTask(StrEnum):
    """Application-level inference intent."""

    STRUCTURED_DECISION = "structured_decision"
    FACTUAL_ANSWER = "factual_answer"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    CREATIVE_GENERATION = "creative_generation"


@dataclass(frozen=True, slots=True)
class LLMInferenceConfig:
    """Provider-independent inference configuration."""

    model: str | None = None
    temperature: float = 0.2
    top_p: float | None = None
    max_output_tokens: int | None = None
    structured_output: bool = False

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0.0 and 2.0")

        if self.top_p is not None and not 0.0 < self.top_p <= 1.0:
            raise ValueError("top_p must be greater than 0.0 and at most 1.0")

        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be greater than 0")

        if self.model is not None and not self.model.strip():
            raise ValueError("model must not be blank")


@dataclass(frozen=True, slots=True)
class InferencePolicy:
    """Resolve application task intent into inference configuration.

    Task-specific temperatures override the global/default temperature.
    Global settings provide operational defaults when a task does not have
    an explicitly configured temperature.

    Model routing/cascading is intentionally outside this policy.
    """

    default_temperature: float = 0.2
    structured_decision_temperature: float = 0.0
    factual_answer_temperature: float | None = 0.2
    summarization_temperature: float | None = 0.3
    classification_temperature: float | None = 0.0
    creative_generation_temperature: float | None = 0.8
    default_top_p: float | None = None
    default_max_output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.default_temperature <= 2.0:
            raise ValueError(
                "default_temperature must be between 0.0 and 2.0",
            )

        task_temperatures = (
            self.structured_decision_temperature,
            self.factual_answer_temperature,
            self.summarization_temperature,
            self.classification_temperature,
            self.creative_generation_temperature,
        )

        for value in task_temperatures:
            if value is not None and not 0.0 <= value <= 2.0:
                raise ValueError(
                    "task temperature must be between 0.0 and 2.0",
                )

        if self.default_top_p is not None and not 0.0 < self.default_top_p <= 1.0:
            raise ValueError(
                "default_top_p must be greater than 0.0 and at most 1.0",
            )

        if self.default_max_output_tokens is not None and self.default_max_output_tokens <= 0:
            raise ValueError(
                "default_max_output_tokens must be greater than 0",
            )

    def resolve(
        self,
        task: LLMTask,
        *,
        model: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        structured_output: bool = False,
    ) -> LLMInferenceConfig:
        """Resolve task intent and optional request overrides."""

        task_temperatures = {
            LLMTask.STRUCTURED_DECISION: self.structured_decision_temperature,
            LLMTask.FACTUAL_ANSWER: self.factual_answer_temperature,
            LLMTask.SUMMARIZATION: self.summarization_temperature,
            LLMTask.CLASSIFICATION: self.classification_temperature,
            LLMTask.CREATIVE_GENERATION: self.creative_generation_temperature,
        }

        task_temperature = task_temperatures[task]

        resolved_temperature = (
            temperature
            if temperature is not None
            else (task_temperature if task_temperature is not None else self.default_temperature)
        )

        return LLMInferenceConfig(
            model=model,
            temperature=resolved_temperature,
            top_p=(top_p if top_p is not None else self.default_top_p),
            max_output_tokens=(
                max_output_tokens
                if max_output_tokens is not None
                else self.default_max_output_tokens
            ),
            structured_output=structured_output,
        )
