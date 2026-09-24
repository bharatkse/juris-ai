"""
Execution plan validator.
"""

from __future__ import annotations

from itertools import combinations

from core.dto.planning import ExecutionPlanDTO, ExecutionStepDTO
from core.enums import ExecutionModeEnum
from core.exceptions.planning import PlanValidationError


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

        cls._validate_agent_concurrency(
            plan=plan,
        )

    @classmethod
    def _validate_agent_concurrency(
        cls,
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Ensure the same agent is never assigned to two steps that could
        execute at the same time.

        Two steps with no dependency relationship between them --
        neither is a (direct or transitive) dependency of the other --
        are unordered relative to each other: the compiled graph starts
        each as soon as its own dependencies are satisfied, with no
        guarantee either finishes before the other even starts (see
        ExecutionGraphBuilder, which derives graph edges purely from
        depends_on -- execution_mode is descriptive metadata only, see
        _validate_mode above). An agent assigned to two such steps would
        be asked to answer twice at once; ResponseValidator rejects that
        downstream as a duplicate response, but only after both agent
        calls already ran. Catching the invalid shape here, before any
        agent is invoked, is strictly cheaper and gives a clearer error.

        The same agent MAY appear on two steps that ARE connected by a
        dependency chain -- one step building on what an earlier step
        using the same agent already produced. That is a real,
        documented pattern (see planning.md's "Agent Assignment"
        section), not the shape this guards against. Safe to run after
        _validate_dependencies: the DAG is already confirmed acyclic by
        _validate_dependency_graph, so the ancestor walk below cannot
        loop.
        """

        ancestors = {
            step.id: cls._transitive_dependencies(
                step_id=step.id,
                plan=plan,
            )
            for step in plan.steps
        }

        steps_by_agent: dict[str, list[ExecutionStepDTO]] = {}

        for step in plan.steps:
            steps_by_agent.setdefault(step.agent, []).append(step)

        for agent, steps in steps_by_agent.items():
            for earlier, later in combinations(steps, 2):
                if earlier.id in ancestors[later.id] or later.id in ancestors[earlier.id]:
                    continue

                raise PlanValidationError(
                    message=(
                        f"Agent '{agent}' is assigned to steps '{earlier.id}' "
                        f"and '{later.id}', which have no dependency "
                        "relationship between them and could execute at the "
                        "same time. The same agent cannot be assigned to two "
                        "independent steps -- combine them into one step, or "
                        "make one depend on the other."
                    ),
                )

    @staticmethod
    def _transitive_dependencies(
        *,
        step_id: str,
        plan: ExecutionPlanDTO,
    ) -> set[str]:
        """
        Every step id ``step_id`` depends on, directly or transitively.
        """

        depends_on = {step.id: step.depends_on for step in plan.steps}

        found: set[str] = set()
        stack = list(depends_on.get(step_id, ()))

        while stack:
            dependency_id = stack.pop()

            if dependency_id in found:
                continue

            found.add(dependency_id)
            stack.extend(depends_on.get(dependency_id, ()))

        return found

    @staticmethod
    def _validate_mode(
        *,
        plan: ExecutionPlanDTO,
    ) -> None:
        """
        Validate the execution mode.

        Execution mode is part of the planning contract and describes
        the intended execution topology.

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
