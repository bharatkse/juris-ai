"""
Unit tests for ComplianceLogService / StandaloneComplianceLogWriter.

Focus: each record_*() method shapes its own payload correctly, and
specifically never leaks raw content -- the no-raw-content rule this
module exists to enforce in one place (see its module docstring).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from adapters.persistence.sqlalchemy.models.compliance_log import ComplianceLog
from application.services.compliance_log import (
    ComplianceLogService,
    StandaloneComplianceLogWriter,
)
from core.dto.tool import RetrievedContentDTO
from core.enums import ActorTypeEnum, ComplianceEventTypeEnum, RetrievalSourceEnum


@pytest.fixture
def repository() -> MagicMock:
    repo = MagicMock()
    repo.create = AsyncMock(side_effect=lambda entity: entity)
    return repo


@pytest.fixture
def service(repository: MagicMock) -> ComplianceLogService:
    return ComplianceLogService(session=MagicMock(), repository=repository)


@pytest.mark.asyncio
async def test_record_request_received_never_stores_raw_message(
    service: ComplianceLogService,
    repository: MagicMock,
) -> None:
    message = "My PAN is ABCDE1234F and my SSN is 123-45-6789."
    request_id = uuid4()

    entry = await service.record_request_received(
        request_id=request_id,
        user_id="user_1",
        tenant_id="user_1",
        conversation_id="conv_1",
        conversation_event_id="evnt_1",
        message=message,
    )

    assert isinstance(entry, ComplianceLog)
    assert entry.event_type is ComplianceEventTypeEnum.REQUEST_RECEIVED
    assert entry.actor_type is ActorTypeEnum.USER

    payload_text = repr(entry.payload)
    assert message not in payload_text
    assert "ABCDE1234F" not in payload_text
    assert "123-45-6789" not in payload_text

    assert entry.payload["message_hash"] == hashlib.sha256(message.encode("utf-8")).hexdigest()
    assert entry.payload["message_length"] == len(message)

    repository.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_response_returned_never_stores_raw_content(
    service: ComplianceLogService,
) -> None:
    content = "The respondent's Aadhaar is 1234 5678 9012."
    request_id = uuid4()

    entry = await service.record_response_returned(
        request_id=request_id,
        user_id="user_1",
        tenant_id="user_1",
        conversation_id="conv_1",
        conversation_event_id="evnt_2",
        content=content,
        citation_count=2,
        action_required=False,
    )

    payload_text = repr(entry.payload)
    assert content not in payload_text
    assert "1234 5678 9012" not in payload_text

    assert entry.payload["content_hash"] == hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert entry.payload["content_length"] == len(content)
    assert entry.payload["citation_count"] == 2
    assert entry.payload["action_required"] is False


@pytest.mark.asyncio
async def test_record_retrieval_performed_never_stores_chunk_text(
    service: ComplianceLogService,
) -> None:
    """
    RETRIEVAL_PERFORMED must record source identifiers only -- never
    RetrievedContentDTO.content, the actual retrieved chunk text.
    """

    secret_chunk_text = "CONFIDENTIAL: client settlement amount is $4,200,000."

    retrieved = (
        RetrievedContentDTO(
            source=RetrievalSourceEnum.VECTOR,
            source_name="knowledge_base",
            content=secret_chunk_text,
            score=0.91,
        ),
    )

    entry = await service.record_retrieval_performed(
        request_id=uuid4(),
        user_id="user_1",
        tenant_id="user_1",
        thread_id="thread_1",
        agent_id="legal",
        retrieved=retrieved,
    )

    payload_text = repr(entry.payload)
    assert secret_chunk_text not in payload_text

    assert entry.payload["result_count"] == 1
    assert entry.payload["results"][0]["source_name"] == "knowledge_base"
    assert entry.payload["results"][0]["score"] == 0.91


@pytest.mark.asyncio
async def test_record_guardrail_fired_never_stores_matched_pii_substring(
    service: ComplianceLogService,
) -> None:
    """
    GUARDRAIL_FIRED must record category/action/count only -- never
    the matched PII substring itself, even though the caller
    (AIOrchestrator) knows the entity_type strings that fired.
    """

    entry = await service.record_guardrail_fired(
        request_id=uuid4(),
        user_id="user_1",
        tenant_id="user_1",
        conversation_id="conv_1",
        action="redacted",
        detection_count=1,
        categories=["IN_PAN"],
        harmful=False,
    )

    assert entry.payload == {
        "action": "redacted",
        "detection_count": 1,
        "categories": ["IN_PAN"],
        "harmful": False,
        "harmful_category": None,
    }
    # Category strings (entity types) are fine to store -- only the
    # matched text itself is forbidden, and there is no field here
    # that could carry it.
    assert "content" not in entry.payload
    assert "matched_text" not in entry.payload


@pytest.mark.asyncio
@pytest.mark.parametrize("answer_verified", [True, False, None])
async def test_record_agent_decision_stores_answer_verified(
    service: ComplianceLogService,
    answer_verified: bool | None,
) -> None:
    entry = await service.record_agent_decision(
        request_id=uuid4(),
        user_id="user_1",
        tenant_id="user_1",
        conversation_id="conv_1",
        agent_id="legal",
        decision_type="final",
        groundedness=0.2,
        relevance=0.3,
        answer_verified=answer_verified,
    )

    assert entry.event_type is ComplianceEventTypeEnum.AGENT_DECISION
    assert entry.payload["answer_verified"] is answer_verified
    assert entry.payload["groundedness"] == 0.2
    assert entry.payload["relevance"] == 0.3


@pytest.mark.asyncio
async def test_record_hitl_approval_decision_allows_missing_request_id(
    service: ComplianceLogService,
) -> None:
    """
    Unlike every other record_*() method, request_id is optional here
    -- see the method's own docstring for why.
    """

    entry = await service.record_hitl_approval_decision(
        user_id="approver_1",
        tenant_id="approver_1",
        agent_action_id="actn_1",
        approval_id="appr_1",
        decision_type="approve",
    )

    assert entry.request_id is None
    assert entry.resource_type == "agent_action"
    assert entry.resource_id == "actn_1"


@pytest.mark.asyncio
async def test_standalone_writer_opens_its_own_session_and_commits() -> None:
    session = MagicMock()
    session.commit = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    session_factory = MagicMock(return_value=session)

    writer = StandaloneComplianceLogWriter(session_factory=session_factory)

    # Patch the repository this writer constructs internally so no
    # real DB call happens -- this test is about session lifecycle
    # (open -> write -> commit), not persistence itself.
    with pytest.MonkeyPatch.context() as mp:
        repo = MagicMock()
        repo.create = AsyncMock(side_effect=lambda entity: entity)
        mp.setattr(
            "adapters.persistence.sqlalchemy.repositories.compliance_log.ComplianceLogRepository",
            lambda **kwargs: repo,
        )

        await writer.record_plan_created(
            request_id=uuid4(),
            user_id="user_1",
            tenant_id="user_1",
            conversation_id="conv_1",
            intent="general",
            mode="sequential",
            step_count=1,
        )

    session_factory.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_standalone_writer_swallows_failures_without_raising() -> None:
    """
    A compliance write failure must never take down the request it is
    observing (same "never blocks the caller" stance UsageService.record
    already takes) -- confirmed here with a session_factory that
    raises.
    """

    def _raise():
        raise RuntimeError("db unavailable")

    writer = StandaloneComplianceLogWriter(session_factory=_raise)

    await writer.record_plan_created(
        request_id=uuid4(),
        user_id="user_1",
        tenant_id="user_1",
        conversation_id="conv_1",
        intent="general",
        mode="sequential",
        step_count=1,
    )

    # No exception propagated -- the assertion is simply that this
    # line was reached.


# ---------------------------------------------------------------------------
# purge_older_than
#
# The retention purge -- destructive, irreversible, and never called
# automatically anywhere in this codebase (see the method's own
# docstring and scripts/python/purge_compliance_log.py, its only
# caller). These tests exist specifically to confirm the None default
# (config.compliance.ComplianceSettings.COMPLIANCE_LOG_RETENTION_DAYS)
# makes an accidental purge impossible.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purge_refuses_when_retention_days_is_none(
    service: ComplianceLogService,
    repository: MagicMock,
) -> None:
    """
    The safety guarantee this whole feature rests on: with the
    default settings value (None), purge_older_than() must refuse to
    run -- raise, delete nothing, never touch the repository's delete
    path.
    """

    repository.delete_older_than = AsyncMock()

    with pytest.raises(ValueError, match="COMPLIANCE_LOG_RETENTION_DAYS"):
        await service.purge_older_than(retention_days=None)

    repository.delete_older_than.assert_not_called()


@pytest.mark.asyncio
async def test_purge_refuses_non_positive_retention_days(
    service: ComplianceLogService,
    repository: MagicMock,
) -> None:
    repository.delete_older_than = AsyncMock()

    with pytest.raises(ValueError, match="positive integer"):
        await service.purge_older_than(retention_days=0)

    with pytest.raises(ValueError, match="positive integer"):
        await service.purge_older_than(retention_days=-30)

    repository.delete_older_than.assert_not_called()


@pytest.mark.asyncio
async def test_purge_deletes_when_retention_days_is_explicitly_set(
    service: ComplianceLogService,
    repository: MagicMock,
) -> None:
    """
    The capability itself: an explicit, non-None retention_days value
    (never a codebase-chosen default -- see COMPLIANCE_LOG_RETENTION_DAYS's
    docstring) does trigger a real delete, with the correct cutoff.
    """

    repository.delete_older_than = AsyncMock(return_value=42)

    deleted_count = await service.purge_older_than(retention_days=30)

    assert deleted_count == 42
    repository.delete_older_than.assert_awaited_once()

    cutoff = repository.delete_older_than.await_args.kwargs["cutoff"]
    expected_cutoff = datetime.now(UTC) - timedelta(days=30)
    # Allow a small tolerance for real wall-clock time elapsed during
    # the test itself.
    assert abs((cutoff - expected_cutoff).total_seconds()) < 5
