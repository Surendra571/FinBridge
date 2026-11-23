"""
Reconciliation Domain Pydantic v2 Schemas.
Configurable matching rules, candidate evaluations, validation results,
and execution run summaries.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ReconciliationConfig(BaseModel):
    """Configurable matching parameters for deterministic financial rules."""
    date_window_days: int = Field(default=5, ge=0, le=90, description="Maximum allowable difference between bank and ledger dates.")
    fee_tolerance: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0.00"), le=Decimal("500.00"), description="Maximum allowable amount variance for fee adjustment.")
    allow_fee_adjustment: bool = Field(default=False, description="Whether to allow matches with small fee variances.")
    require_reference_match: bool = Field(default=False, description="Strict mode requiring identical reference numbers.")
    direction_convention: Literal["INVERTED_CASH", "DIRECT_FLOW"] = Field(
        default="INVERTED_CASH",
        description="Accounting direction convention: INVERTED_CASH (Bank CREDIT = Ledger DEBIT) or DIRECT_FLOW."
    )
    min_description_similarity: Decimal = Field(
        default=Decimal("0.50"),
        ge=Decimal("0.00"),
        le=Decimal("1.00"),
        description="Minimum token/fuzzy similarity required when reference number is absent."
    )


class ReconciliationRunRequest(BaseModel):
    config: ReconciliationConfig = Field(default_factory=ReconciliationConfig)
    bank_account_id: Optional[uuid.UUID] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ValidationResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_valid: bool
    rule_name: str
    bank_total: Decimal
    ledger_total: Decimal
    calculated_variance: Decimal
    allowed_tolerance: Decimal
    currency_parity_passed: bool
    direction_parity_passed: bool
    amount_parity_passed: bool
    date_window_passed: bool
    unconsumed_check_passed: bool
    reversal_check_passed: bool
    failure_reason: Optional[str]
    validated_at: datetime


class MatchCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reconciliation_run_id: uuid.UUID
    bank_transaction_id: uuid.UUID
    ledger_entry_id: uuid.UUID
    candidate_source: str
    confidence_score: Decimal
    decision_status: str  # MATCHED, NEEDS_REVIEW, UNMATCHED, REJECTED
    rule_name: str
    explanation: str
    amount_variance: Decimal
    date_difference_days: int
    created_at: datetime
    validation: Optional[ValidationResultResponse] = None


class ReconciliationRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    run_type: str
    total_bank_candidates: int
    total_ledger_candidates: int
    matched_count: int
    needs_review_count: int
    unmatched_count: int
    execution_duration_ms: Optional[int]
    status: str
    configuration: Dict[str, Any]
    created_at: datetime
    completed_at: Optional[datetime]
    candidates: List[MatchCandidateResponse] = []


class MatchDetailsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reconciliation_run_id: uuid.UUID
    match_candidate_id: Optional[uuid.UUID]
    bank_transaction_id: uuid.UUID
    ledger_entry_id: uuid.UUID
    match_type: str
    bank_amount: Decimal
    ledger_amount: Decimal
    variance_amount: Decimal
    status: str
    reconciled_at: datetime

