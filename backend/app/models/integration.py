"""
Integrations & Reliability Domain Models (Phase 12).
Persists simulated external providers (Core Banking, ERP Ledger, Webhook Receivers),
outbound integration request logs, idempotency records, and exponential retry attempts.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    JSON,
    Integer,
    Boolean,
    Float,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, utc_now


class Integration(Base):
    """
    Configures simulated external financial providers (Core Banking, NetSuite/SAP ERP).
    Clearly labeled as SIMULATED integration entities.
    """
    __tablename__ = "integrations"
    __table_args__ = (
        Index("ix_integrations_org", "organization_id"),
        Index("ix_integrations_type", "provider_type"),
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
    provider_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )  # e.g. "SIMULATED_CORE_BANKING_CHASE", "SIMULATED_ERP_NETSUITE"
    provider_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # CORE_BANKING, ERP_LEDGER, WEBHOOK_RECEIVER
    base_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="https://simulated-api.finbridge.internal",
    )
    is_simulated: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )  # Always True for testing/simulated environments
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    health_status: Mapped[str] = mapped_column(
        String(50),
        default="HEALTHY",
        nullable=False,
    )  # HEALTHY, DEGRADED, UNHEALTHY
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    config: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class IntegrationRequest(Base):
    """
    Telemetry log of outbound requests and webhook invocations dispatched to integrations.
    Records request parameters, response status, latency, error classification, and DLQ status.
    """
    __tablename__ = "integration_requests"
    __table_args__ = (
        Index("ix_integration_requests_org", "organization_id", "created_at"),
        Index("ix_integration_requests_idempotency", "organization_id", "idempotency_key"),
        Index("ix_integration_requests_status", "status"),
        Index("ix_integration_requests_correlation", "correlation_id"),
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
    integration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integrations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    correlation_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    http_method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="POST",
    )
    request_headers: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    request_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    response_status: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    response_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    error_category: Mapped[str] = mapped_column(
        String(50),
        default="NONE",
        nullable=False,
    )  # NONE, RATE_LIMIT_429, SERVER_ERROR_500, CONNECTION_TIMEOUT, NETWORK_INTERRUPTION, ERP_WRITE_TIMEOUT_RECOVERED, WORKER_CRASH
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="COMPLETED",
        nullable=False,
    )  # PENDING, COMPLETED, FAILED, DEAD_LETTER
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    recovery_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )


class IdempotencyRecord(Base):
    """
    Prevents duplicate execution of financial transactions, writes, and webhooks.
    """
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_idempotency_per_org"),
        Index("ix_idempotency_org_key", "organization_id", "idempotency_key"),
        Index("ix_idempotency_expiry", "expires_at"),
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
    idempotency_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    request_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="IN_FLIGHT",
        nullable=False,
    )  # IN_FLIGHT, COMPLETED, FAILED
    response_code: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    response_body: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class RetryAttempt(Base):
    """
    Manages exponential backoff retries with randomized jitter for failed tasks.
    """
    __tablename__ = "retry_attempts"
    __table_args__ = (
        Index("ix_retry_attempts_pending", "next_retry_at"),
        Index("ix_retry_attempts_request", "integration_request_id"),
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
    integration_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integration_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        default=3,
        nullable=False,
    )
    backoff_delay_seconds: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    jitter_seconds: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    next_retry_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="PENDING",
        nullable=False,
    )  # PENDING, SUCCEEDED, EXHAUSTED, CANCELLED
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
