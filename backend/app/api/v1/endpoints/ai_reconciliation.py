"""
AI-Assisted Financial Reconciliation Endpoints (Phase 9).
Provides endpoints to trigger LangGraph-driven AI reconciliation runs
and inspect immutable AI proposal audit logs.
"""
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_current_user,
    require_role,
)
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.models.audit import AuditEvent
from app.schemas.ai_reconciliation import (
    AIReconciliationRunRequest,
    AIReconciliationRunResponse,
)
from app.services.ai.ai_reconciliation_service import AIReconciliationService

router = APIRouter(prefix="/reconciliation/ai", tags=["AI Reconciliation"])


@router.post(
    "/run",
    response_model=AIReconciliationRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute AI-assisted reconciliation run (LangGraph)",
)
async def run_ai_reconciliation(
    request: AIReconciliationRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER"])
    ),
):
    """
    Execute AI-Assisted Tier-2 financial reconciliation using LangGraph and OpenAI.
    AI proposes candidate rankings; all proposals are strictly validated by the
    deterministic engine. Unvalidated proposals are never auto-approved.
    Requires ADMIN or FINANCE_MANAGER role.
    """
    org, _ = org_and_membership
    response = await AIReconciliationService.execute_ai_run(
        db=db,
        organization_id=org.id,
        user_id=current_user.id,
        request=request,
    )
    return response


@router.get(
    "/audit",
    response_model=List[Dict[str, Any]],
    summary="Retrieve AI reconciliation audit logs",
)
async def get_ai_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "AUDITOR"])
    ),
):
    """
    Retrieve immutable audit event trail for AI reconciliation operations.
    Includes prompt versions, model metadata, matching signals, and deterministic outcomes.
    Accessible to ADMIN, FINANCE_MANAGER, and AUDITOR roles.
    """
    org, _ = org_and_membership
    query = (
        select(AuditEvent)
        .where(
            and_(
                AuditEvent.organization_id == org.id,
                AuditEvent.actor_type == "AI_AGENT",
            )
        )
        .order_by(desc(AuditEvent.created_at))
        .limit(limit)
    )
    res = await db.execute(query)
    events = res.scalars().all()

    return [
        {
            "id": str(e.id),
            "action": e.action,
            "resource_type": e.resource_type,
            "resource_id": str(e.resource_id) if e.resource_id else None,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
