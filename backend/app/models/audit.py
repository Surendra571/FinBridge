"""
Audit Domain Models (Phase 11).
Persists cryptographically chained, tamper-evident, append-only audit events.
Enforces ORM-level immutability rules prohibiting updates and deletions.
Tracks periodic cryptographic integrity verification audits.
"""
import uuid
import hashlib
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    JSON,
    BigInteger,
    Integer,
    Boolean,
    Index,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, utc_now

GENESIS_HASH: str = "0" * 64


def compute_audit_hash(
    prev_hash: str,
    sequence_id: int,
    organization_id: str,
    event_type: str,
    entity_type: str,
    entity_id: Optional[str],
    actor_id: Optional[str],
    timestamp_iso: str,
    payload: Dict[str, Any],
    before_state: Optional[Dict[str, Any]] = None,
    after_state: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    model_version: Optional[str] = None,
    prompt_version: Optional[str] = None,
) -> str:
    """
    Computes deterministic SHA-256 hash chaining over canonical serialized fields.
    Guarantees that any post-creation tampering of event fields breaks the cryptographic chain.
    """
    canonical_payload = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"), default=str)
    canonical_before = json.dumps(before_state or {}, sort_keys=True, separators=(",", ":"), default=str)
    canonical_after = json.dumps(after_state or {}, sort_keys=True, separators=(",", ":"), default=str)

    data_elements = [
        prev_hash,
        str(sequence_id),
        str(organization_id),
        event_type,
        entity_type,
        str(entity_id or ""),
        str(actor_id or ""),
        timestamp_iso,
        canonical_payload,
        canonical_before,
        canonical_after,
        str(correlation_id or ""),
        str(model_version or ""),
        str(prompt_version or ""),
    ]
    canonical_string = "|".join(data_elements)
    return hashlib.sha256(canonical_string.encode("utf-8")).hexdigest()


class AuditEvent(Base):
    """
    Cryptographically chained, tamper-evident, append-only operational audit log.
    Records financial and systemic state changes with sequence numbers and SHA-256 chain hashes.
    """
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "sequence_id", name="uq_org_audit_sequence"),
        Index("ix_audit_events_org_seq", "organization_id", "sequence_id"),
        Index("ix_audit_events_org_action", "organization_id", "action"),
        Index("ix_audit_events_resource", "resource_type", "resource_id"),
        Index("ix_audit_events_correlation", "correlation_id"),
        Index("ix_audit_events_created_at", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    sequence_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_type: Mapped[str] = mapped_column(
        String(50),
        default="AI_AGENT",
        nullable=False,
    )  # USER, SYSTEM, AI_AGENT, INTEGRATION
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )

    # Core event & entity classifications
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="OPERATIONAL_EVENT",
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="SYSTEM",
        index=True,
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )

    # Backward compatibility attributes
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="OPERATIONAL_ACTION",
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="SYSTEM",
    )
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )

    # State capture & Details
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    before_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    after_state: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Correlation & Metadata
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    model_version: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    prompt_version: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Cryptographic Hash Chaining
    prev_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=GENESIS_HASH,
    )
    current_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=GENESIS_HASH,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )


# ------------------------------------------------------------------------------
# Immutability Protection: Restrict Application Permissions
# ------------------------------------------------------------------------------
@event.listens_for(AuditEvent, "before_update")
def enforce_audit_event_update_immutability(mapper: Any, connection: Any, target: AuditEvent) -> None:
    """Enforces that existing audit events can NEVER be updated."""
    raise PermissionError(
        f"IMMUTABILITY VIOLATION: AuditEvent {target.id} is an append-only cryptographic record and cannot be modified."
    )


@event.listens_for(AuditEvent, "before_delete")
def enforce_audit_event_delete_immutability(mapper: Any, connection: Any, target: AuditEvent) -> None:
    """Enforces that audit events can NEVER be deleted by application operations."""
    raise PermissionError(
        f"IMMUTABILITY VIOLATION: AuditEvent {target.id} is an append-only cryptographic record and cannot be deleted."
    )


class AuditIntegrityCheck(Base):
    """
    Records periodic and on-demand cryptographic verification scans of the audit trail.
    Identifies chain continuity, gaps, or data tampering.
    """
    __tablename__ = "audit_integrity_checks"
    __table_args__ = (
        Index("ix_audit_integrity_org_time", "organization_id", "check_timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    check_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    start_sequence_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
    )
    end_sequence_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
    )
    total_events_checked: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="VERIFIED",  # VERIFIED, TAMPERED, BROKEN_CHAIN, MISSING_EVENTS
    )
    broken_at_sequence_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    tampered_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )
    verification_duration_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    performed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
