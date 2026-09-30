"""
The graph runs in what is left of the request's deadline (review R18): the
orchestrator starts that deadline before planning, so planning time is taken
out of the graph's 300 s budget instead of added to it.
"""

from __future__ import annotations

from agentic.execution.config import ExecutionTimeoutPolicy
from agentic.execution.session import ExecutionSession
from core.deadline import deadline_within


def _session(timeout_seconds: float) -> ExecutionSession:
    session = object.__new__(ExecutionSession)
    session._timeout_policy = ExecutionTimeoutPolicy(timeout_seconds=timeout_seconds)
    return session


def test_without_a_request_deadline_the_graph_gets_its_own_timeout() -> None:
    assert _session(300)._graph_timeout() == 300


def test_the_graph_gets_only_what_is_left_of_the_request_deadline() -> None:
    with deadline_within(10):
        assert 0 < _session(300)._graph_timeout() <= 10


def test_a_graph_timeout_shorter_than_the_deadline_still_applies() -> None:
    with deadline_within(600):
        assert _session(300)._graph_timeout() == 300
