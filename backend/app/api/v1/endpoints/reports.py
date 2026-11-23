"""
Financial Reports and Analytics REST Endpoints (Phase 13).
Supports date range filtering, organization isolation, role-based access control,
accurate financial aggregations across currencies, and CSV file exports.
"""
from datetime import date
from typing import Optional, Union
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_role
from app.models.organization import Organization, OrganizationMembership
from app.services.reports.report_service import ReportService
from app.schemas.reports import (
    DailyReconciliationResponse,
    MonthlyReconciliationResponse,
    UnmatchedTransactionsResponse,
    BankFeesReportResponse,
    PendingApprovalsResponse,
    ExceptionSummaryResponse,
    IntegrationFailureResponse,
    AuditActivityReportResponse,
)

router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])

# Enforce role-based access control: Only financial operators & auditors can access reports
REPORT_PERMITTED_ROLES = ["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"]


# ----------------------------------------------------------------------------
# 1. DAILY RECONCILIATION REPORT
# ----------------------------------------------------------------------------
@router.get(
    "/daily",
    summary="Daily reconciliation report partitioned by date and currency",
    response_model=DailyReconciliationResponse,
)
async def get_daily_report(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    currency: Optional[str] = Query(None, description="ISO currency code filter"),
    format: Optional[str] = Query("json", description="Output format: 'json' or 'csv'"),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(REPORT_PERMITTED_ROLES)
    ),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_membership
    report_data = await ReportService.get_daily_report(
        db=db,
        org_id=org.id,
        start_date=start_date,
        end_date=end_date,
        currency_filter=currency,
    )

    if format and format.lower() == "csv":
        csv_text = ReportService.generate_daily_report_csv(report_data)
        filename = f"daily_reconciliation_{org.slug}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data


# ----------------------------------------------------------------------------
# 2. MONTHLY RECONCILIATION REPORT
# ----------------------------------------------------------------------------
@router.get(
    "/monthly",
    summary="Monthly reconciliation report with volume trends and rates",
    response_model=MonthlyReconciliationResponse,
)
async def get_monthly_report(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    currency: Optional[str] = Query(None, description="ISO currency code filter"),
    format: Optional[str] = Query("json", description="Output format: 'json' or 'csv'"),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(REPORT_PERMITTED_ROLES)
    ),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_membership
    report_data = await ReportService.get_monthly_report(
        db=db,
        org_id=org.id,
        start_date=start_date,
        end_date=end_date,
        currency_filter=currency,
    )

    if format and format.lower() == "csv":
        csv_text = ReportService.generate_monthly_report_csv(report_data)
        filename = f"monthly_reconciliation_{org.slug}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data


# ----------------------------------------------------------------------------
# 3. UNMATCHED TRANSACTIONS REPORT
# ----------------------------------------------------------------------------
@router.get(
    "/unmatched",
    summary="Open unmatched bank transactions and ledger entries with aging analysis",
    response_model=UnmatchedTransactionsResponse,
)
async def get_unmatched_report(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    currency: Optional[str] = Query(None, description="ISO currency code filter"),
    format: Optional[str] = Query("json", description="Output format: 'json' or 'csv'"),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(REPORT_PERMITTED_ROLES)
    ),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_membership
    report_data = await ReportService.get_unmatched_report(
        db=db,
        org_id=org.id,
        start_date=start_date,
        end_date=end_date,
        currency_filter=currency,
    )

    if format and format.lower() == "csv":
        csv_text = ReportService.generate_unmatched_report_csv(report_data)
        filename = f"unmatched_transactions_{org.slug}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data


# ----------------------------------------------------------------------------
# 4. BANK FEES & VARIANCES REPORT
# ----------------------------------------------------------------------------
@router.get(
    "/bank-fees",
    summary="Bank fees, wire charges, and adjustment variances report",
    response_model=BankFeesReportResponse,
)
async def get_bank_fees_report(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    currency: Optional[str] = Query(None, description="ISO currency code filter"),
    format: Optional[str] = Query("json", description="Output format: 'json' or 'csv'"),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(REPORT_PERMITTED_ROLES)
    ),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_membership
    report_data = await ReportService.get_bank_fees_report(
        db=db,
        org_id=org.id,
        start_date=start_date,
        end_date=end_date,
        currency_filter=currency,
    )

    if format and format.lower() == "csv":
        csv_text = ReportService.generate_bank_fees_report_csv(report_data)
        filename = f"bank_fees_report_{org.slug}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data


# ----------------------------------------------------------------------------
# 5. PENDING APPROVALS REPORT
# ----------------------------------------------------------------------------
@router.get(
    "/pending-approvals",
    summary="Pending reconciliation approvals and maker-checker adjustments queue",
    response_model=PendingApprovalsResponse,
)
async def get_pending_approvals_report(
    priority: Optional[str] = Query(None, description="Priority filter: CRITICAL, HIGH, MEDIUM, LOW"),
    format: Optional[str] = Query("json", description="Output format: 'json' or 'csv'"),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(REPORT_PERMITTED_ROLES)
    ),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_membership
    report_data = await ReportService.get_pending_approvals_report(
        db=db,
        org_id=org.id,
        priority_filter=priority,
    )

    if format and format.lower() == "csv":
        csv_text = ReportService.generate_pending_approvals_report_csv(report_data)
        filename = f"pending_approvals_{org.slug}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data


# ----------------------------------------------------------------------------
# 6. EXCEPTION SUMMARY REPORT
# ----------------------------------------------------------------------------
@router.get(
    "/exceptions",
    summary="Exception categorization summary across 9 standard reconciliation rules",
    response_model=ExceptionSummaryResponse,
)
async def get_exception_summary_report(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    format: Optional[str] = Query("json", description="Output format: 'json' or 'csv'"),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(REPORT_PERMITTED_ROLES)
    ),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_membership
    report_data = await ReportService.get_exception_summary_report(
        db=db,
        org_id=org.id,
        start_date=start_date,
        end_date=end_date,
    )

    if format and format.lower() == "csv":
        csv_text = ReportService.generate_exception_summary_csv(report_data)
        filename = f"reconciliation_exceptions_{org.slug}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data


# ----------------------------------------------------------------------------
# 7. INTEGRATION FAILURE REPORT
# ----------------------------------------------------------------------------
@router.get(
    "/integration-failures",
    summary="Integration reliability metrics, error breakdowns, and dead-letter rates",
    response_model=IntegrationFailureResponse,
)
async def get_integration_failure_report(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    format: Optional[str] = Query("json", description="Output format: 'json' or 'csv'"),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(REPORT_PERMITTED_ROLES)
    ),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_membership
    report_data = await ReportService.get_integration_failure_report(
        db=db,
        org_id=org.id,
        start_date=start_date,
        end_date=end_date,
    )

    if format and format.lower() == "csv":
        csv_text = ReportService.generate_integration_failure_csv(report_data)
        filename = f"integration_failures_{org.slug}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data


# ----------------------------------------------------------------------------
# 8. AUDIT ACTIVITY REPORT
# ----------------------------------------------------------------------------
@router.get(
    "/audit-activity",
    summary="Audit event telemetry and cryptographic chain integrity report",
    response_model=AuditActivityReportResponse,
)
async def get_audit_activity_report(
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
    format: Optional[str] = Query("json", description="Output format: 'json' or 'csv'"),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(REPORT_PERMITTED_ROLES)
    ),
    db: AsyncSession = Depends(get_db),
):
    org, _ = org_and_membership
    report_data = await ReportService.get_audit_activity_report(
        db=db,
        org_id=org.id,
        start_date=start_date,
        end_date=end_date,
    )

    if format and format.lower() == "csv":
        csv_text = ReportService.generate_audit_activity_csv(report_data)
        filename = f"audit_activity_{org.slug}_{date.today().isoformat()}.csv"
        return StreamingResponse(
            iter([csv_text]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return report_data
