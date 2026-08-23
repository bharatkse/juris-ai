"""
Unit tests for ApprovalRepository.
"""

from __future__ import annotations

import pytest

from src.core.enums import ApprovalStatusEnum
from tests.factories.approval import ApprovalFactory
from tests.helpers.identifiers import unknown_approval_id


@pytest.mark.asyncio
async def test_create_persists_approval(
    approval_repository,
) -> None:
    """
    It should persist an approval.
    """

    approval = ApprovalFactory.build()

    created = await approval_repository.create(
        entity=approval,
    )

    assert created.id == approval.id
    assert created.status == approval.status
    assert created.agent_action_id == approval.agent_action_id
    assert created.requested_by == approval.requested_by


@pytest.mark.asyncio
async def test_create_sets_timestamps(
    approval_repository,
) -> None:
    """
    It should populate timestamps.
    """

    approval = ApprovalFactory.build()

    created = await approval_repository.create(
        entity=approval,
    )

    assert created.created_at is not None
    assert created.updated_at is not None


@pytest.mark.asyncio
async def test_get_returns_existing_approval(
    approval_repository,
) -> None:
    """
    It should retrieve an existing approval.
    """

    approval = await approval_repository.create(
        entity=ApprovalFactory.build(),
    )

    found = await approval_repository.get(
        approval_id=approval.id,
    )

    assert found is not None
    assert found.id == approval.id
    assert found.status == approval.status
    assert found.agent_action_id == approval.agent_action_id
    assert found.requested_by == approval.requested_by


@pytest.mark.asyncio
async def test_get_returns_none_when_approval_does_not_exist(
    approval_repository,
) -> None:
    """
    It should return None for an unknown approval.
    """

    found = await approval_repository.get(
        approval_id=unknown_approval_id(),
    )

    assert found is None


@pytest.mark.asyncio
async def test_save_persists_changes(
    approval_repository,
) -> None:
    """
    It should persist changes to an approval.
    """

    approval = await approval_repository.create(
        entity=ApprovalFactory.build(
            status=ApprovalStatusEnum.WAITING,
        ),
    )

    approval.status = ApprovalStatusEnum.APPROVED

    updated = await approval_repository.save(
        entity=approval,
    )

    assert updated is approval
    assert updated.status == ApprovalStatusEnum.APPROVED


@pytest.mark.asyncio
async def test_save_persists_decision(
    approval_repository,
) -> None:
    """
    It should persist approval decision details.
    """

    approval = await approval_repository.create(
        entity=ApprovalFactory.build(
            status=ApprovalStatusEnum.WAITING,
        ),
    )

    approval.status = ApprovalStatusEnum.APPROVED
    approval.decision_reason = "Approved by reviewer."

    updated = await approval_repository.save(
        entity=approval,
    )

    assert updated.status == ApprovalStatusEnum.APPROVED
    assert updated.decision_reason == "Approved by reviewer."
