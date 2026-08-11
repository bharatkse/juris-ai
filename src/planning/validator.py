"""
Execution plan validator.
"""

from __future__ import annotations

from src.core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from src.core.enums import ExecutionModeEnum
from src.core.exceptions.planning import PlanValidationError


class ExecutionPlanValidator:
    """
    Validates execution plans before execution.
    """

    def validate(
        self,
        plan: ExecutionPlanDTO,
    ) -> ExecutionPlanDTO:
        """
        Validate an execution plan.

        Raises:
            PlanValidationError:
                If the execution plan is invalid.
        """

        self._validate_plan(
            plan=plan,
        )

        return plan

    @classmethod
    def _validate_plan(
        cls,
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate an execution plan.
        """

        if not plan.steps:
            raise PlanValidationError(
                message="Execution plan must contain at least one execution step.",
            )

        cls._validate_step_ids(
            plan=plan,
        )

        cls._validate_mode(
            plan=plan,
        )

        for step in plan.steps:
            cls._validate_step(
                step=step,
            )

    @staticmethod
    def _validate_mode(
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate the execution mode.
        """

        match plan.mode:
            case ExecutionModeEnum.SEQUENTIAL:
                pass

            case ExecutionModeEnum.PARALLEL:
                pass

            case ExecutionModeEnum.HYBRID:
                ExecutionPlanValidator._validate_hybrid(
                    plan=plan,
                )

            case _:
                raise PlanValidationError(
                    message=(f"Unsupported execution mode '{plan.mode}'."),
                )

    @staticmethod
    def _validate_hybrid(
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate a hybrid execution plan.
        """

        stages = [step.stage for step in plan.steps]

        if min(stages) != 1:
            raise PlanValidationError(
                message="Hybrid execution stages must start at 1.",
            )

    @staticmethod
    def _validate_step_ids(
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate execution step identifiers.
        """

        step_ids = [step.id for step in plan.steps]

        if len(step_ids) != len(set(step_ids)):
            raise PlanValidationError(
                message="Execution step identifiers must be unique.",
            )

    @staticmethod
    def _validate_step(
        *,
        step: ExecutionStepDTO,
    ) -> None:
        """
        Validate a single execution step.
        """

        if not step.id.strip():
            raise PlanValidationError(
                message="Execution step identifier cannot be empty.",
            )

        if not step.agent:
            raise PlanValidationError(
                message="Execution step must specify an agent.",
            )

        if not step.instruction.strip():
            raise PlanValidationError(
                message="Execution step instruction cannot be empty.",
            )

        if step.stage < 1:
            raise PlanValidationError(
                message="Execution step stage must be greater than zero.",
            )
