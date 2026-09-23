"""
All enumerations used across the application.

Str-based enums provide JSON-friendly serialization while keeping
application state explicit and type-safe.
"""

from enum import StrEnum


class JWTAlgorithmEnum(StrEnum):
    """
    Supported JWT signing algorithms.
    """

    HS256 = "HS256"
    HS384 = "HS384"
    HS512 = "HS512"

    RS256 = "RS256"
    RS384 = "RS384"
    RS512 = "RS512"


class EnvironmentEnum(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class CacheBackendEnum(StrEnum):
    MEMORY = "memory"
    REDIS = "redis"


class GenderEnum(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class MessageRoleEnum(StrEnum):
    """
    Supported chat message roles.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    TEST = "test"


class EventTypeEnum(StrEnum):
    """
    Supported conversation event types.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RETRIEVAL = "retrieval"
    RERANK = "rerank"
    PLANNER = "planner"


class SortOrderEnum(StrEnum):
    ASC = "asc"
    DESC = "desc"


class LLMProviderEnum(StrEnum):
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    LOCAL = "local"


class GroqModelEnum(StrEnum):
    # CONFIRMED DEAD as of 2026-09-14: every real call with this model
    # returns groq.NotFoundError (404 model_not_found) on this
    # project's Groq account/API key -- Groq has been rotating out
    # older Llama 3.1 8B variants. Not a code bug, not a quality
    # question -- do not select this for GROQ_MODEL/JUDGE_MODEL until
    # re-verified against the live Groq API (its catalog can change
    # independently of this codebase). Left in place rather than
    # deleted: MODEL_CONTEXT_WINDOWS (agents/prompts/token_budget.py)
    # and a unit test still reference it, and Groq could re-add an
    # equivalent small model under this or another name later.
    LLAMA_3_1_8B = "llama-3.1-8b-instant"
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GPT_OSS_20B = "openai/gpt-oss-20b"


class LLMMODELEnum(StrEnum):
    QWEN3_4B = "qwen3:4b"
    QWEN3_8B = "qwen3:8b"


class AgentTypeEnum(StrEnum):
    """
    Supported agent types.
    """

    LEGAL = "legal"
    CONTRACT = "contract"


class LibraryStatusEnum(StrEnum):
    """
    Upload file processing status.
    """

    UPLOADED = "uploaded"
    READY = "ready"
    FAILED = "failed"


class KnowledgeStatusEnum(StrEnum):
    """
    Knowledge source processing status.
    """

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class LibrarySourceEnum(StrEnum):
    FILE = "file"
    WEBSITE = "website"
    TEXT = "text"
    CLOUD_STORAGE = "cloud_storage"


class KnowledgeSourceEnum(StrEnum):
    FILE = "file"
    WEBSITE = "website"
    TEXT = "text"
    CLOUD_STORAGE = "cloud_storage"


class StorageTypeEnum(StrEnum):
    """
    Supported storage providers.
    """

    LOCAL = "local"
    S3 = "s3"
    AZURE_BLOB = "azure_blob"
    GCS = "gcs"
    MINIO = "minio"


class IntentEnum(StrEnum):
    """
    Supported planning intents.
    """

    GENERAL = "general"
    LEGAL_RESEARCH = "legal_research"
    CONTRACT_REVIEW = "contract_review"
    CONTRACT_ANALYSIS = "contract_analysis"
    CLAUSE_EXTRACTION = "clause_extraction"
    RISK_ANALYSIS = "risk_analysis"


class ExecutionModeEnum(StrEnum):
    """
    Supported execution modes.

    The execution mode is part of the planning contract.
    Runtime topology is derived from plan dependencies and
    executed by LangGraph.
    """

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


class ExecutionStatusEnum(StrEnum):
    """
    Runtime execution status.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_FOR_APPROVAL = "waiting_for_approval"


class RetrievalSourceEnum(StrEnum):
    """
    Sources of retrieved content.
    """

    WEB = "web"
    DOCUMENT = "document"
    VECTOR = "vector"
    DATABASE = "database"
    MEMORY = "memory"


class AttachmentTypeEnum(StrEnum):
    """
    Supported attachment types.
    """

    PDF = "pdf"
    DOCX = "docx"
    IMAGE = "image"
    TEXT = "text"
    OTHER = "other"


class RequestSourceEnum(StrEnum):
    """
    Sources of orchestration requests.
    """

    CHAT = "chat"
    API = "api"
    TOOL = "tool"


# ============================================================================
# Authorization
# ============================================================================


class AuthorizationDecisionEnum(StrEnum):
    """
    Result of an authorization evaluation.

    This represents whether an actor is permitted to perform
    a requested operation.
    """

    ALLOW = "allow"
    DENY = "deny"


class ApprovalPolicyDecisionEnum(StrEnum):
    """
    Result of evaluating whether an authorized action requires
    human approval.

    This is a policy decision, not the lifecycle state of an
    approval request.
    """

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"


# ============================================================================
# Agent Actions
# ============================================================================


class ActionTypeEnum(StrEnum):
    """
    Categories of executable actions.

    AGENT_CALL represents agent-to-agent execution and allows
    the same action authorization path to be used for both
    tool actions and agent interactions.
    """

    GENERAL = "general"
    READ = "read"
    ANALYZE = "analyze"
    GENERATE = "generate"
    UPDATE = "update"
    DELETE = "delete"
    SEND = "send"
    SUBMIT = "submit"
    EXTERNAL = "external"
    AGENT_CALL = "agent_call"
    TOOL_CALL = "tool"


class AgentActionStatusEnum(StrEnum):
    """
    Lifecycle state of a persisted executable agent action.
    """

    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


# ============================================================================
# Human Approval
# ============================================================================


class ApprovalStatusEnum(StrEnum):
    """
    Lifecycle state of a persisted human approval request.

    An Approval record exists only when human approval is required.
    """

    WAITING = "waiting"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"
    EXPIRED = "expired"


class ApprovalDecisionEnum(StrEnum):
    """
    Decision submitted by a human for an approval request.

    This is intentionally separate from ApprovalStatusEnum:
    a decision is an input, while status is persisted state.
    """

    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class HitlResumeStatusEnum(StrEnum):
    """
    Outcome of resuming a paused execution after an approval decision.

    Reported alongside the decision, which is committed before resume
    runs and stands whatever this outcome is.
    """

    COMPLETED = "completed"
    FAILED = "failed"
    NOT_RESUMED = "not_resumed"


# ============================================================================
# Actors
# ============================================================================


class ActorTypeEnum(StrEnum):
    """
    Actor responsible for initiating an executable action.
    """

    USER = "user"
    AGENT = "agent"


# ============================================================================
# Compliance Log
# ============================================================================


class ComplianceEventTypeEnum(StrEnum):
    """
    Kind of fact recorded in the compliance_log table -- one row per
    discrete auditable event in a request's lifecycle, not a status.

    See application/services/compliance_log.py for the no-raw-content
    rule each event type's payload must follow (never verbatim
    message/response text, retrieved chunk text, or matched PII
    substrings -- identifiers, hashes, and counts only).
    """

    REQUEST_RECEIVED = "request_received"
    RETRIEVAL_PERFORMED = "retrieval_performed"
    PLAN_CREATED = "plan_created"
    TOOL_CALL_EXECUTED = "tool_call_executed"
    AGENT_DECISION = "agent_decision"
    GUARDRAIL_FIRED = "guardrail_fired"
    HITL_APPROVAL_DECISION = "hitl_approval_decision"
    RESPONSE_RETURNED = "response_returned"
    # A change to, or use of, a user's long-term memory. The specific
    # operation is in the payload (see UserMemoryOperationEnum). One
    # event type rather than one per operation: a native Postgres enum
    # value can never be removed, so this stays minimal.
    MEMORY_OPERATION = "memory_operation"


# ============================================================================
# User memory
# ============================================================================


class UserMemoryKindEnum(StrEnum):
    """
    Category of a durable, user-stated fact.

    Phase 1 stores only facts that describe the user's own working
    preferences/profile. Nothing here identifies a client or a matter.
    """

    PREFERENCE = "preference"
    PROFILE = "profile"
    FACT = "fact"


class UserMemoryStatusEnum(StrEnum):
    """
    Lifecycle state of a user memory.

    Only ACTIVE rows are ever injected into a prompt. PENDING is
    reserved for facts awaiting the user's confirmation; SUPERSEDED
    marks a fact replaced by a newer one.
    """

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    PENDING = "pending"


class UserMemoryScopeEnum(StrEnum):
    """
    What a memory is scoped to.

    Only USER exists today, and user_memories carries a CHECK
    constraint that rejects anything else. A "matter" scope requires a
    matters model with hard isolation between matters and is deliberately
    absent: widening this needs a migration, not just a new member here.
    """

    USER = "user"


class UserMemoryOperationEnum(StrEnum):
    """
    What happened to a user's long-term memory, as recorded in the
    compliance log's MEMORY_OPERATION payload.

    The compliance log is insert-only and retained indefinitely by
    default, so it can never honour an erasure request. These events
    therefore carry identifiers, counts and a content hash only -- never
    memory text.
    """

    STORED = "stored"
    UPDATED = "updated"
    SUPERSEDED = "superseded"
    DELETED = "deleted"
    DELETED_ALL = "deleted_all"
    PURGED_EXPIRED = "purged_expired"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    INJECTED = "injected"
