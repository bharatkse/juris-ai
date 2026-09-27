"""
Unit tests for ComplianceLogService.record_memory_operation.

The compliance log is insert-only and retained indefinitely by default,
so it can never honour an erasure request. These tests pin the contract
that keeps memory text out of it structurally, not just by convention.
"""

from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

from application.services.compliance_log import (
    ComplianceLogService,
    StandaloneComplianceLogWriter,
)
from core.enums import (
    ActorTypeEnum,
    ComplianceEventTypeEnum,
    UserMemoryOperationEnum,
)

_ALLOWED_PARAMETERS = {
    "self",
    "user_id",
    "tenant_id",
    "operation",
    "actor_type",
    "memory_id",
    "content_hash",
    "kind",
    "count",
    "request_id",
    "conversation_id",
    "conversation_event_id",
}


def _service() -> tuple[ComplianceLogService, MagicMock]:
    repository = MagicMock()
    repository.create = AsyncMock(side_effect=lambda entry: entry)

    return ComplianceLogService(session=MagicMock(), repository=repository), repository


def test_the_method_has_no_parameter_that_could_carry_memory_text() -> None:
    parameters = set(inspect.signature(ComplianceLogService.record_memory_operation).parameters)

    assert parameters <= _ALLOWED_PARAMETERS, (
        f"unexpected parameter(s) {parameters - _ALLOWED_PARAMETERS}: memory text must never "
        "be loggable here; only identifiers, counts and hashes."
    )
    for forbidden in ("content", "text", "message", "payload", "detail", "extra"):
        assert forbidden not in parameters


async def test_payload_holds_only_the_operation_and_the_supplied_identifiers() -> None:
    service, repository = _service()

    entry = await service.record_memory_operation(
        user_id="user_a",
        tenant_id="user_a",
        operation=UserMemoryOperationEnum.STORED,
        actor_type=ActorTypeEnum.AGENT,
        memory_id="umem_1",
        content_hash="ab" * 32,
        kind="preference",
    )

    assert entry.event_type is ComplianceEventTypeEnum.MEMORY_OPERATION
    assert entry.payload == {
        "operation": "stored",
        "memory_id": "umem_1",
        "content_hash": "ab" * 32,
        "kind": "preference",
    }
    assert entry.resource_type == "user_memory"
    assert entry.resource_id == "umem_1"
    repository.create.assert_awaited_once()


async def test_omitted_fields_are_left_out_of_the_payload_rather_than_null() -> None:
    service, _ = _service()

    entry = await service.record_memory_operation(
        user_id="user_a",
        tenant_id="user_a",
        operation=UserMemoryOperationEnum.CONSENT_WITHDRAWN,
        actor_type=ActorTypeEnum.USER,
        count=3,
    )

    assert entry.payload == {"operation": "consent_withdrawn", "count": 3}
    assert entry.resource_id is None


async def test_a_count_of_zero_is_kept() -> None:
    service, _ = _service()

    entry = await service.record_memory_operation(
        user_id="user_a",
        tenant_id="user_a",
        operation=UserMemoryOperationEnum.DELETED_ALL,
        actor_type=ActorTypeEnum.USER,
        count=0,
    )

    assert entry.payload["count"] == 0


async def test_the_standalone_writer_exposes_it_for_background_work() -> None:
    assert hasattr(StandaloneComplianceLogWriter, "record_memory_operation")
