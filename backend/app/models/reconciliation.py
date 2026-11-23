"""
Reconciliation Domain Models.
Persists execution runs, candidate pairings, validation gate results,
and permanent verified reconciliation bindings.
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Numeric,
    ForeignKey,
    Integer,
    Text,
    BigInteger,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, utc_now


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    triggered_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    run_type: Mapped[str] = mapped_column(
        String(50),
        default="DETERMINISTIC_TIER1",
        nullable=False,
    )
    total_bank_candidates: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_ledger_candidates: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    matched_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    needs_review_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    unmatched_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    execution_duration_ms: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="COMPLETED",
        nullable=False,
    )  # IN_PROGRESS, COMPLETED, FAILED, CANCELLED
    configuration: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    candidates: Mapped[List["MatchCandidate"]] = relationship(
        "MatchCandidate",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    matches: Mapped[List["ReconciliationMatch"]] = relationship(
        "ReconciliationMatch",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class MatchCandidate(Base):
    __tablename__ = "match_candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bank_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ledger_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_entries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    candidate_source: Mapped[str] = mapped_column(
        String(50),
        default="DETERMINISTIC_TIER1",
        nullable=False,
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("1.0000"),
        nullable=False,
    )
    decision_status: Mapped[str] = mapped_column(
        String(30),
        default="MATCHED",
        nullable=False,
        index=True,
    )  # MATCHED, NEEDS_REVIEW, UNMATCHED, REJECTED
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    amount_variance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    date_difference_days: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    run: Mapped["ReconciliationRun"] = relationship(
        "ReconciliationRun",
        back_populates="candidates",
    )
    validation_results: Mapped[List["ValidationResult"]] = relationship(
        "ValidationResult",
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class ReconciliationMatch(Base):
    __tablename__ = "reconciliation_matches"
    __table_args__ = (
        UniqueConstraint("bank_transaction_id", name="uq_reconciled_bank_tx"),
        UniqueConstraint("ledger_entry_id", name="uq_reconciled_ledger_entry"),
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
    reconciliation_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    match_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("match_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    bank_transaction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ledger_entry_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_entries.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    match_type: Mapped[str] = mapped_column(
        String(30),
        default="ONE_TO_ONE",
        nullable=False,
    )
    bank_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    ledger_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    variance_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="AUTO_RECONCILED",
        nullable=False,
    )  # AUTO_RECONCILED, PENDING_APPROVAL, RECONCILED, REJECTED
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    run: Mapped["ReconciliationRun"] = relationship(
        "ReconciliationRun",
        back_populates="matches",
    )


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    match_candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("match_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_valid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    rule_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    bank_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    ledger_total: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    calculated_variance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    allowed_tolerance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    currency_parity_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    direction_parity_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    amount_parity_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    date_window_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    unconsumed_check_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    reversal_check_passed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    candidate: Mapped["MatchCandidate"] = relationship(
        "MatchCandidate",
        back_populates="validation_results",
    )

