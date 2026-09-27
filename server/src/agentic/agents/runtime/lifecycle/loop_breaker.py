from __future__ import annotations

from dataclasses import dataclass

from agentic.agents.runtime.lifecycle.guard import BudgetCheckResult, BudgetGuard
from agentic.agents.runtime.lifecycle.state import AgentState


@dataclass(slots=True)
class LoopBreaker:
    """
    Deterministic loop-control component for one request-scoped execution.

    LoopBreaker does not own execution state, execute actions, invoke agents,
    or create continuation loops. It evaluates whether the existing agent
    execution is repeatedly performing the same action or failing to make
    progress.

    AgentState remains the source of truth for counters.
    BudgetGuard remains responsible for the configured numeric limit.
    AgentLifecycle remains responsible for applying terminal state changes.
    """

    state: AgentState
    guard: BudgetGuard

    def record_action(self, action_key: str) -> BudgetCheckResult:
        """
        Track consecutive repetitions of an executable action.

        The first occurrence of an action starts a repetition sequence but
        does not count as a repetition. Each subsequent identical action
        increments the repetition counter. A different action resets the
        sequence.

        Therefore max_repeated_action represents the maximum number of
        consecutive repeats after the first occurrence.

        Uses the same pre-operation, increment-only-after-allow convention
        as every other budget counter (see AgentLifecycle.begin_iteration
        etc.): the guard is checked against the count of repeats already
        recorded, and the counter only advances once the guard allows it.
        """
        if not action_key:
            raise ValueError("action_key must not be empty.")

        if action_key != self.state.last_action_key:
            self.state.last_action_key = action_key
            self.state.repeated_action_count = 0

            return self.guard.check_repeated_action(
                repeat_count=self.state.repeated_action_count,
            )

        result = self.guard.check_repeated_action(
            repeat_count=self.state.repeated_action_count,
        )

        if result.allowed:
            self.state.repeated_action_count += 1

        return result

    def record_progress(
        self,
        progress_key: str,
    ) -> BudgetCheckResult:
        """
        Track consecutive observations that produce the same progress key.

        The first progress observation establishes the baseline and does not
        count as no-progress. Repeating the same progress identity increments
        the no-progress counter. A new progress key represents progress and
        resets the no-progress counter.

        No-progress uses its dedicated execution budget and termination
        reason rather than reusing the repeated-action control. This keeps
        semantic no-progress distinct from repeatedly issuing the same
        executable action.

        Uses the same pre-operation, increment-only-after-allow convention
        as record_action (see there for why).
        """
        if not progress_key:
            raise ValueError("progress_key must not be empty.")

        if progress_key != self.state.last_progress_key:
            self.state.last_progress_key = progress_key
            self.state.no_progress_count = 0

            return self.guard.check_no_progress(
                no_progress_count=self.state.no_progress_count,
            )

        result = self.guard.check_no_progress(
            no_progress_count=self.state.no_progress_count,
        )

        if result.allowed:
            self.state.no_progress_count += 1

        return result
