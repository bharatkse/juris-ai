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

    The validator is responsible for structural and dependency
    validation only.

    It does not:
        - execute steps,
        - reorder steps,
        - mutate plans,
        - access external services,
        - maintain runtime state.
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
                message=("Execution plan must contain at least " "one execution step."),
            )

        cls._validate_step_ids(
            plan=plan,
        )

        cls._validate_mode(
            plan=plan,
        )

        cls._validate_steps(
            plan=plan,
        )

        cls._validate_dependencies(
            plan=plan,
        )

    @staticmethod
    def _validate_mode(
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate the execution mode.

        Execution mode defines the execution strategy.

        Dependencies are validated independently and are the
        authoritative representation of the execution graph.
        """

        match plan.mode:
            case ExecutionModeEnum.SEQUENTIAL:
                return

            case ExecutionModeEnum.PARALLEL:
                return

            case ExecutionModeEnum.HYBRID:
                return

            case _:
                raise PlanValidationError(
                    message=(f"Unsupported execution mode " f"'{plan.mode}'."),
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
                message=("Execution step identifiers must be unique."),
            )

    @classmethod
    def _validate_steps(
        cls,
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate individual execution steps.
        """

        for step in plan.steps:
            cls._validate_step(
                step=step,
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
                message=("Execution step identifier " "cannot be empty."),
            )

        if not step.agent:
            raise PlanValidationError(
                message=("Execution step must specify an agent."),
            )

        if not step.instruction.strip():
            raise PlanValidationError(
                message=("Execution step instruction " "cannot be empty."),
            )

        if step.stage < 1:
            raise PlanValidationError(
                message=("Execution step stage must be " "greater than zero."),
            )

    @classmethod
    def _validate_dependencies(
        cls,
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate execution step dependencies.

        Dependencies must:
            - reference existing steps,
            - not reference the current step,
            - not contain duplicates,
            - form an acyclic directed graph.
        """

        step_ids = {step.id for step in plan.steps}

        for step in plan.steps:
            cls._validate_step_dependencies(
                step=step,
                step_ids=step_ids,
            )

        cls._validate_dependency_graph(
            plan=plan,
        )

    @staticmethod
    def _validate_step_dependencies(
        *,
        step: ExecutionStepDTO,
        step_ids: set[str],
    ) -> None:
        """
        Validate dependencies declared by a single step.
        """

        dependencies = step.depends_on

        if len(dependencies) != len(set(dependencies)):
            raise PlanValidationError(
                message=(f"Execution step '{step.id}' " "contains duplicate dependencies."),
            )

        for dependency_id in dependencies:
            if not dependency_id.strip():
                raise PlanValidationError(
                    message=(
                        f"Execution step '{step.id}' " "contains an empty dependency identifier."
                    ),
                )

            if dependency_id == step.id:
                raise PlanValidationError(
                    message=(f"Execution step '{step.id}' " "cannot depend on itself."),
                )

            if dependency_id not in step_ids:
                raise PlanValidationError(
                    message=(
                        f"Execution step '{step.id}' "
                        f"has unknown dependency "
                        f"'{dependency_id}'."
                    ),
                )

    @classmethod
    def _validate_dependency_graph(
        cls,
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate that execution dependencies form a DAG.

        Uses depth-first traversal with three node states:

            unvisited
            visiting
            visited

        Encountering a node that is already being visited
        indicates a dependency cycle.
        """

        dependencies = {step.id: step.depends_on for step in plan.steps}

        visiting: set[str] = set()
        visited: set[str] = set()

        for step_id in dependencies:
            cls._visit_dependency(
                step_id=step_id,
                dependencies=dependencies,
                visiting=visiting,
                visited=visited,
            )

    @classmethod
    def _visit_dependency(
        cls,
        *,
        step_id: str,
        dependencies: dict[str, tuple[str, ...]],
        visiting: set[str],
        visited: set[str],
    ) -> None:
        """
        Visit a dependency node during cycle detection.
        """

        if step_id in visited:
            return

        if step_id in visiting:
            raise PlanValidationError(
                message=("Execution plan contains a " "dependency cycle."),
            )

        visiting.add(
            step_id,
        )

        for dependency_id in dependencies[step_id]:
            cls._visit_dependency(
                step_id=dependency_id,
                dependencies=dependencies,
                visiting=visiting,
                visited=visited,
            )

        visiting.remove(
            step_id,
        )

        visited.add(
            step_id,
        )
