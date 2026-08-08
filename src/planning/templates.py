"""
Planning templates.

Provides deterministic execution plans for
well-known intents.
"""

from __future__ import annotations

from src.core.models.planning import (
    AgentType,
    ExecutionMode,
    ExecutionPlan,
    ExecutionStep,
    Intent,
)


class PlanTemplateRegistry:
    """
    Resolve rule-based execution plans.
    """

    def resolve(
        self,
        *,
        intent: Intent,
    ) -> ExecutionPlan | None:
        """
        Return a predefined execution plan.

        Returns:
            A deterministic execution plan when one exists,
            otherwise None.
        """

        match intent:
            case Intent.CONTRACT_REVIEW:
                return self._contract_review()

            case Intent.CONTRACT_ANALYSIS:
                return self._contract_analysis()

            case Intent.CLAUSE_EXTRACTION:
                return self._clause_extraction()

            case Intent.RISK_ANALYSIS:
                return self._risk_analysis()

            case Intent.LEGAL_RESEARCH:
                return self._legal_research()

            case _:
                return None

    def default(
        self,
    ) -> ExecutionPlan:
        """
        Return the default execution plan.
        """

        return self._build_plan(
            intent=Intent.GENERAL,
            mode=ExecutionMode.SEQUENTIAL,
            steps=(
                ExecutionStep(
                    id="answer",
                    stage=1,
                    agent=AgentType.LEGAL,
                    instruction="Answer the user's question.",
                ),
            ),
        )

    def _contract_review(
        self,
    ) -> ExecutionPlan:
        """
        Build the contract review execution plan.

        NOTE:
            This starts as a sequential plan but can later
            evolve into a hybrid workflow without changing
            the planner or executor.
        """

        return self._build_plan(
            intent=Intent.CONTRACT_REVIEW,
            mode=ExecutionMode.SEQUENTIAL,
            steps=(
                ExecutionStep(
                    id="review_contract",
                    stage=1,
                    agent=AgentType.CONTRACT,
                    instruction="Review the supplied contract.",
                ),
            ),
        )

    def _contract_analysis(
        self,
    ) -> ExecutionPlan:
        """
        Build the contract analysis execution plan.
        """

        return self._build_plan(
            intent=Intent.CONTRACT_ANALYSIS,
            mode=ExecutionMode.SEQUENTIAL,
            steps=(
                ExecutionStep(
                    id="analyze_contract",
                    stage=1,
                    agent=AgentType.CONTRACT,
                    instruction="Analyze the supplied contract.",
                ),
            ),
        )

    def _clause_extraction(
        self,
    ) -> ExecutionPlan:
        """
        Build the clause extraction execution plan.
        """

        return self._build_plan(
            intent=Intent.CLAUSE_EXTRACTION,
            mode=ExecutionMode.SEQUENTIAL,
            steps=(
                ExecutionStep(
                    id="extract_clauses",
                    stage=1,
                    agent=AgentType.CONTRACT,
                    instruction="Extract important clauses.",
                ),
            ),
        )

    def _risk_analysis(
        self,
    ) -> ExecutionPlan:
        """
        Build the risk analysis execution plan.
        """

        return self._build_plan(
            intent=Intent.RISK_ANALYSIS,
            mode=ExecutionMode.SEQUENTIAL,
            steps=(
                ExecutionStep(
                    id="identify_risks",
                    stage=1,
                    agent=AgentType.CONTRACT,
                    instruction="Identify contractual risks.",
                ),
            ),
        )

    def _legal_research(
        self,
    ) -> ExecutionPlan:
        """
        Build the legal research execution plan.
        """

        return self._build_plan(
            intent=Intent.LEGAL_RESEARCH,
            mode=ExecutionMode.SEQUENTIAL,
            steps=(
                ExecutionStep(
                    id="answer_legal_question",
                    stage=1,
                    agent=AgentType.LEGAL,
                    instruction="Answer the legal question.",
                ),
            ),
        )

    @staticmethod
    def _build_plan(
        *,
        intent: Intent,
        mode: ExecutionMode,
        steps: tuple[
            ExecutionStep,
            ...,
        ],
    ) -> ExecutionPlan:
        """
        Build an execution plan.
        """

        return ExecutionPlan(
            intent=intent,
            mode=mode,
            steps=steps,
        )
