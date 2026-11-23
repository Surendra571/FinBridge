"""
Pydantic Schemas for Human Review & Maker-Checker Workflow (Phase 10).
Defines request/response contracts for review queue filtering, workspace inspection,
reviewer decision actions, note logs, and maker-checker adjustment proposals.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class ReviewCategory(str, Enum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    MULTIPLE_MATCHES = "MULTIPLE_MATCHES"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    MISSING_LEDGER_ENTRY = "MISSING_LEDGER_ENTRY"
    MISSING_BANK_TRANSACTION = "MISSING_BANK_TRANSACTION"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    POSSIBLE_REVERSAL = "POSSIBLE_REVERSAL"
    POSSIBLE_REFUND = "POSSIBLE_REFUND"


class ReviewStatus(str, Enum):
    PENDING = "PENDING"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"
    INVESTIGATION_REQUESTED = "INVESTIGATION_REQUESTED"


class ReviewPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Action Requests
class ApproveMatchRequest(BaseModel):
    review_notes: Optional[str] = Field(default=None, max_length=1000)


class RejectMatchRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class MarkUnresolvedRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=1000)


class RemapCandidateRequest(BaseModel):
    ledger_entry_id: uuid.UUID
    reason: str = Field(..., min_length=3, max_length=1000)


class AddNoteRequest(BaseModel):
    note_type: str = Field(default="GENERAL", pattern="^(GENERAL|INVESTIGATION_REQUEST|APPROVAL_JUSTIFICATION|REJECTION_REASON)$")
    content: str = Field(..., min_length=2, max_length=2000)


class RequestInvestigationRequest(BaseModel):
    investigation_notes: str = Field(..., min_length=5, max_length=2000)
    assign_to: Optional[uuid.UUID] = None


class ProposeAdjustmentRequest(BaseModel):
    adjustment_amount: Decimal = Field(..., ge=Decimal("0.00"), description="Disputed variance amount")
    adjustment_reason: str = Field(..., min_length=5, max_length=255)
    target_ledger_id: uuid.UUID


class DecideAdjustmentRequest(BaseModel):
    approved: bool
    decision_notes: Optional[str] = Field(default=None, max_length=1000)


# Responses
class ReviewNoteResponse(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    note_type: str
    content: str
    created_at: datetime


class AdjustmentProposalResponse(BaseModel):
    id: uuid.UUID
    maker_id: uuid.UUID
    checker_id: Optional[uuid.UUID] = None
    proposed_bank_id: uuid.UUID
    proposed_ledger_id: uuid.UUID
    adjustment_amount: Decimal
    adjustment_reason: str
    status: str
    decision_notes: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None


class ReviewQueueItemResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    category: str
    status: str
    priority: str
    requires_maker_checker: bool
    bank_transaction_id: Optional[uuid.UUID] = None
    bank_booking_date: Optional[date] = None
    bank_amount: Optional[Decimal] = None
    bank_currency: Optional[str] = None
    bank_description: Optional[str] = None
    candidate_ledger_id: Optional[uuid.UUID] = None
    ledger_amount: Optional[Decimal] = None
    ledger_description: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    created_at: datetime
    assigned_to: Optional[uuid.UUID] = None


class ReviewWorkspaceDetailResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    category: str
    status: str
    priority: str
    requires_maker_checker: bool
    maker_id: Optional[uuid.UUID] = None
    checker_id: Optional[uuid.UUID] = None

    # Bank Transaction Details (Raw + Normalized)
    bank_transaction: Optional[Dict[str, Any]] = None

    # Proposed Candidate Ledger Entry
    proposed_candidate: Optional[Dict[str, Any]] = None

    # Alternative Ledger Candidates
    alternative_candidates: List[Dict[str, Any]] = []

    # AI Reasoning & Signals
    ai_explanation: Optional[str] = None
    ai_confidence_score: Optional[Decimal] = None
    ai_signals: List[str] = []
    ai_potential_concerns: List[str] = []

    # Deterministic Rule Validation Checklist
    deterministic_validation: Optional[Dict[str, Any]] = None

    # Previous Reconciliation Activity & Audit History
    audit_history: List[Dict[str, Any]] = []

    # Investigation Notes
    notes: List[ReviewNoteResponse] = []

    # Active Maker-Checker Adjustment Proposals
    adjustment_proposals: List[AdjustmentProposalResponse] = []

    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_action: Optional[str] = None
    resolution_notes: Optional[str] = None
