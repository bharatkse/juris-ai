from core.dto.inference import InferencePolicy, LLMInferenceConfig, LLMTask


def test_structured_decision_uses_zero_temperature():
    config = InferencePolicy().resolve(LLMTask.STRUCTURED_DECISION)
    assert config.temperature == 0.0
    assert config.structured_output is False


def test_factual_answer_uses_factual_temperature():
    config = InferencePolicy().resolve(LLMTask.FACTUAL_ANSWER)
    assert config.temperature == 0.2


def test_request_temperature_overrides_task_temperature():
    config = InferencePolicy().resolve(
        LLMTask.FACTUAL_ANSWER,
        temperature=0.7,
    )
    assert config.temperature == 0.7


def test_default_temperature_is_used_when_task_temperature_is_none():
    policy = InferencePolicy(
        default_temperature=0.5,
        factual_answer_temperature=None,
    )
    config = policy.resolve(LLMTask.FACTUAL_ANSWER)
    assert config.temperature == 0.5


def test_top_p_and_max_output_tokens_are_resolved():
    config = InferencePolicy(
        default_top_p=0.9,
        default_max_output_tokens=512,
    ).resolve(LLMTask.FACTUAL_ANSWER)

    assert config.top_p == 0.9
    assert config.max_output_tokens == 512


def test_structured_output_flag_is_preserved():
    config = InferencePolicy().resolve(
        LLMTask.STRUCTURED_DECISION,
        structured_output=True,
    )
    assert config.structured_output is True


def test_inference_config_rejects_invalid_temperature():
    try:
        LLMInferenceConfig(temperature=2.1)
    except ValueError as exc:
        assert "temperature" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_inference_config_rejects_invalid_top_p():
    try:
        LLMInferenceConfig(top_p=0.0)
    except ValueError as exc:
        assert "top_p" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_inference_config_rejects_invalid_max_output_tokens():
    try:
        LLMInferenceConfig(max_output_tokens=0)
    except ValueError as exc:
        assert "max_output_tokens" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_inference_config_rejects_blank_model():
    try:
        LLMInferenceConfig(model="   ")
    except ValueError as exc:
        assert "model" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
