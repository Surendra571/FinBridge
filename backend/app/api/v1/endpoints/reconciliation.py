"""
Deterministic Financial Reconciliation API Endpoints.
Allows Finance Managers and Admins to trigger deterministic matching runs,
view candidate pairings, and inspect explainable validation trees.
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_current_user,
    get_current_org_membership,
    require_role,
)
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.schemas.reconciliation import (
    ReconciliationRunRequest,
    ReconciliationRunResponse,
    MatchCandidateResponse,
)
from app.services.reconciliation.reconciliation_service import ReconciliationService

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post(
    "/run",
    response_model=ReconciliationRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute deterministic reconciliation run",
)
async def run_reconciliation(
    request: ReconciliationRunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER"])
    ),
):
    """
    Execute deterministic Tier-1 reconciliation matching unconsumed bank transactions
    against ledger entries according to configured financial validation rules.
    Requires ADMIN or FINANCE_MANAGER role.
    """
    org, _ = org_and_membership
    run_response = await ReconciliationService.execute_run(
        db=db,
        organization_id=org.id,
        user_id=current_user.id,
        request=request,
    )
    return run_response


@router.get(
    "/runs",
    response_model=List[ReconciliationRunResponse],
    summary="List past reconciliation runs",
)
async def list_reconciliation_runs(
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    Retrieve all historical reconciliation runs for the current organization.
    """
    org, _ = org_and_membership
    runs = await ReconciliationService.get_runs(db=db, organization_id=org.id)
    return runs


@router.get(
    "/runs/{run_id}",
    response_model=ReconciliationRunResponse,
    summary="Get reconciliation run details by ID",
)
async def get_reconciliation_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    Retrieve single reconciliation run details, KPI metrics, and execution metadata.
    """
    org, _ = org_and_membership
    run = await ReconciliationService.get_run(db=db, organization_id=org.id, run_id=run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reconciliation run not found.",
        )
    return run

