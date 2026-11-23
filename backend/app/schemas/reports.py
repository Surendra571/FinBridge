"""
Financial Reports & Analytics Schemas (Phase 13).
Strongly typed models for real-time dashboard metrics, currency-partitioned
aggregations, date-filtered reconciliation reports, and CSV exports.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ReportFilterParams(BaseModel):
    """Common filtering parameters for all financial reports."""
    start_date: Optional[date] = Field(None, description="Start date for reporting window (inclusive)")
    end_date: Optional[date] = Field(None, description="End date for reporting window (inclusive)")
    currency: Optional[str] = Field(None, description="Optional ISO currency code filter (e.g. USD, EUR)")
    format: Optional[str] = Field("json", description="Output format: json or csv")


class DashboardMetricsResponse(BaseModel):
    """
    Real-time dashboard metrics connected to active database records.
    Currency parity invariant: different currencies are never combined into a single scalar sum.
    """
    total_bank_transactions: int = Field(..., description="Total bank transactions recorded")
    matched_transactions: int = Field(..., description="Total reconciled bank transactions")
    pending_review: int = Field(..., description="Transactions pending proposal validation or manual review")
    unmatched_transactions: int = Field(..., description="Open unmatched transactions")
    reconciliation_rate: Decimal = Field(..., description="Percentage of reconciled transactions (0.00 to 100.00)")
    
    # Financial amounts strictly partitioned by currency code (e.g. {"USD": Decimal("125000.00"), "EUR": Decimal("45000.00")})
    total_reconciled_amount_by_currency: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Reconciled financial volume broken down by ISO currency code"
    )
    total_unreconciled_amount_by_currency: Dict[str, Decimal] = Field(
        default_factory=dict,
        description="Unreconciled financial volume broken down by ISO currency code"
    )
    
    calculation_basis: str = Field("CALCULATED_EXACT", description="Distinguishes exact calculations from estimates")
    as_of: datetime = Field(..., description="UTC timestamp of the calculation snapshot")
    organization_id: str = Field(..., description="Tenant organization UUID")
    base_currency: str = Field(..., description="Organization default base currency")


# ============================================================================
# REPORT 1: DAILY RECONCILIATION REPORT
# ============================================================================
class DailyReconciliationItem(BaseModel):
    date: date
    currency: str
    total_transactions: int
    matched_count: int
    pending_count: int
    unmatched_count: int
    reconciled_amount: Decimal
    unreconciled_amount: Decimal
    reconciliation_rate: Decimal
    calculation_basis: str = "CALCULATED_EXACT"


class DailyReconciliationResponse(BaseModel):
    items: List[DailyReconciliationItem]
    total_days: int
    currencies: List[str]
    calculation_basis: str = "CALCULATED_EXACT"


# ============================================================================
# REPORT 2: MONTHLY RECONCILIATION REPORT
# ============================================================================
class MonthlyReconciliationItem(BaseModel):
    period: str  # YYYY-MM
    currency: str
    total_transactions: int
    matched_count: int
    unmatched_count: int
    reconciled_amount: Decimal
    unreconciled_amount: Decimal
    reconciliation_rate: Decimal
    calculation_basis: str = "CALCULATED_EXACT"


class MonthlyReconciliationResponse(BaseModel):
    items: List[MonthlyReconciliationItem]
    total_months: int
    currencies: List[str]
    calculation_basis: str = "CALCULATED_EXACT"


# ============================================================================
# REPORT 3: UNMATCHED TRANSACTIONS REPORT
# ============================================================================
class UnmatchedTransactionItem(BaseModel):
    id: str
    source_type: str  # BANK_TRANSACTION or LEDGER_ENTRY
    record_date: date
    description: str
    reference_id: Optional[str] = None
    amount: Decimal
    currency: str
    direction: str  # DEBIT or CREDIT
    days_open: int
    aging_bucket: str  # <30_DAYS, 30-60_DAYS, 60-90_DAYS, 90+_DAYS


class UnmatchedTransactionsResponse(BaseModel):
    items: List[UnmatchedTransactionItem]
    total_unmatched_count: int
    unmatched_amounts_by_currency: Dict[str, Decimal]
    aging_summary: Dict[str, int]
    calculation_basis: str = "CALCULATED_EXACT"


# ============================================================================
# REPORT 4: BANK FEES & VARIANCES REPORT
# ============================================================================
class BankFeeItem(BaseModel):
    item_id: str
    record_date: date
    currency: str
    fee_or_variance_amount: Decimal
    fee_type: str  # VARIANCE_ADJUSTMENT, WIRE_FEE, DISCREPANCY
    description: str
    status: str  # APPROVED, PENDING_APPROVAL, RESOLVED
    maker_id: Optional[str] = None
    checker_id: Optional[str] = None


class BankFeesReportResponse(BaseModel):
    items: List[BankFeeItem]
    total_fee_count: int
    total_fee_amounts_by_currency: Dict[str, Decimal]
    calculation_basis: str = "CALCULATED_EXACT"


# ============================================================================
# REPORT 5: PENDING APPROVALS REPORT
# ============================================================================
class PendingApprovalItem(BaseModel):
    item_id: str
    item_type: str  # MANUAL_REVIEW or MAKER_CHECKER_ADJUSTMENT
    category: str
    priority: str
    currency: str
    amount: Decimal
    days_pending: int
    created_at: datetime
    assigned_to: Optional[str] = None
    requires_maker_checker: bool


class PendingApprovalsResponse(BaseModel):
    items: List[PendingApprovalItem]
    total_pending_count: int
    pending_amounts_by_currency: Dict[str, Decimal]
    priority_breakdown: Dict[str, int]
    calculation_basis: str = "CALCULATED_EXACT"


# ============================================================================
# REPORT 6: EXCEPTION SUMMARY REPORT
# ============================================================================
class ExceptionCategorySummary(BaseModel):
    category: str
    total_count: int
    pending_count: int
    resolved_count: int
    unresolved_count: int
    amounts_by_currency: Dict[str, Decimal]
    percentage_of_total: Decimal


class ExceptionSummaryResponse(BaseModel):
    categories: List[ExceptionCategorySummary]
    total_exceptions: int
    resolved_rate: Decimal
    calculation_basis: str = "CALCULATED_EXACT"


# ============================================================================
# REPORT 7: INTEGRATION FAILURE REPORT
# ============================================================================
class IntegrationFailureItem(BaseModel):
    provider_name: str
    provider_type: str
    endpoint: str
    total_requests: int
    success_count: int
    failure_count: int
    dead_letter_count: int
    recovered_count: int
    failure_breakdown: Dict[str, int]
    avg_latency_ms: float
    availability_rate: Decimal


class IntegrationFailureResponse(BaseModel):
    items: List[IntegrationFailureItem]
    total_requests: int
    total_failures: int
    total_dead_letters: int
    overall_availability_rate: Decimal
    calculation_basis: str = "CALCULATED_EXACT"


# ============================================================================
# REPORT 8: AUDIT ACTIVITY REPORT
# ============================================================================
class AuditActivityReportResponse(BaseModel):
    total_events: int
    events_by_actor_type: Dict[str, int]
    events_by_event_type: Dict[str, int]
    integrity_status: str
    last_verified_at: Optional[datetime] = None
    last_verified_sequence_id: Optional[int] = None
    earliest_event_at: Optional[datetime] = None
    latest_event_at: Optional[datetime] = None
    calculation_basis: str = "CALCULATED_EXACT"
