"""
Human Review and Maker-Checker Domain Models (Phase 10).
Manages manual review queue, investigation notes, maker-checker financial
adjustment proposals, and audit records for human-in-the-loop verification.
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
    JSON,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, utc_now


class ManualReviewItem(Base):
    """
    Item requiring human review in the reconciliation queue.
    Classified by categories (e.g. LOW_CONFIDENCE, AMOUNT_MISMATCH, REVERSAL).
    """
    __tablename__ = "manual_reviews"
    __table_args__ = (
        Index("ix_manual_reviews_org_status", "organization_id", "status"),
        Index("ix_manual_reviews_category", "organization_id", "category"),
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
    bank_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    match_candidate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("match_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reconciliation_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("reconciliation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Categories:
    # LOW_CONFIDENCE, MULTIPLE_MATCHES, AMOUNT_MISMATCH, MISSING_LEDGER_ENTRY,
    # MISSING_BANK_TRANSACTION, DUPLICATE_TRANSACTION, CURRENCY_MISMATCH,
    # POSSIBLE_REVERSAL, POSSIBLE_REFUND
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # Status: PENDING, IN_REVIEW, APPROVED, REJECTED, UNRESOLVED, INVESTIGATION_REQUESTED
    status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING",
        nullable=False,
        index=True,
    )

    # Priority: LOW, MEDIUM, HIGH, CRITICAL
    priority: Mapped[str] = mapped_column(
        String(20),
        default="MEDIUM",
        nullable=False,
    )

    requires_maker_checker: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    maker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    checker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Resolution details
    resolution_action: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # APPROVED_PROPOSAL, REJECTED_PROPOSAL, REMAPPED_MATCH, MARKED_UNRESOLVED, INVESTIGATION_PENDING
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    selected_ledger_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("ledger_entries.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    notes: Mapped[List["ReviewNote"]] = relationship(
        "ReviewNote",
        back_populates="review_item",
        cascade="all, delete-orphan",
    )
    adjustment_proposals: Mapped[List["AdjustmentProposal"]] = relationship(
        "AdjustmentProposal",
        back_populates="review_item",
        cascade="all, delete-orphan",
    )


class ReviewNote(Base):
    """
    Immutable investigation notes and reviewer observations.
    """
    __tablename__ = "review_notes"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    manual_review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manual_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    note_type: Mapped[str] = mapped_column(
        String(30),
        default="GENERAL",
        nullable=False,
    )  # GENERAL, INVESTIGATION_REQUEST, APPROVAL_JUSTIFICATION, REJECTION_REASON
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    review_item: Mapped["ManualReviewItem"] = relationship(
        "ManualReviewItem",
        back_populates="notes",
    )


class AdjustmentProposal(Base):
    """
    Maker-checker financial adjustment proposal for variances or fee disputes.
    Enforces that maker_id != checker_id on final approval.
    """
    __tablename__ = "adjustment_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    manual_review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("manual_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    maker_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    checker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposed_bank_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bank_transactions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    proposed_ledger_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ledger_entries.id", ondelete="RESTRICT"),
        nullable=False,
    )
    adjustment_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
    )
    adjustment_reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING_APPROVAL",
        nullable=False,
    )  # PENDING_APPROVAL, APPROVED, REJECTED
    decision_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    review_item: Mapped["ManualReviewItem"] = relationship(
        "ManualReviewItem",
        back_populates="adjustment_proposals",
    )
