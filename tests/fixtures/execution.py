import pytest

from src.execution.graph.builder import ExecutionGraphBuilder


@pytest.fixture
def execution_graph_builder() -> ExecutionGraphBuilder:
    """
    Provide an execution graph builder.
    """

    return ExecutionGraphBuilder()
