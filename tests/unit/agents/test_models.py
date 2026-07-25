from src.agents.models import AgentChunk, AgentRequest


def test_agent_request_defaults_history_to_empty_list() -> None:
    request = AgentRequest(question="Hello")

    assert request.history == []


def test_agent_chunk_defaults_metadata_to_empty_dict() -> None:
    chunk = AgentChunk()

    assert chunk.metadata == {}
