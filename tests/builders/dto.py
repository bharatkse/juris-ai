from typing import Any

from src.core.dto.agent_action import AgentActionResponseDTO
from src.core.enums import ActionTypeEnum, ActorTypeEnum, AgentActionStatusEnum


def build_agent_action_response_dto(
    **kwargs: Any,
) -> AgentActionResponseDTO:
    """
    Build an AgentActionResponseDTO for tests.
    """

    data = {
        "action_id": "action_123",
        "execution_id": "exec_123",
        "thread_id": "thread_123",
        "conversation_event_id": "event_123",
        "agent_id": "agent_123",
        "action_type": ActionTypeEnum.TOOL_CALL,
        "actor_type": ActorTypeEnum.AGENT,
        "tool_name": "search",
        "target_agent_id": None,
        "resource_type": "document",
        "resource_id": "doc_123",
        "parameters": {
            "query": "contract",
        },
        "reason": "Search the contract",
        "status": AgentActionStatusEnum.PENDING_APPROVAL,
        "fingerprint": "fingerprint_123",
    }

    data.update(kwargs)

    return AgentActionResponseDTO(
        **data,
    )
