"""
Pydantic Schemas for Audit Trail & Hash-Chained Cryptographic Integrity (Phase 11).
Defines request and response structures for audit exploration, event recording,
and cryptographic chain verification reporting.
"""
import uuid
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, Field


class AuditEventType(str, Enum):
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    STATEMENT_UPLOAD = "STATEMENT_UPLOAD"
    LEDGER_IMPORT = "LEDGER_IMPORT"
    TRANSACTION_NORMALIZATION = "TRANSACTION_NORMALIZATION"
    RECONCILIATION_RUN = "RECONCILIATION_RUN"
    AI_PROPOSAL = "AI_PROPOSAL"
    DETERMINISTIC_VALIDATION = "DETERMINISTIC_VALIDATION"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    APPROVAL = "APPROVAL"
    REJECTION = "REJECTION"
    ADJUSTMENT = "ADJUSTMENT"
    INTEGRATION_REQUEST = "INTEGRATION_REQUEST"
    RETRY = "RETRY"
    FAILURE_AND_RECOVERY = "FAILURE_AND_RECOVERY"


class AuditActorType(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI_AGENT = "AI_AGENT"
    INTEGRATION = "INTEGRATION"


class AuditEventCreateRequest(BaseModel):
    event_type: str = Field(..., description="Standardized audit event category")
    entity_type: str = Field(..., description="Target business entity type")
    entity_id: Optional[uuid.UUID] = Field(default=None, description="UUID of target entity")
    actor_type: str = Field(default="USER", description="Originating actor classification")
    actor_id: Optional[uuid.UUID] = Field(default=None, description="Identifier of the executing actor")
    action: Optional[str] = Field(default=None, description="Operational action name")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Structured event metadata & parameters")
    before_state: Optional[Dict[str, Any]] = Field(default=None, description="Entity state prior to modification")
    after_state: Optional[Dict[str, Any]] = Field(default=None, description="Entity state following modification")
    correlation_id: Optional[str] = Field(default=None, max_length=100, description="Distributed tracing identifier")
    model_version: Optional[str] = Field(default=None, max_length=100, description="AI model version if applicable")
    prompt_version: Optional[str] = Field(default=None, max_length=100, description="Prompt template version if applicable")
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None, max_length=255)


class AuditEventResponse(BaseModel):
    id: uuid.UUID
    sequence_id: int
    organization_id: uuid.UUID
    actor_type: str
    actor_id: Optional[uuid.UUID] = None
    event_type: str
    entity_type: str
    entity_id: Optional[uuid.UUID] = None
    action: str
    resource_type: str
    resource_id: Optional[uuid.UUID] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    prev_hash: str
    current_hash: str
    created_at: datetime


class AuditIntegrityVerificationResponse(BaseModel):
    status: str = Field(..., description="VERIFIED, TAMPERED, BROKEN_CHAIN, or MISSING_EVENTS")
    is_valid: bool = Field(..., description="True if cryptographic chain is completely unblemished")
    total_events_checked: int
    start_sequence_id: int
    end_sequence_id: int
    broken_at_sequence_id: Optional[int] = None
    tampered_event_id: Optional[uuid.UUID] = None
    verification_duration_ms: int
    details: Dict[str, Any] = Field(default_factory=dict)
    limitation_disclosure: str = Field(
        default=(
            "Cryptographic hash chaining detects any post-hoc field modification, sequence insertion, "
            "or record deletion across the audit trail. However, hash chaining alone cannot protect "
            "against an attacker with superuser database access who rewrites both the data and forward "
            "hashes unless external WORM storage (e.g. AWS S3 Object Lock) or trusted RFC 3161 "
            "timestamping anchors are applied."
        )
    )


class AuditIntegrityCheckResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    check_timestamp: datetime
    start_sequence_id: int
    end_sequence_id: int
    total_events_checked: int
    is_valid: bool
    status: str
    broken_at_sequence_id: Optional[int] = None
    tampered_event_id: Optional[uuid.UUID] = None
    verification_duration_ms: int
    details: Dict[str, Any] = Field(default_factory=dict)
    performed_by: Optional[uuid.UUID] = None


class AuditEventsListResponse(BaseModel):
    items: List[AuditEventResponse]
    total_count: int
    limit: int
    offset: int
