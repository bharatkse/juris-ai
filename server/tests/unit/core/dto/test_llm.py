from core.dto.clients.llm import LLMMessageDTO, LLMRequestDTO
from core.dto.inference import LLMInferenceConfig
from core.enums import MessageRoleEnum


def test_llm_request_defaults_to_inference_config():
    request = LLMRequestDTO(
        messages=(
            LLMMessageDTO(
                role=MessageRoleEnum.USER,
                content="hello",
            ),
        ),
    )

    assert isinstance(request.inference, LLMInferenceConfig)
    assert request.inference.temperature == 0.2


def test_llm_request_accepts_inference_config():
    inference = LLMInferenceConfig(
        temperature=0.0,
        top_p=0.9,
        max_output_tokens=256,
        structured_output=True,
    )

    request = LLMRequestDTO(
        messages=(),
        inference=inference,
    )

    assert request.inference is inference


def test_with_response_format_preserves_inference():
    inference = LLMInferenceConfig(
        temperature=0.0,
        max_output_tokens=128,
    )
    request = LLMRequestDTO(
        messages=(),
        inference=inference,
    )

    updated = request.with_response_format(
        response_format={"type": "json_object"},
    )

    assert updated.inference is inference
    assert updated.response_format == {"type": "json_object"}
