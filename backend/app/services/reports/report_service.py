"""
Financial Reports & Analytics Service (Phase 13).
Executes database aggregations, currency-segregated rollups,
aging analysis, exception categorizations, and CSV stream exports.
"""
import csv
import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Tuple, Any

from sqlalchemy import select, func, and_, or_, case, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.financial import BankTransaction, LedgerEntry
from app.models.reconciliation import ReconciliationMatch, ReconciliationRun
from app.models.review import ManualReviewItem, AdjustmentProposal
from app.models.integration import Integration, IntegrationRequest
from app.models.audit import AuditEvent, AuditIntegrityCheck
from app.schemas.reports import (
    DashboardMetricsResponse,
    DailyReconciliationItem,
    DailyReconciliationResponse,
    MonthlyReconciliationItem,
    MonthlyReconciliationResponse,
    UnmatchedTransactionItem,
    UnmatchedTransactionsResponse,
    BankFeeItem,
    BankFeesReportResponse,
    PendingApprovalItem,
    PendingApprovalsResponse,
    ExceptionCategorySummary,
    ExceptionSummaryResponse,
    IntegrationFailureItem,
    IntegrationFailureResponse,
    AuditActivityReportResponse,
)


class ReportService:
    """Enterprise financial reporting and analytics engine."""

    # ------------------------------------------------------------------------
    # DASHBOARD REAL-TIME METRICS
    # ------------------------------------------------------------------------
    @classmethod
    async def get_dashboard_metrics(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        base_currency: str = "USD",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> DashboardMetricsResponse:
        """
        Aggregate live database metrics for the active organization.
        Currency parity invariant: Different currencies are NEVER added together.
        """
        # Bank transactions query
        tx_filters = [BankTransaction.organization_id == org_id]
        if start_date:
            tx_filters.append(BankTransaction.booking_date >= start_date)
        if end_date:
            tx_filters.append(BankTransaction.booking_date <= end_date)

        # 1. Total counts by status
        status_stmt = (
            select(
                BankTransaction.reconciliation_status,
                func.count(BankTransaction.id),
            )
            .where(and_(*tx_filters))
            .group_by(BankTransaction.reconciliation_status)
        )
        status_res = await db.execute(status_stmt)
        status_counts = {row[0]: row[1] for row in status_res.fetchall()}

        matched_count = status_counts.get("RECONCILED", 0)
        unmatched_count = status_counts.get("UNMATCHED", 0)
        proposed_count = status_counts.get("PROPOSED", 0)
        excluded_count = status_counts.get("EXCLUDED", 0)
        total_tx = matched_count + unmatched_count + proposed_count + excluded_count

        # Pending review: either proposed transactions or pending manual review items
        review_stmt = (
            select(func.count(ManualReviewItem.id))
            .where(
                and_(
                    ManualReviewItem.organization_id == org_id,
                    ManualReviewItem.status.in_(["PENDING", "IN_REVIEW"]),
                )
            )
        )
        review_res = await db.execute(review_stmt)
        manual_pending = review_res.scalar_one_or_none() or 0
        total_pending = max(proposed_count, manual_pending)

        # Reconciliation rate percentage
        if total_tx > 0:
            rec_rate = (Decimal(matched_count) / Decimal(total_tx) * Decimal("100.00")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            rec_rate = Decimal("0.00")

        # 2. Currency-segregated financial amounts
        reconciled_curr_stmt = (
            select(
                BankTransaction.currency,
                func.sum(BankTransaction.amount),
            )
            .where(
                and_(
                    *tx_filters,
                    BankTransaction.reconciliation_status == "RECONCILED",
                )
            )
            .group_by(BankTransaction.currency)
        )
        rec_res = await db.execute(reconciled_curr_stmt)
        reconciled_by_curr: Dict[str, Decimal] = {
            row[0]: Decimal(str(row[1] or "0.00")).quantize(Decimal("0.01"))
            for row in rec_res.fetchall()
        }

        unreconciled_curr_stmt = (
            select(
                BankTransaction.currency,
                func.sum(BankTransaction.amount),
            )
            .where(
                and_(
                    *tx_filters,
                    BankTransaction.reconciliation_status.in_(["UNMATCHED", "PROPOSED"]),
                )
            )
            .group_by(BankTransaction.currency)
        )
        unrec_res = await db.execute(unreconciled_curr_stmt)
        unreconciled_by_curr: Dict[str, Decimal] = {
            row[0]: Decimal(str(row[1] or "0.00")).quantize(Decimal("0.01"))
            for row in unrec_res.fetchall()
        }

        return DashboardMetricsResponse(
            total_bank_transactions=total_tx,
            matched_transactions=matched_count,
            pending_review=total_pending,
            unmatched_transactions=unmatched_count,
            reconciliation_rate=rec_rate,
            total_reconciled_amount_by_currency=reconciled_by_curr,
            total_unreconciled_amount_by_currency=unreconciled_by_curr,
            calculation_basis="CALCULATED_EXACT",
            as_of=datetime.now(timezone.utc),
            organization_id=str(org_id),
            base_currency=base_currency,
        )

    # ------------------------------------------------------------------------
    # REPORT 1: DAILY RECONCILIATION REPORT
    # ------------------------------------------------------------------------
    @classmethod
    async def get_daily_report(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        currency_filter: Optional[str] = None,
    ) -> DailyReconciliationResponse:
        """Daily grouping of transactions, matches, amounts, and rates per currency."""
        filters = [BankTransaction.organization_id == org_id]
        if start_date:
            filters.append(BankTransaction.booking_date >= start_date)
        if end_date:
            filters.append(BankTransaction.booking_date <= end_date)
        if currency_filter:
            filters.append(BankTransaction.currency == currency_filter.upper())

        stmt = (
            select(
                BankTransaction.booking_date,
                BankTransaction.currency,
                func.count(BankTransaction.id).label("total"),
                func.sum(
                    case((BankTransaction.reconciliation_status == "RECONCILED", 1), else_=0)
                ).label("matched"),
                func.sum(
                    case((BankTransaction.reconciliation_status == "PROPOSED", 1), else_=0)
                ).label("pending"),
                func.sum(
                    case((BankTransaction.reconciliation_status == "UNMATCHED", 1), else_=0)
                ).label("unmatched"),
                func.sum(
                    case(
                        (BankTransaction.reconciliation_status == "RECONCILED", BankTransaction.amount),
                        else_=Decimal("0.00"),
                    )
                ).label("reconciled_amt"),
                func.sum(
                    case(
                        (BankTransaction.reconciliation_status.in_(["UNMATCHED", "PROPOSED"]), BankTransaction.amount),
                        else_=Decimal("0.00"),
                    )
                ).label("unreconciled_amt"),
            )
            .where(and_(*filters))
            .group_by(BankTransaction.booking_date, BankTransaction.currency)
            .order_by(desc(BankTransaction.booking_date), BankTransaction.currency)
        )
        rows = (await db.execute(stmt)).fetchall()

        items: List[DailyReconciliationItem] = []
        currencies_seen = set()
        dates_seen = set()

        for r in rows:
            b_date, curr, total, matched, pending, unmatched, rec_amt, unrec_amt = r
            currencies_seen.add(curr)
            dates_seen.add(b_date)
            total_int = int(total or 0)
            matched_int = int(matched or 0)
            rec_rate = (
                (Decimal(matched_int) / Decimal(total_int) * Decimal("100.00")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if total_int > 0
                else Decimal("0.00")
            )
            items.append(
                DailyReconciliationItem(
                    date=b_date,
                    currency=curr,
                    total_transactions=total_int,
                    matched_count=matched_int,
                    pending_count=int(pending or 0),
                    unmatched_count=int(unmatched or 0),
                    reconciled_amount=Decimal(str(rec_amt or "0.00")).quantize(Decimal("0.01")),
                    unreconciled_amount=Decimal(str(unrec_amt or "0.00")).quantize(Decimal("0.01")),
                    reconciliation_rate=rec_rate,
                    calculation_basis="CALCULATED_EXACT",
                )
            )

        return DailyReconciliationResponse(
            items=items,
            total_days=len(dates_seen),
            currencies=sorted(list(currencies_seen)),
            calculation_basis="CALCULATED_EXACT",
        )

    # ------------------------------------------------------------------------
    # REPORT 2: MONTHLY RECONCILIATION REPORT
    # ------------------------------------------------------------------------
    @classmethod
    async def get_monthly_report(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        currency_filter: Optional[str] = None,
    ) -> MonthlyReconciliationResponse:
        """Monthly aggregation of reconciliation volume and success rates."""
        daily_resp = await cls.get_daily_report(db, org_id, start_date, end_date, currency_filter)
        
        # Aggregate monthly from daily items to avoid dialect-specific SQL date formatting
        monthly_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for item in daily_resp.items:
            month_key = item.date.strftime("%Y-%m")
            curr = item.currency
            key = (month_key, curr)
            if key not in monthly_map:
                monthly_map[key] = {
                    "total": 0,
                    "matched": 0,
                    "unmatched": 0,
                    "rec_amt": Decimal("0.00"),
                    "unrec_amt": Decimal("0.00"),
                }
            monthly_map[key]["total"] += item.total_transactions
            monthly_map[key]["matched"] += item.matched_count
            monthly_map[key]["unmatched"] += item.unmatched_count
            monthly_map[key]["rec_amt"] += item.reconciled_amount
            monthly_map[key]["unrec_amt"] += item.unreconciled_amount

        items: List[MonthlyReconciliationItem] = []
        months_seen = set()
        currencies_seen = set()

        for (month_key, curr), data in sorted(monthly_map.items(), reverse=True):
            months_seen.add(month_key)
            currencies_seen.add(curr)
            total = data["total"]
            matched = data["matched"]
            rec_rate = (
                (Decimal(matched) / Decimal(total) * Decimal("100.00")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if total > 0
                else Decimal("0.00")
            )
            items.append(
                MonthlyReconciliationItem(
                    period=month_key,
                    currency=curr,
                    total_transactions=total,
                    matched_count=matched,
                    unmatched_count=data["unmatched"],
                    reconciled_amount=data["rec_amt"].quantize(Decimal("0.01")),
                    unreconciled_amount=data["unrec_amt"].quantize(Decimal("0.01")),
                    reconciliation_rate=rec_rate,
                    calculation_basis="CALCULATED_EXACT",
                )
            )

        return MonthlyReconciliationResponse(
            items=items,
            total_months=len(months_seen),
            currencies=sorted(list(currencies_seen)),
            calculation_basis="CALCULATED_EXACT",
        )

    # ------------------------------------------------------------------------
    # REPORT 3: UNMATCHED TRANSACTIONS REPORT
    # ------------------------------------------------------------------------
    @classmethod
    async def get_unmatched_report(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        currency_filter: Optional[str] = None,
    ) -> UnmatchedTransactionsResponse:
        """Lists and ages open unmatched bank transactions and ledger entries."""
        today = date.today()
        items: List[UnmatchedTransactionItem] = []
        amounts_by_curr: Dict[str, Decimal] = {}
        aging_summary = {"<30_DAYS": 0, "30-60_DAYS": 0, "60-90_DAYS": 0, "90+_DAYS": 0}

        # 1. Unmatched Bank Transactions
        b_filters = [
            BankTransaction.organization_id == org_id,
            BankTransaction.reconciliation_status == "UNMATCHED",
        ]
        if start_date:
            b_filters.append(BankTransaction.booking_date >= start_date)
        if end_date:
            b_filters.append(BankTransaction.booking_date <= end_date)
        if currency_filter:
            b_filters.append(BankTransaction.currency == currency_filter.upper())

        b_stmt = select(BankTransaction).where(and_(*b_filters)).order_by(desc(BankTransaction.booking_date))
        b_txs = (await db.execute(b_stmt)).scalars().all()

        for tx in b_txs:
            days_open = max(0, (today - tx.booking_date).days)
            if days_open < 30:
                bucket = "<30_DAYS"
            elif days_open <= 60:
                bucket = "30-60_DAYS"
            elif days_open <= 90:
                bucket = "60-90_DAYS"
            else:
                bucket = "90+_DAYS"

            aging_summary[bucket] += 1
            curr = tx.currency
            amounts_by_curr[curr] = amounts_by_curr.get(curr, Decimal("0.00")) + Decimal(str(tx.amount))

            items.append(
                UnmatchedTransactionItem(
                    id=str(tx.id),
                    source_type="BANK_TRANSACTION",
                    record_date=tx.booking_date,
                    description=tx.normalized_description,
                    reference_id=tx.reference_id,
                    amount=Decimal(str(tx.amount)).quantize(Decimal("0.01")),
                    currency=curr,
                    direction=tx.direction,
                    days_open=days_open,
                    aging_bucket=bucket,
                )
            )

        # 2. Unmatched Ledger Entries
        l_filters = [
            LedgerEntry.organization_id == org_id,
            LedgerEntry.reconciliation_status == "UNRECONCILED",
        ]
        if start_date:
            l_filters.append(LedgerEntry.posting_date >= start_date)
        if end_date:
            l_filters.append(LedgerEntry.posting_date <= end_date)
        if currency_filter:
            l_filters.append(LedgerEntry.currency == currency_filter.upper())

        l_stmt = select(LedgerEntry).where(and_(*l_filters)).order_by(desc(LedgerEntry.posting_date))
        l_entries = (await db.execute(l_stmt)).scalars().all()

        for entry in l_entries:
            days_open = max(0, (today - entry.posting_date).days)
            if days_open < 30:
                bucket = "<30_DAYS"
            elif days_open <= 60:
                bucket = "30-60_DAYS"
            elif days_open <= 90:
                bucket = "60-90_DAYS"
            else:
                bucket = "90+_DAYS"

            aging_summary[bucket] += 1
            curr = entry.currency
            amounts_by_curr[curr] = amounts_by_curr.get(curr, Decimal("0.00")) + Decimal(str(entry.amount))

            items.append(
                UnmatchedTransactionItem(
                    id=str(entry.id),
                    source_type="LEDGER_ENTRY",
                    record_date=entry.posting_date,
                    description=entry.description,
                    reference_id=entry.reference_number,
                    amount=Decimal(str(entry.amount)).quantize(Decimal("0.01")),
                    currency=curr,
                    direction=entry.direction,
                    days_open=days_open,
                    aging_bucket=bucket,
                )
            )

        # Sort combined items by record_date desc
        items.sort(key=lambda x: x.record_date, reverse=True)

        return UnmatchedTransactionsResponse(
            items=items,
            total_unmatched_count=len(items),
            unmatched_amounts_by_currency={k: v.quantize(Decimal("0.01")) for k, v in amounts_by_curr.items()},
            aging_summary=aging_summary,
            calculation_basis="CALCULATED_EXACT",
        )

    # ------------------------------------------------------------------------
    # REPORT 4: BANK FEES & VARIANCES REPORT
    # ------------------------------------------------------------------------
    @classmethod
    async def get_bank_fees_report(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        currency_filter: Optional[str] = None,
    ) -> BankFeesReportResponse:
        """Documents variance adjustments, fee write-offs, and wire charges."""
        items: List[BankFeeItem] = []
        amounts_by_curr: Dict[str, Decimal] = {}

        # 1. From AdjustmentProposals (maker-checker variances)
        adj_filters = [AdjustmentProposal.organization_id == org_id]
        if currency_filter:
            pass  # will check currency on joined bank transaction
        
        adj_stmt = (
            select(AdjustmentProposal, BankTransaction)
            .join(BankTransaction, AdjustmentProposal.proposed_bank_id == BankTransaction.id)
            .where(and_(*adj_filters))
            .order_by(desc(AdjustmentProposal.created_at))
        )
        adj_results = (await db.execute(adj_stmt)).fetchall()

        for prop, b_tx in adj_results:
            prop_date = prop.created_at.date() if prop.created_at else date.today()
            if start_date and prop_date < start_date:
                continue
            if end_date and prop_date > end_date:
                continue
            if currency_filter and b_tx.currency != currency_filter.upper():
                continue

            amt = Decimal(str(prop.adjustment_amount)).quantize(Decimal("0.01"))
            curr = b_tx.currency
            amounts_by_curr[curr] = amounts_by_curr.get(curr, Decimal("0.00")) + amt

            items.append(
                BankFeeItem(
                    item_id=str(prop.id),
                    record_date=prop_date,
                    currency=curr,
                    fee_or_variance_amount=amt,
                    fee_type="VARIANCE_ADJUSTMENT",
                    description=prop.adjustment_reason,
                    status=prop.status,
                    maker_id=str(prop.maker_id),
                    checker_id=str(prop.checker_id) if prop.checker_id else None,
                )
            )

        # 2. From ReconciliationMatches with non-zero variance
        match_stmt = (
            select(ReconciliationMatch, BankTransaction)
            .join(BankTransaction, ReconciliationMatch.bank_transaction_id == BankTransaction.id)
            .where(
                and_(
                    ReconciliationMatch.organization_id == org_id,
                    ReconciliationMatch.variance_amount > Decimal("0.00"),
                )
            )
            .order_by(desc(ReconciliationMatch.reconciled_at))
        )
        match_results = (await db.execute(match_stmt)).fetchall()

        for match, b_tx in match_results:
            m_date = match.reconciled_at.date() if match.reconciled_at else date.today()
            if start_date and m_date < start_date:
                continue
            if end_date and m_date > end_date:
                continue
            if currency_filter and b_tx.currency != currency_filter.upper():
                continue

            amt = Decimal(str(match.variance_amount)).quantize(Decimal("0.01"))
            curr = b_tx.currency
            amounts_by_curr[curr] = amounts_by_curr.get(curr, Decimal("0.00")) + amt

            items.append(
                BankFeeItem(
                    item_id=str(match.id),
                    record_date=m_date,
                    currency=curr,
                    fee_or_variance_amount=amt,
                    fee_type="MATCH_TOLERANCE_VARIANCE",
                    description=f"Automated match variance against ledger ({b_tx.normalized_description[:30]})",
                    status="RESOLVED",
                    maker_id=None,
                    checker_id=None,
                )
            )

        return BankFeesReportResponse(
            items=items,
            total_fee_count=len(items),
            total_fee_amounts_by_currency={k: v.quantize(Decimal("0.01")) for k, v in amounts_by_curr.items()},
            calculation_basis="CALCULATED_EXACT",
        )

    # ------------------------------------------------------------------------
    # REPORT 5: PENDING APPROVALS REPORT
    # ------------------------------------------------------------------------
    @classmethod
    async def get_pending_approvals_report(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        priority_filter: Optional[str] = None,
    ) -> PendingApprovalsResponse:
        """Queue of review items and maker-checker adjustments awaiting approval."""
        today = date.today()
        items: List[PendingApprovalItem] = []
        amounts_by_curr: Dict[str, Decimal] = {}
        priority_breakdown = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

        # 1. Pending ManualReviewItems
        rev_stmt = (
            select(ManualReviewItem, BankTransaction)
            .outerjoin(BankTransaction, ManualReviewItem.bank_transaction_id == BankTransaction.id)
            .where(
                and_(
                    ManualReviewItem.organization_id == org_id,
                    ManualReviewItem.status.in_(["PENDING", "IN_REVIEW"]),
                )
            )
            .order_by(desc(ManualReviewItem.created_at))
        )
        rev_results = (await db.execute(rev_stmt)).fetchall()

        for item, b_tx in rev_results:
            prio = item.priority or "MEDIUM"
            if priority_filter and prio != priority_filter.upper():
                continue
            priority_breakdown[prio] = priority_breakdown.get(prio, 0) + 1

            amt = Decimal(str(b_tx.amount)) if b_tx else Decimal("0.00")
            curr = b_tx.currency if b_tx else "USD"
            amounts_by_curr[curr] = amounts_by_curr.get(curr, Decimal("0.00")) + amt

            days_pending = max(0, (today - item.created_at.date()).days) if item.created_at else 0

            items.append(
                PendingApprovalItem(
                    item_id=str(item.id),
                    item_type="MANUAL_REVIEW",
                    category=item.category,
                    priority=prio,
                    currency=curr,
                    amount=amt.quantize(Decimal("0.01")),
                    days_pending=days_pending,
                    created_at=item.created_at,
                    assigned_to=str(item.assigned_to) if item.assigned_to else None,
                    requires_maker_checker=item.requires_maker_checker,
                )
            )

        # 2. Pending Adjustment Proposals
        adj_stmt = (
            select(AdjustmentProposal, BankTransaction)
            .join(BankTransaction, AdjustmentProposal.proposed_bank_id == BankTransaction.id)
            .where(
                and_(
                    AdjustmentProposal.organization_id == org_id,
                    AdjustmentProposal.status == "PENDING_APPROVAL",
                )
            )
        )
        adj_results = (await db.execute(adj_stmt)).fetchall()

        for prop, b_tx in adj_results:
            priority_breakdown["HIGH"] = priority_breakdown.get("HIGH", 0) + 1
            amt = Decimal(str(prop.adjustment_amount))
            curr = b_tx.currency
            amounts_by_curr[curr] = amounts_by_curr.get(curr, Decimal("0.00")) + amt
            days_pending = max(0, (today - prop.created_at.date()).days) if prop.created_at else 0

            items.append(
                PendingApprovalItem(
                    item_id=str(prop.id),
                    item_type="MAKER_CHECKER_ADJUSTMENT",
                    category="VARIANCE_PROPOSAL",
                    priority="HIGH",
                    currency=curr,
                    amount=amt.quantize(Decimal("0.01")),
                    days_pending=days_pending,
                    created_at=prop.created_at,
                    assigned_to=None,
                    requires_maker_checker=True,
                )
            )

        return PendingApprovalsResponse(
            items=items,
            total_pending_count=len(items),
            pending_amounts_by_currency={k: v.quantize(Decimal("0.01")) for k, v in amounts_by_curr.items()},
            priority_breakdown=priority_breakdown,
            calculation_basis="CALCULATED_EXACT",
        )

    # ------------------------------------------------------------------------
    # REPORT 6: EXCEPTION SUMMARY REPORT
    # ------------------------------------------------------------------------
    @classmethod
    async def get_exception_summary_report(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ExceptionSummaryResponse:
        """Breakdown of exceptions across the 9 standard reconciliation categories."""
        STANDARD_CATEGORIES = [
            "LOW_CONFIDENCE",
            "MULTIPLE_MATCHES",
            "AMOUNT_MISMATCH",
            "MISSING_LEDGER_ENTRY",
            "MISSING_BANK_TRANSACTION",
            "DUPLICATE_TRANSACTION",
            "CURRENCY_MISMATCH",
            "POSSIBLE_REVERSAL",
            "POSSIBLE_REFUND",
        ]

        filters = [ManualReviewItem.organization_id == org_id]
        if start_date:
            filters.append(ManualReviewItem.created_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc))
        if end_date:
            filters.append(ManualReviewItem.created_at <= datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc))

        stmt = (
            select(
                ManualReviewItem.category,
                ManualReviewItem.status,
                BankTransaction.currency,
                func.count(ManualReviewItem.id),
                func.sum(BankTransaction.amount),
            )
            .outerjoin(BankTransaction, ManualReviewItem.bank_transaction_id == BankTransaction.id)
            .where(and_(*filters))
            .group_by(ManualReviewItem.category, ManualReviewItem.status, BankTransaction.currency)
        )
        rows = (await db.execute(stmt)).fetchall()

        cat_data: Dict[str, Dict[str, Any]] = {
            cat: {
                "total": 0,
                "pending": 0,
                "resolved": 0,
                "unresolved": 0,
                "currencies": {},
            }
            for cat in STANDARD_CATEGORIES
        }

        total_all_exceptions = 0
        total_resolved = 0

        for category, status, currency, count, sum_amt in rows:
            if category not in cat_data:
                cat_data[category] = {
                    "total": 0,
                    "pending": 0,
                    "resolved": 0,
                    "unresolved": 0,
                    "currencies": {},
                }

            c_info = cat_data[category]
            c_info["total"] += count
            total_all_exceptions += count

            if status in ["APPROVED", "REJECTED"]:
                c_info["resolved"] += count
                total_resolved += count
            elif status in ["PENDING", "IN_REVIEW"]:
                c_info["pending"] += count
            else:
                c_info["unresolved"] += count

            if currency and sum_amt:
                curr_map = c_info["currencies"]
                curr_map[currency] = curr_map.get(currency, Decimal("0.00")) + Decimal(str(sum_amt))

        summaries: List[ExceptionCategorySummary] = []
        for cat in STANDARD_CATEGORIES:
            data = cat_data[cat]
            tot = data["total"]
            pct = (
                (Decimal(tot) / Decimal(total_all_exceptions) * Decimal("100.00")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if total_all_exceptions > 0
                else Decimal("0.00")
            )
            summaries.append(
                ExceptionCategorySummary(
                    category=cat,
                    total_count=tot,
                    pending_count=data["pending"],
                    resolved_count=data["resolved"],
                    unresolved_count=data["unresolved"],
                    amounts_by_currency={k: v.quantize(Decimal("0.01")) for k, v in data["currencies"].items()},
                    percentage_of_total=pct,
                )
            )

        resolved_rate = (
            (Decimal(total_resolved) / Decimal(total_all_exceptions) * Decimal("100.00")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if total_all_exceptions > 0
            else Decimal("0.00")
        )

        return ExceptionSummaryResponse(
            categories=summaries,
            total_exceptions=total_all_exceptions,
            resolved_rate=resolved_rate,
            calculation_basis="CALCULATED_EXACT",
        )

    # ------------------------------------------------------------------------
    # REPORT 7: INTEGRATION FAILURE REPORT
    # ------------------------------------------------------------------------
    @classmethod
    async def get_integration_failure_report(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> IntegrationFailureResponse:
        """Aggregates simulated external provider failure rates, DLQ count, and latencies."""
        filters = [IntegrationRequest.organization_id == org_id]
        if start_date:
            filters.append(IntegrationRequest.created_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc))
        if end_date:
            filters.append(IntegrationRequest.created_at <= datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc))

        stmt = (
            select(
                Integration.provider_name,
                Integration.provider_type,
                IntegrationRequest.endpoint,
                func.count(IntegrationRequest.id).label("total"),
                func.sum(case((IntegrationRequest.status == "COMPLETED", 1), else_=0)).label("successes"),
                func.sum(case((IntegrationRequest.status == "FAILED", 1), else_=0)).label("failures"),
                func.sum(case((IntegrationRequest.status == "DEAD_LETTER", 1), else_=0)).label("dead_letters"),
                func.sum(
                    case((IntegrationRequest.error_category == "ERP_WRITE_TIMEOUT_RECOVERED", 1), else_=0)
                ).label("recovered"),
                func.avg(IntegrationRequest.latency_ms).label("avg_latency"),
            )
            .join(Integration, IntegrationRequest.integration_id == Integration.id)
            .where(and_(*filters))
            .group_by(Integration.provider_name, Integration.provider_type, IntegrationRequest.endpoint)
        )
        rows = (await db.execute(stmt)).fetchall()

        # Detailed breakdown of error categories per provider
        err_stmt = (
            select(
                Integration.provider_name,
                IntegrationRequest.endpoint,
                IntegrationRequest.error_category,
                func.count(IntegrationRequest.id),
            )
            .join(Integration, IntegrationRequest.integration_id == Integration.id)
            .where(and_(*filters, IntegrationRequest.error_category != "NONE"))
            .group_by(Integration.provider_name, IntegrationRequest.endpoint, IntegrationRequest.error_category)
        )
        err_rows = (await db.execute(err_stmt)).fetchall()
        err_breakdown: Dict[Tuple[str, str], Dict[str, int]] = {}
        for p_name, endpoint, err_cat, cnt in err_rows:
            key = (p_name, endpoint)
            if key not in err_breakdown:
                err_breakdown[key] = {}
            err_breakdown[key][err_cat] = cnt

        items: List[IntegrationFailureItem] = []
        tot_all_reqs = 0
        tot_all_fails = 0
        tot_all_dlq = 0
        tot_all_success = 0

        for r in rows:
            p_name, p_type, endpoint, total, successes, failures, dead_letters, recovered, avg_lat = r
            t_int = int(total or 0)
            s_int = int(successes or 0)
            f_int = int(failures or 0)
            d_int = int(dead_letters or 0)
            r_int = int(recovered or 0)

            tot_all_reqs += t_int
            tot_all_fails += f_int
            tot_all_dlq += d_int
            tot_all_success += s_int

            avail_rate = (
                (Decimal(s_int) / Decimal(t_int) * Decimal("100.00")).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if t_int > 0
                else Decimal("100.00")
            )

            items.append(
                IntegrationFailureItem(
                    provider_name=p_name,
                    provider_type=p_type,
                    endpoint=endpoint,
                    total_requests=t_int,
                    success_count=s_int,
                    failure_count=f_int,
                    dead_letter_count=d_int,
                    recovered_count=r_int,
                    failure_breakdown=err_breakdown.get((p_name, endpoint), {}),
                    avg_latency_ms=round(float(avg_lat or 0.0), 2),
                    availability_rate=avail_rate,
                )
            )

        overall_avail = (
            (Decimal(tot_all_success) / Decimal(tot_all_reqs) * Decimal("100.00")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if tot_all_reqs > 0
            else Decimal("100.00")
        )

        return IntegrationFailureResponse(
            items=items,
            total_requests=tot_all_reqs,
            total_failures=tot_all_fails,
            total_dead_letters=tot_all_dlq,
            overall_availability_rate=overall_avail,
            calculation_basis="CALCULATED_EXACT",
        )

    # ------------------------------------------------------------------------
    # REPORT 8: AUDIT ACTIVITY REPORT
    # ------------------------------------------------------------------------
    @classmethod
    async def get_audit_activity_report(
        cls,
        db: AsyncSession,
        org_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AuditActivityReportResponse:
        """Compliance and cryptographic verification status of the immutable audit log."""
        filters = [AuditEvent.organization_id == org_id]
        if start_date:
            filters.append(AuditEvent.created_at >= datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc))
        if end_date:
            filters.append(AuditEvent.created_at <= datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc))

        # 1. Total and earliest/latest timestamps
        agg_stmt = select(
            func.count(AuditEvent.id),
            func.min(AuditEvent.created_at),
            func.max(AuditEvent.created_at),
        ).where(and_(*filters))
        total_events, earliest, latest = (await db.execute(agg_stmt)).fetchone() or (0, None, None)

        # 2. Events by actor type
        actor_stmt = (
            select(AuditEvent.actor_type, func.count(AuditEvent.id))
            .where(and_(*filters))
            .group_by(AuditEvent.actor_type)
        )
        actor_rows = (await db.execute(actor_stmt)).fetchall()
        actors_map = {row[0]: row[1] for row in actor_rows}

        # 3. Events by event type
        event_type_stmt = (
            select(AuditEvent.event_type, func.count(AuditEvent.id))
            .where(and_(*filters))
            .group_by(AuditEvent.event_type)
        )
        etype_rows = (await db.execute(event_type_stmt)).fetchall()
        etype_map = {row[0]: row[1] for row in etype_rows}

        # 4. Cryptographic integrity check record
        check_stmt = (
            select(AuditIntegrityCheck)
            .where(AuditIntegrityCheck.organization_id == org_id)
            .order_by(desc(AuditIntegrityCheck.check_timestamp))
            .limit(1)
        )
        last_check = (await db.execute(check_stmt)).scalars().first()

        integrity_status = last_check.status if last_check else "CHAIN_INTACT"
        last_verified_at = last_check.check_timestamp if last_check else None
        last_seq = last_check.end_sequence_id if last_check else None

        return AuditActivityReportResponse(
            total_events=int(total_events or 0),
            events_by_actor_type=actors_map,
            events_by_event_type=etype_map,
            integrity_status=integrity_status,
            last_verified_at=last_verified_at,
            last_verified_sequence_id=last_seq,
            earliest_event_at=earliest,
            latest_event_at=latest,
            calculation_basis="CALCULATED_EXACT",
        )

    # ------------------------------------------------------------------------
    # CSV GENERATION HELPERS
    # ------------------------------------------------------------------------
    @classmethod
    def generate_daily_report_csv(cls, data: DailyReconciliationResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Date",
            "Currency",
            "Total Transactions",
            "Matched Count",
            "Pending Count",
            "Unmatched Count",
            "Reconciled Amount",
            "Unreconciled Amount",
            "Reconciliation Rate (%)",
            "Calculation Basis",
        ])
        for it in data.items:
            writer.writerow([
                it.date.isoformat(),
                it.currency,
                it.total_transactions,
                it.matched_count,
                it.pending_count,
                it.unmatched_count,
                f"{it.reconciled_amount:.2f}",
                f"{it.unreconciled_amount:.2f}",
                f"{it.reconciliation_rate:.2f}",
                it.calculation_basis,
            ])
        return output.getvalue()

    @classmethod
    def generate_monthly_report_csv(cls, data: MonthlyReconciliationResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Period (Month)",
            "Currency",
            "Total Transactions",
            "Matched Count",
            "Unmatched Count",
            "Reconciled Amount",
            "Unreconciled Amount",
            "Reconciliation Rate (%)",
            "Calculation Basis",
        ])
        for it in data.items:
            writer.writerow([
                it.period,
                it.currency,
                it.total_transactions,
                it.matched_count,
                it.unmatched_count,
                f"{it.reconciled_amount:.2f}",
                f"{it.unreconciled_amount:.2f}",
                f"{it.reconciliation_rate:.2f}",
                it.calculation_basis,
            ])
        return output.getvalue()

    @classmethod
    def generate_unmatched_report_csv(cls, data: UnmatchedTransactionsResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Item ID",
            "Source Type",
            "Record Date",
            "Currency",
            "Amount",
            "Direction",
            "Days Open",
            "Aging Bucket",
            "Reference ID",
            "Description",
            "Calculation Basis",
        ])
        for it in data.items:
            writer.writerow([
                it.id,
                it.source_type,
                it.record_date.isoformat(),
                it.currency,
                f"{it.amount:.2f}",
                it.direction,
                it.days_open,
                it.aging_bucket,
                it.reference_id or "",
                it.description,
                data.calculation_basis,
            ])
        return output.getvalue()

    @classmethod
    def generate_bank_fees_report_csv(cls, data: BankFeesReportResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Item ID",
            "Record Date",
            "Currency",
            "Fee / Variance Amount",
            "Fee Type",
            "Status",
            "Description",
            "Maker ID",
            "Checker ID",
            "Calculation Basis",
        ])
        for it in data.items:
            writer.writerow([
                it.item_id,
                it.record_date.isoformat(),
                it.currency,
                f"{it.fee_or_variance_amount:.2f}",
                it.fee_type,
                it.status,
                it.description,
                it.maker_id or "",
                it.checker_id or "",
                data.calculation_basis,
            ])
        return output.getvalue()

    @classmethod
    def generate_pending_approvals_report_csv(cls, data: PendingApprovalsResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Item ID",
            "Item Type",
            "Category",
            "Priority",
            "Currency",
            "Amount",
            "Days Pending",
            "Requires Maker-Checker",
            "Created At (UTC)",
            "Assigned To",
            "Calculation Basis",
        ])
        for it in data.items:
            writer.writerow([
                it.item_id,
                it.item_type,
                it.category,
                it.priority,
                it.currency,
                f"{it.amount:.2f}",
                it.days_pending,
                "YES" if it.requires_maker_checker else "NO",
                it.created_at.isoformat() if it.created_at else "",
                it.assigned_to or "UNASSIGNED",
                data.calculation_basis,
            ])
        return output.getvalue()

    @classmethod
    def generate_exception_summary_csv(cls, data: ExceptionSummaryResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Category",
            "Total Exceptions",
            "Pending Count",
            "Resolved Count",
            "Unresolved Count",
            "Share of Total (%)",
            "Amounts by Currency",
            "Calculation Basis",
        ])
        for it in data.categories:
            curr_str = "; ".join([f"{k}: {v:.2f}" for k, v in it.amounts_by_currency.items()]) or "0.00"
            writer.writerow([
                it.category,
                it.total_count,
                it.pending_count,
                it.resolved_count,
                it.unresolved_count,
                f"{it.percentage_of_total:.2f}",
                curr_str,
                data.calculation_basis,
            ])
        return output.getvalue()

    @classmethod
    def generate_integration_failure_csv(cls, data: IntegrationFailureResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Provider Name",
            "Provider Type",
            "Endpoint",
            "Total Requests",
            "Success Count",
            "Failure Count",
            "Dead Letter Count",
            "Recovered Count",
            "Avg Latency (ms)",
            "Availability Rate (%)",
            "Calculation Basis",
        ])
        for it in data.items:
            writer.writerow([
                it.provider_name,
                it.provider_type,
                it.endpoint,
                it.total_requests,
                it.success_count,
                it.failure_count,
                it.dead_letter_count,
                it.recovered_count,
                f"{it.avg_latency_ms:.2f}",
                f"{it.availability_rate:.2f}",
                data.calculation_basis,
            ])
        return output.getvalue()

    @classmethod
    def generate_audit_activity_csv(cls, data: AuditActivityReportResponse) -> str:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Metric", "Value"])
        writer.writerow(["Total Audit Events", data.total_events])
        writer.writerow(["Cryptographic Integrity Status", data.integrity_status])
        writer.writerow(["Last Verified At", data.last_verified_at.isoformat() if data.last_verified_at else "NEVER"])
        writer.writerow(["Last Verified Sequence ID", data.last_verified_sequence_id or "N/A"])
        writer.writerow(["Earliest Event Timestamp", data.earliest_event_at.isoformat() if data.earliest_event_at else "N/A"])
        writer.writerow(["Latest Event Timestamp", data.latest_event_at.isoformat() if data.latest_event_at else "N/A"])
        writer.writerow(["Calculation Basis", data.calculation_basis])
        writer.writerow([])
        writer.writerow(["Actor Type", "Event Count"])
        for actor, cnt in data.events_by_actor_type.items():
            writer.writerow([actor, cnt])
        writer.writerow([])
        writer.writerow(["Event Type", "Event Count"])
        for etype, cnt in data.events_by_event_type.items():
            writer.writerow([etype, cnt])
        return output.getvalue()
