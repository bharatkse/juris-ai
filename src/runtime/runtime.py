"""
Runtime service composition.

Creates the shared runtime services.

Responsibilities:

- Create the planner
- Create the executor
- Create the response validator

No business logic belongs in this module.
"""

from __future__ import annotations

from src.execution.executor import Executor
from src.execution.hybrid import HybridExecutionStrategy
from src.execution.parallel import ParallelExecutionStrategy
from src.execution.sequential import SequentialExecutionStrategy
from src.planning.intent import IntentAnalyzer
from src.planning.llm_planner import LLMPlanGenerator
from src.planning.planner import ExecutionPlanner
from src.planning.templates import PlanTemplateRegistry
from src.planning.validator import ExecutionPlanValidator
from src.runtime.containers import ClientContainer, RegistryContainer, RuntimeContainer
from src.validation.response import ResponseValidator


def create_runtime(
    *,
    clients: ClientContainer,
    registries: RegistryContainer,
) -> RuntimeContainer:
    """
    Create the runtime services.
    """

    planner = ExecutionPlanner(
        intent_analyzer=IntentAnalyzer(),
        template_registry=PlanTemplateRegistry(),
        llm_planner=LLMPlanGenerator(
            llm_client=clients.llm_client,
        ),
        validator=ExecutionPlanValidator(
            agent_registry=registries.agent_registry,
        ),
    )

    executor = Executor(
        agent_registry=registries.agent_registry,
        sequential_strategy=SequentialExecutionStrategy(),
        parallel_strategy=ParallelExecutionStrategy(),
        hybrid_strategy=HybridExecutionStrategy(),
    )

    validator = ResponseValidator()

    return RuntimeContainer(
        planner=planner,
        executor=executor,
        validator=validator,
    )
