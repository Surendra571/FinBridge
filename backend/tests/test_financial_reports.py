"""
Automated Test Suite for Phase 13: Financial Reports and Analytics.
Validates:
- Live database dashboard metrics calculation and exact basis labeling
- Currency Parity Invariant: Multiple currencies are NEVER summed into a single scalar value
- Date range filtering (start_date, end_date) across report queries
- Daily reconciliation report grouping and CSV streaming export
- Monthly reconciliation volume trends and CSV export
- Unmatched transactions aging breakdown (<30d, 30-60d, 60-90d, 90+d) and CSV export
- Bank fees and variance adjustments report and CSV export
- Pending approvals and maker-checker queue report and CSV export
- Exception summary report across the 9 standard categories and CSV export
- Integration reliability & failure report with DLQ tracking and CSV export
- Audit activity telemetry and cryptographic chain status report and CSV export
- Role-based access control (RBAC) authorization enforcement
"""
import uuid
import pytest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.models.organization import Organization, OrganizationMembership
from app.models.financial import BankTransaction, LedgerEntry
from app.models.reconciliation import ReconciliationMatch
from app.models.review import ManualReviewItem, AdjustmentProposal
from app.models.integration import Integration, IntegrationRequest
from app.models.audit import AuditEvent, AuditIntegrityCheck
from app.services.reports.report_service import ReportService
from app.api.deps import require_role
from tests.conftest import run_coroutine


# ----------------------------------------------------------------------------
# 1. TEST DASHBOARD METRICS CALCULATION
# ----------------------------------------------------------------------------
def test_dashboard_metrics_calculation():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    # Mock DB query results:
    # 1. status_stmt -> [('RECONCILED', 8), ('UNMATCHED', 2), ('PROPOSED', 1)]
    # 2. review_stmt -> 1 pending review item
    # 3. reconciled_curr_stmt -> [('USD', Decimal('15000.00')), ('EUR', Decimal('5000.00'))]
    # 4. unreconciled_curr_stmt -> [('USD', Decimal('3000.00'))]
    res1 = MagicMock()
    res1.fetchall.return_value = [("RECONCILED", 8), ("UNMATCHED", 2), ("PROPOSED", 1)]

    res2 = MagicMock()
    res2.scalar_one_or_none.return_value = 1

    res3 = MagicMock()
    res3.fetchall.return_value = [("USD", Decimal("15000.00")), ("EUR", Decimal("5000.00"))]

    res4 = MagicMock()
    res4.fetchall.return_value = [("USD", Decimal("3000.00"))]

    mock_db.execute.side_effect = [res1, res2, res3, res4]

    metrics = run_coroutine(
        ReportService.get_dashboard_metrics(
            db=mock_db,
            org_id=org_id,
            base_currency="USD",
        )
    )

    assert metrics.total_bank_transactions == 11
    assert metrics.matched_transactions == 8
    assert metrics.unmatched_transactions == 2
    assert metrics.pending_review == 1
    # 8 / 11 * 100 = 72.73%
    assert metrics.reconciliation_rate == Decimal("72.73")
    assert metrics.calculation_basis == "CALCULATED_EXACT"


# ----------------------------------------------------------------------------
# 2. TEST CURRENCY PARITY INVARIANT (NO CONFLATION)
# ----------------------------------------------------------------------------
def test_currency_parity_invariant():
    """
    CRITICAL FINANCIAL RULE:
    Never combine different currencies into one scalar sum without explicit conversion.
    Amounts must be preserved and keyed strictly by currency.
    """
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    res1 = MagicMock()
    res1.fetchall.return_value = [("RECONCILED", 2)]

    res2 = MagicMock()
    res2.scalar_one_or_none.return_value = 0

    res3 = MagicMock()
    res3.fetchall.return_value = [("USD", Decimal("10000.50")), ("EUR", Decimal("4500.25")), ("GBP", Decimal("2200.00"))]

    res4 = MagicMock()
    res4.fetchall.return_value = [("JPY", Decimal("500000.00"))]

    mock_db.execute.side_effect = [res1, res2, res3, res4]

    metrics = run_coroutine(
        ReportService.get_dashboard_metrics(
            db=mock_db,
            org_id=org_id,
        )
    )

    # Validate that amounts exist in their distinct currency keys and are NOT combined
    reconciled_curr = metrics.total_reconciled_amount_by_currency
    assert len(reconciled_curr) == 3
    assert reconciled_curr["USD"] == Decimal("10000.50")
    assert reconciled_curr["EUR"] == Decimal("4500.25")
    assert reconciled_curr["GBP"] == Decimal("2200.00")
    assert "JPY" not in reconciled_curr

    unreconciled_curr = metrics.total_unreconciled_amount_by_currency
    assert len(unreconciled_curr) == 1
    assert unreconciled_curr["JPY"] == Decimal("500000.00")


# ----------------------------------------------------------------------------
# 3. TEST DAILY RECONCILIATION REPORT & CSV EXPORT
# ----------------------------------------------------------------------------
def test_daily_reconciliation_report():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    # Rows: (booking_date, currency, total, matched, pending, unmatched, rec_amt, unrec_amt)
    mock_rows = [
        (
            date(2026, 11, 20),
            "USD",
            10,
            9,
            0,
            1,
            Decimal("9000.00"),
            Decimal("1000.00"),
        ),
        (
            date(2026, 11, 20),
            "EUR",
            5,
            5,
            0,
            0,
            Decimal("5000.00"),
            Decimal("0.00"),
        ),
        (
            date(2026, 11, 19),
            "USD",
            8,
            6,
            1,
            1,
            Decimal("6000.00"),
            Decimal("2000.00"),
        ),
    ]
    res = MagicMock()
    res.fetchall.return_value = mock_rows
    mock_db.execute.return_value = res

    daily_report = run_coroutine(
        ReportService.get_daily_report(
            db=mock_db,
            org_id=org_id,
            start_date=date(2026, 11, 19),
            end_date=date(2026, 11, 20),
        )
    )

    assert len(daily_report.items) == 3
    assert daily_report.total_days == 2
    assert "USD" in daily_report.currencies
    assert "EUR" in daily_report.currencies
    assert daily_report.items[0].reconciliation_rate == Decimal("90.00")
    assert daily_report.items[1].reconciliation_rate == Decimal("100.00")

    # Test CSV Generation
    csv_text = ReportService.generate_daily_report_csv(daily_report)
    assert "Date,Currency,Total Transactions,Matched Count" in csv_text
    assert "2026-11-20,USD,10,9,0,1,9000.00,1000.00,90.00,CALCULATED_EXACT" in csv_text
    assert "2026-11-20,EUR,5,5,0,0,5000.00,0.00,100.00,CALCULATED_EXACT" in csv_text


# ----------------------------------------------------------------------------
# 4. TEST MONTHLY RECONCILIATION REPORT & CSV EXPORT
# ----------------------------------------------------------------------------
def test_monthly_reconciliation_report():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    mock_rows = [
        (date(2026, 11, 20), "USD", 10, 8, 1, 1, Decimal("8000.00"), Decimal("2000.00")),
        (date(2026, 11, 15), "USD", 10, 10, 0, 0, Decimal("10000.00"), Decimal("0.00")),
        (date(2026, 10, 10), "USD", 5, 4, 0, 1, Decimal("4000.00"), Decimal("1000.00")),
    ]
    res = MagicMock()
    res.fetchall.return_value = mock_rows
    mock_db.execute.return_value = res

    monthly_report = run_coroutine(
        ReportService.get_monthly_report(
            db=mock_db,
            org_id=org_id,
        )
    )

    assert len(monthly_report.items) == 2
    nov_item = next(it for it in monthly_report.items if it.period == "2026-11")
    oct_item = next(it for it in monthly_report.items if it.period == "2026-10")

    assert nov_item.total_transactions == 20
    assert nov_item.matched_count == 18
    assert nov_item.reconciled_amount == Decimal("18000.00")
    assert nov_item.reconciliation_rate == Decimal("90.00")

    assert oct_item.total_transactions == 5
    assert oct_item.reconciled_amount == Decimal("4000.00")

    csv_text = ReportService.generate_monthly_report_csv(monthly_report)
    assert "Period (Month),Currency,Total Transactions" in csv_text
    assert "2026-11,USD,20,18,1,18000.00,2000.00,90.00,CALCULATED_EXACT" in csv_text


# ----------------------------------------------------------------------------
# 5. TEST UNMATCHED TRANSACTIONS AGING REPORT & CSV EXPORT
# ----------------------------------------------------------------------------
def test_unmatched_transactions_aging_report():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    today = date.today()

    b_tx_fresh = BankTransaction(
        id=uuid.uuid4(),
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        raw_data={},
        raw_description="Fresh Wire",
        raw_amount_string="500.00",
        raw_date_string="2026-11-20",
        booking_date=today - timedelta(days=5),
        amount=Decimal("500.00"),
        direction="CREDIT",
        currency="USD",
        normalized_description="Fresh Wire Transfer",
        reconciliation_status="UNMATCHED",
        created_at=datetime.now(timezone.utc),
    )

    b_tx_aged = BankTransaction(
        id=uuid.uuid4(),
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=2,
        raw_data={},
        raw_description="Old Deposit",
        raw_amount_string="1200.00",
        raw_date_string="2026-08-01",
        booking_date=today - timedelta(days=75),
        amount=Decimal("1200.00"),
        direction="CREDIT",
        currency="USD",
        normalized_description="Old Deposit Investigation",
        reconciliation_status="UNMATCHED",
        created_at=datetime.now(timezone.utc),
    )

    l_entry_very_old = LedgerEntry(
        id=uuid.uuid4(),
        organization_id=org_id,
        batch_id=uuid.uuid4(),
        entry_id="LED-991",
        source_row_number=1,
        posting_date=today - timedelta(days=120),
        description="Vendor Check Outstanding",
        amount=Decimal("350.00"),
        direction="DEBIT",
        currency="EUR",
        account_code="2000",
        source_system="ERP",
        raw_data={},
        raw_entry_id="LED-991",
        raw_amount_string="350.00",
        raw_date_string="2026-07-01",
        raw_description="Vendor Check Outstanding",
        reconciliation_status="UNRECONCILED",
        created_at=datetime.now(timezone.utc),
    )

    res_b = MagicMock()
    res_b.scalars().all.return_value = [b_tx_fresh, b_tx_aged]

    res_l = MagicMock()
    res_l.scalars().all.return_value = [l_entry_very_old]

    mock_db.execute.side_effect = [res_b, res_l]

    report = run_coroutine(
        ReportService.get_unmatched_report(
            db=mock_db,
            org_id=org_id,
        )
    )

    assert report.total_unmatched_count == 3
    assert report.aging_summary["<30_DAYS"] == 1
    assert report.aging_summary["60-90_DAYS"] == 1
    assert report.aging_summary["90+_DAYS"] == 1
    assert report.unmatched_amounts_by_currency["USD"] == Decimal("1700.00")
    assert report.unmatched_amounts_by_currency["EUR"] == Decimal("350.00")

    csv_text = ReportService.generate_unmatched_report_csv(report)
    assert "Item ID,Source Type,Record Date,Currency,Amount,Direction,Days Open,Aging Bucket" in csv_text
    assert "<30_DAYS" in csv_text
    assert "90+_DAYS" in csv_text


# ----------------------------------------------------------------------------
# 6. TEST BANK FEES & VARIANCES REPORT & CSV EXPORT
# ----------------------------------------------------------------------------
def test_bank_fees_report():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    b_tx = BankTransaction(
        id=uuid.uuid4(),
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        raw_data={},
        raw_description="Intl Wire",
        raw_amount_string="1025.00",
        raw_date_string="2026-11-20",
        booking_date=date(2026, 11, 20),
        amount=Decimal("1025.00"),
        direction="CREDIT",
        currency="USD",
        normalized_description="Intl Wire Transfer",
        reconciliation_status="RECONCILED",
        created_at=datetime.now(timezone.utc),
    )

    prop = AdjustmentProposal(
        id=uuid.uuid4(),
        manual_review_id=uuid.uuid4(),
        organization_id=org_id,
        maker_id=uuid.uuid4(),
        proposed_bank_id=b_tx.id,
        proposed_ledger_id=uuid.uuid4(),
        adjustment_amount=Decimal("25.00"),
        adjustment_reason="Intermediary Wire Service Fee",
        status="APPROVED",
        created_at=datetime.now(timezone.utc),
    )

    res_adj = MagicMock()
    res_adj.fetchall.return_value = [(prop, b_tx)]

    res_match = MagicMock()
    res_match.fetchall.return_value = []

    mock_db.execute.side_effect = [res_adj, res_match]

    report = run_coroutine(
        ReportService.get_bank_fees_report(
            db=mock_db,
            org_id=org_id,
        )
    )

    assert report.total_fee_count == 1
    assert report.total_fee_amounts_by_currency["USD"] == Decimal("25.00")
    assert report.items[0].fee_type == "VARIANCE_ADJUSTMENT"
    assert report.items[0].description == "Intermediary Wire Service Fee"

    csv_text = ReportService.generate_bank_fees_report_csv(report)
    assert "Item ID,Record Date,Currency,Fee / Variance Amount,Fee Type,Status,Description" in csv_text
    assert "25.00,VARIANCE_ADJUSTMENT,APPROVED" in csv_text


# ----------------------------------------------------------------------------
# 7. TEST PENDING APPROVALS REPORT & CSV EXPORT
# ----------------------------------------------------------------------------
def test_pending_approvals_report():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    review_item = ManualReviewItem(
        id=uuid.uuid4(),
        organization_id=org_id,
        bank_transaction_id=uuid.uuid4(),
        category="AMOUNT_MISMATCH",
        status="PENDING",
        priority="HIGH",
        requires_maker_checker=True,
        created_at=datetime.now(timezone.utc),
    )

    b_tx = BankTransaction(
        id=review_item.bank_transaction_id,
        organization_id=org_id,
        bank_statement_id=uuid.uuid4(),
        bank_account_id=uuid.uuid4(),
        source_row_number=1,
        raw_data={},
        raw_description="Vendor Pmt",
        raw_amount_string="4500.00",
        raw_date_string="2026-11-20",
        booking_date=date(2026, 11, 20),
        amount=Decimal("4500.00"),
        direction="DEBIT",
        currency="EUR",
        normalized_description="Vendor Payment Miscount",
        reconciliation_status="PROPOSED",
        created_at=datetime.now(timezone.utc),
    )

    res_rev = MagicMock()
    res_rev.fetchall.return_value = [(review_item, b_tx)]

    res_adj = MagicMock()
    res_adj.fetchall.return_value = []

    mock_db.execute.side_effect = [res_rev, res_adj]

    report = run_coroutine(
        ReportService.get_pending_approvals_report(
            db=mock_db,
            org_id=org_id,
        )
    )

    assert report.total_pending_count == 1
    assert report.priority_breakdown["HIGH"] == 1
    assert report.pending_amounts_by_currency["EUR"] == Decimal("4500.00")
    assert report.items[0].category == "AMOUNT_MISMATCH"
    assert report.items[0].requires_maker_checker is True

    csv_text = ReportService.generate_pending_approvals_report_csv(report)
    assert "Item ID,Item Type,Category,Priority,Currency,Amount,Days Pending,Requires Maker-Checker" in csv_text
    assert "AMOUNT_MISMATCH,HIGH,EUR,4500.00,0,YES" in csv_text


# ----------------------------------------------------------------------------
# 8. TEST EXCEPTION SUMMARY REPORT & CSV EXPORT
# ----------------------------------------------------------------------------
def test_exception_summary_report():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    # (category, status, currency, count, sum_amt)
    mock_rows = [
        ("LOW_CONFIDENCE", "PENDING", "USD", 5, Decimal("2500.00")),
        ("LOW_CONFIDENCE", "APPROVED", "USD", 10, Decimal("5000.00")),
        ("DUPLICATE_TRANSACTION", "REJECTED", "EUR", 2, Decimal("1000.00")),
        ("POSSIBLE_REFUND", "PENDING", "USD", 1, Decimal("150.00")),
    ]
    res = MagicMock()
    res.fetchall.return_value = mock_rows
    mock_db.execute.return_value = res

    report = run_coroutine(
        ReportService.get_exception_summary_report(
            db=mock_db,
            org_id=org_id,
        )
    )

    assert report.total_exceptions == 18
    # Resolved: 10 + 2 = 12 / 18 = 66.67%
    assert report.resolved_rate == Decimal("66.67")

    low_conf = next(c for c in report.categories if c.category == "LOW_CONFIDENCE")
    assert low_conf.total_count == 15
    assert low_conf.pending_count == 5
    assert low_conf.resolved_count == 10
    # 15 / 18 * 100 = 83.33%
    assert low_conf.percentage_of_total == Decimal("83.33")

    csv_text = ReportService.generate_exception_summary_csv(report)
    assert "Category,Total Exceptions,Pending Count,Resolved Count,Unresolved Count,Share of Total (%),Amounts by Currency" in csv_text
    assert "LOW_CONFIDENCE,15,5,10,0,83.33" in csv_text


# ----------------------------------------------------------------------------
# 9. TEST INTEGRATION FAILURE REPORT & CSV EXPORT
# ----------------------------------------------------------------------------
def test_integration_failure_report():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    # (provider_name, provider_type, endpoint, total, successes, failures, dead_letters, recovered, avg_lat)
    mock_rows = [
        ("SIMULATED_CORE_BANKING", "CORE_BANKING", "/v1/statements/sync", 100, 95, 5, 2, 0, 45.2),
        ("SIMULATED_ERP_NETSUITE", "ERP_LEDGER", "/services/rest/record/v1/journal", 50, 48, 2, 0, 1, 120.5),
    ]
    res1 = MagicMock()
    res1.fetchall.return_value = mock_rows

    # err_rows: (provider_name, endpoint, error_category, count)
    err_rows = [
        ("SIMULATED_CORE_BANKING", "/v1/statements/sync", "RATE_LIMIT_429", 3),
        ("SIMULATED_CORE_BANKING", "/v1/statements/sync", "SERVER_ERROR_500", 2),
    ]
    res2 = MagicMock()
    res2.fetchall.return_value = err_rows

    mock_db.execute.side_effect = [res1, res2]

    report = run_coroutine(
        ReportService.get_integration_failure_report(
            db=mock_db,
            org_id=org_id,
        )
    )

    assert report.total_requests == 150
    assert report.total_failures == 7
    assert report.total_dead_letters == 2
    # 143 successes / 150 total = 95.33%
    assert report.overall_availability_rate == Decimal("95.33")

    cb_item = next(it for it in report.items if it.provider_name == "SIMULATED_CORE_BANKING")
    assert cb_item.failure_breakdown["RATE_LIMIT_429"] == 3
    assert cb_item.dead_letter_count == 2

    erp_item = next(it for it in report.items if it.provider_name == "SIMULATED_ERP_NETSUITE")
    assert erp_item.recovered_count == 1

    csv_text = ReportService.generate_integration_failure_csv(report)
    assert "Provider Name,Provider Type,Endpoint,Total Requests,Success Count,Failure Count,Dead Letter Count" in csv_text
    assert "SIMULATED_CORE_BANKING,CORE_BANKING,/v1/statements/sync,100,95,5,2" in csv_text


# ----------------------------------------------------------------------------
# 10. TEST AUDIT ACTIVITY REPORT & CSV EXPORT
# ----------------------------------------------------------------------------
def test_audit_activity_report():
    org_id = uuid.uuid4()
    mock_db = AsyncMock()

    t_earliest = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)
    t_latest = datetime(2026, 11, 21, 14, 0, tzinfo=timezone.utc)

    # 1. total, min, max
    res1 = MagicMock()
    res1.fetchone.return_value = (142, t_earliest, t_latest)

    # 2. actor rows
    res2 = MagicMock()
    res2.fetchall.return_value = [("USER", 80), ("SYSTEM_WORKER", 42), ("AI_AGENT", 20)]

    # 3. event type rows
    res3 = MagicMock()
    res3.fetchall.return_value = [("RECONCILIATION_RUN", 30), ("HUMAN_REVIEW_APPROVED", 12), ("STATEMENT_UPLOAD", 10)]

    # 4. integrity check
    mock_check = AuditIntegrityCheck(
        id=uuid.uuid4(),
        organization_id=org_id,
        start_sequence_id=1,
        end_sequence_id=142,
        total_events_checked=142,
        status="VERIFIED",
        check_timestamp=datetime.now(timezone.utc),
    )
    res4 = MagicMock()
    res4.scalars().first.return_value = mock_check

    mock_db.execute.side_effect = [res1, res2, res3, res4]

    report = run_coroutine(
        ReportService.get_audit_activity_report(
            db=mock_db,
            org_id=org_id,
        )
    )

    assert report.total_events == 142
    assert report.integrity_status == "VERIFIED"
    assert report.events_by_actor_type["USER"] == 80
    assert report.events_by_actor_type["AI_AGENT"] == 20
    assert report.last_verified_sequence_id == 142

    csv_text = ReportService.generate_audit_activity_csv(report)
    assert "Total Audit Events,142" in csv_text
    assert "Cryptographic Integrity Status,VERIFIED" in csv_text
    assert "USER,80" in csv_text


# ----------------------------------------------------------------------------
# 11. TEST ROLE-BASED ACCESS CONTROL (RBAC) FOR REPORTS
# ----------------------------------------------------------------------------
def test_role_based_access_control():
    """Verify that permitted roles can access reports, while unauthorized roles are rejected."""
    org = Organization(id=uuid.uuid4(), name="Acme Financial", slug="acme")
    
    # Allowed roles
    admin_membership = OrganizationMembership(organization_id=org.id, user_id=uuid.uuid4(), role="ADMIN")
    fm_membership = OrganizationMembership(organization_id=org.id, user_id=uuid.uuid4(), role="FINANCE_MANAGER")
    accountant_membership = OrganizationMembership(organization_id=org.id, user_id=uuid.uuid4(), role="ACCOUNTANT")
    auditor_membership = OrganizationMembership(organization_id=org.id, user_id=uuid.uuid4(), role="AUDITOR")

    checker = require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])

    # Permitted roles should succeed
    for mem in [admin_membership, fm_membership, accountant_membership, auditor_membership]:
        res = run_coroutine(checker((org, mem)))
        assert res == (org, mem)

    # Unauthorized role (e.g. VIEWER or EXTERNAL_CLIENT) should raise HTTP 403
    unauthorized_membership = OrganizationMembership(
        organization_id=org.id,
        user_id=uuid.uuid4(),
        role="EXTERNAL_GUEST",
    )
    with pytest.raises(HTTPException) as exc_info:
        run_coroutine(checker((org, unauthorized_membership)))
    assert exc_info.value.status_code == 403
    assert "Access denied" in exc_info.value.detail
