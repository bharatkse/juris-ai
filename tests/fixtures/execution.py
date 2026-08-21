from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.base import BaseCheckpointSaver

from src.execution.graph.builder import ExecutionGraphBuilder


@pytest.fixture
def execution_graph_builder() -> ExecutionGraphBuilder:
    """
    Provide an execution graph builder.
    """

    return ExecutionGraphBuilder()


@pytest.fixture
def mock_checkpointer() -> BaseCheckpointSaver:
    """
    Return a mocked retriever tool for agent tests.
    """

    return MagicMock(
        spec=BaseCheckpointSaver,
    )
