"""
Planning templates.

Provides deterministic execution plans for
well-known intents.
"""

from __future__ import annotations

from src.core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from src.core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum


class PlanTemplateRegistry:
    """
    Resolve rule-based execution plans.
    """

    def resolve(
        self,
        *,
        intent: IntentEnum,
    ) -> ExecutionPlanDTO | None:
        """
        Return a predefined execution plan.

        Returns:
            A deterministic execution plan when one exists,
            otherwise None.
        """

        match intent:
            case IntentEnum.CONTRACT_REVIEW:
                return self._contract_review()

            case IntentEnum.CONTRACT_ANALYSIS:
                return self._contract_analysis()

            case IntentEnum.CLAUSE_EXTRACTION:
                return self._clause_extraction()

            case IntentEnum.RISK_ANALYSIS:
                return self._risk_analysis()

            case IntentEnum.LEGAL_RESEARCH:
                return self._legal_research()

            case _:
                return None

    def default(
        self,
    ) -> ExecutionPlanDTO:
        """
        Return the default execution plan.
        """

        return self._build_plan(
            intent=IntentEnum.GENERAL,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="answer",
                    stage=1,
                    agent=AgentTypeEnum.LEGAL,
                    instruction="Answer the user's question.",
                ),
            ),
        )

    def _contract_review(
        self,
    ) -> ExecutionPlanDTO:
        """
        Build the contract review execution plan.

        NOTE:
            This starts as a sequential plan but can later
            evolve into a hybrid workflow without changing
            the planner or executor.
        """

        return self._build_plan(
            intent=IntentEnum.CONTRACT_REVIEW,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="review_contract",
                    stage=1,
                    agent=AgentTypeEnum.CONTRACT,
                    instruction="Review the supplied contract.",
                ),
            ),
        )

    def _contract_analysis(
        self,
    ) -> ExecutionPlanDTO:
        """
        Build the contract analysis execution plan.
        """

        return self._build_plan(
            intent=IntentEnum.CONTRACT_ANALYSIS,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="analyze_contract",
                    stage=1,
                    agent=AgentTypeEnum.CONTRACT,
                    instruction="Analyze the supplied contract.",
                ),
            ),
        )

    def _clause_extraction(
        self,
    ) -> ExecutionPlanDTO:
        """
        Build the clause extraction execution plan.
        """

        return self._build_plan(
            intent=IntentEnum.CLAUSE_EXTRACTION,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="extract_clauses",
                    stage=1,
                    agent=AgentTypeEnum.CONTRACT,
                    instruction="Extract important clauses.",
                ),
            ),
        )

    def _risk_analysis(
        self,
    ) -> ExecutionPlanDTO:
        """
        Build the risk analysis execution plan.
        """

        return self._build_plan(
            intent=IntentEnum.RISK_ANALYSIS,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="identify_risks",
                    stage=1,
                    agent=AgentTypeEnum.CONTRACT,
                    instruction="Identify contractual risks.",
                ),
            ),
        )

    def _legal_research(
        self,
    ) -> ExecutionPlanDTO:
        """
        Build the legal research execution plan.
        """

        return self._build_plan(
            intent=IntentEnum.LEGAL_RESEARCH,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="answer_legal_question",
                    stage=1,
                    agent=AgentTypeEnum.LEGAL,
                    instruction="Answer the legal question.",
                ),
            ),
        )

    @staticmethod
    def _build_plan(
        *,
        intent: IntentEnum,
        mode: ExecutionModeEnum,
        steps: tuple[
            ExecutionStepDTO,
            ...,
        ],
    ) -> ExecutionPlanDTO:
        """
        Build an execution plan.
        """

        return ExecutionPlanDTO(
            intent=intent,
            mode=mode,
            steps=steps,
        )
