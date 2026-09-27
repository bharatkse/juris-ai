"""
Planning templates.

Provides deterministic execution plans for
well-known request patterns.
"""

from __future__ import annotations

import re

from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO, PlanningRequestDTO
from core.enums import AgentTypeEnum, ExecutionModeEnum, IntentEnum


class PlanTemplateRegistry:
    """
    Resolve deterministic execution plans.

    Template resolution is intentionally:
        - synchronous,
        - stateless,
        - deterministic,
        - CPU-only,
        - independent of LLM providers.

    A template match bypasses the planning LLM entirely.
    """

    def resolve(
        self,
        *,
        request: PlanningRequestDTO,
    ) -> ExecutionPlanDTO | None:
        """
        Resolve a deterministic execution plan.

        A template is returned only when exactly one supported
        template matches the request.

        Multiple matches are treated as ambiguous and delegated
        to the LLM planner.
        """

        message = self._normalize(
            request.message,
        )

        matches = (
            (
                self._is_contract_review(
                    message=message,
                ),
                self._contract_review,
            ),
            (
                self._is_contract_analysis(
                    message=message,
                ),
                self._contract_analysis,
            ),
            (
                self._is_clause_extraction(
                    message=message,
                ),
                self._clause_extraction,
            ),
            (
                self._is_risk_analysis(
                    message=message,
                ),
                self._risk_analysis,
            ),
            (
                self._is_legal_research(
                    message=message,
                ),
                self._legal_research,
            ),
        )

        matched_templates = tuple(builder for matched, builder in matches if matched)

        if len(matched_templates) != 1:
            return None

        return matched_templates[0]()

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
                    agent=AgentTypeEnum.LEGAL,
                    instruction="Answer the user's question.",
                ),
            ),
        )

    @staticmethod
    def _normalize(
        message: str,
    ) -> str:
        """
        Normalize a request for deterministic matching.
        """

        return re.sub(
            r"\s+",
            " ",
            message.strip().lower(),
        )

    @staticmethod
    def _is_contract_review(
        *,
        message: str,
    ) -> bool:
        """
        Determine whether the request is an explicit
        contract-review request.
        """

        return any(
            phrase in message
            for phrase in (
                "review this contract",
                "review the contract",
                "review this agreement",
                "review the agreement",
            )
        )

    @staticmethod
    def _is_contract_analysis(
        *,
        message: str,
    ) -> bool:
        """
        Determine whether the request is an explicit
        contract-analysis request.
        """

        return any(
            phrase in message
            for phrase in (
                "analyze this contract",
                "analyze the contract",
                "analyse this contract",
                "analyse the contract",
                "analyze this agreement",
                "analyze the agreement",
                "analyse this agreement",
                "analyse the agreement",
            )
        )

    @staticmethod
    def _is_clause_extraction(
        *,
        message: str,
    ) -> bool:
        """
        Determine whether the request is an explicit
        clause-extraction request.
        """

        return any(
            phrase in message
            for phrase in (
                "extract clauses",
                "extract the clauses",
                "extract important clauses",
                "list important clauses",
                "find important clauses",
            )
        )

    @staticmethod
    def _is_risk_analysis(
        *,
        message: str,
    ) -> bool:
        """
        Determine whether the request is an explicit
        risk-analysis request.
        """

        return any(
            phrase in message
            for phrase in (
                "risk analysis",
                "analyze risks",
                "analyse risks",
                "identify risks",
                "identify legal risks",
                "identify contractual risks",
                "find legal risks",
                "find contractual risks",
            )
        )

    @staticmethod
    def _is_legal_research(
        *,
        message: str,
    ) -> bool:
        """
        Determine whether the request is an explicit
        legal-research request.
        """

        return any(
            phrase in message
            for phrase in (
                "legal research",
                "research the law",
                "research this law",
                "research the regulation",
                "research this regulation",
                "research the applicable regulation",
                "research this applicable regulation",
                "case law",
                "legal precedent",
                "what does the law say",
                "what does the regulation say",
            )
        )

    @staticmethod
    def _contract_review() -> ExecutionPlanDTO:
        """
        Build the contract review execution plan.
        """

        return PlanTemplateRegistry._build_plan(
            intent=IntentEnum.CONTRACT_REVIEW,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="review_contract",
                    agent=AgentTypeEnum.CONTRACT,
                    instruction="Review the supplied contract.",
                ),
            ),
        )

    @staticmethod
    def _contract_analysis() -> ExecutionPlanDTO:
        """
        Build the contract analysis execution plan.
        """

        return PlanTemplateRegistry._build_plan(
            intent=IntentEnum.CONTRACT_ANALYSIS,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="analyze_contract",
                    agent=AgentTypeEnum.CONTRACT,
                    instruction="Analyze the supplied contract.",
                ),
            ),
        )

    @staticmethod
    def _clause_extraction() -> ExecutionPlanDTO:
        """
        Build the clause extraction execution plan.
        """

        return PlanTemplateRegistry._build_plan(
            intent=IntentEnum.CLAUSE_EXTRACTION,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="extract_clauses",
                    agent=AgentTypeEnum.CONTRACT,
                    instruction="Extract important clauses.",
                ),
            ),
        )

    @staticmethod
    def _risk_analysis() -> ExecutionPlanDTO:
        """
        Build the risk analysis execution plan.
        """

        return PlanTemplateRegistry._build_plan(
            intent=IntentEnum.RISK_ANALYSIS,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="identify_risks",
                    agent=AgentTypeEnum.CONTRACT,
                    instruction="Identify contractual risks.",
                ),
            ),
        )

    @staticmethod
    def _legal_research() -> ExecutionPlanDTO:
        """
        Build the legal research execution plan.
        """

        return PlanTemplateRegistry._build_plan(
            intent=IntentEnum.LEGAL_RESEARCH,
            mode=ExecutionModeEnum.SEQUENTIAL,
            steps=(
                ExecutionStepDTO(
                    id="answer_legal_question",
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
