"""
Human Review & Maker-Checker Endpoints (Phase 10).
Provides REST APIs for review queue triage, comprehensive workspace inspection,
reviewer approval actions, investigation notes, and maker-checker adjustments.
"""
import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_current_user,
    require_role,
)
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.schemas.review import (
    ReviewQueueItemResponse,
    ReviewWorkspaceDetailResponse,
    ReviewNoteResponse,
    AdjustmentProposalResponse,
    ApproveMatchRequest,
    RejectMatchRequest,
    MarkUnresolvedRequest,
    RemapCandidateRequest,
    AddNoteRequest,
    RequestInvestigationRequest,
    ProposeAdjustmentRequest,
    DecideAdjustmentRequest,
)
from app.services.review.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["Human Review"])


@router.get(
    "/queue",
    response_model=List[ReviewQueueItemResponse],
    summary="List review queue items with category/status filters",
)
async def get_review_queue(
    category: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    priority: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])
    ),
):
    """Retrieve review queue items scoped to current organization."""
    org, _ = org_and_membership
    return await ReviewService.get_review_queue(
        db=db,
        organization_id=org.id,
        category=category,
        status_filter=status_filter,
        priority=priority,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{review_id}/workspace",
    response_model=ReviewWorkspaceDetailResponse,
    summary="Get comprehensive review workspace details",
)
async def get_review_workspace(
    review_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])
    ),
):
    """Retrieve complete review workspace context (Bank, Ledger, AI, Deterministic rules, Notes)."""
    org, _ = org_and_membership
    return await ReviewService.get_review_workspace(
        db=db,
        organization_id=org.id,
        review_id=review_id,
    )


@router.post(
    "/{review_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve a proposed transaction match",
)
async def approve_match(
    review_id: uuid.UUID,
    request: ApproveMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER"])
    ),
):
    """Approve match and reconcile records. Requires ADMIN or FINANCE_MANAGER."""
    org, _ = org_and_membership
    return await ReviewService.approve_match(
        db=db,
        organization_id=org.id,
        review_id=review_id,
        user_id=current_user.id,
        request=request,
    )


@router.post(
    "/{review_id}/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject a proposed transaction match",
)
async def reject_match(
    review_id: uuid.UUID,
    request: RejectMatchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER"])
    ),
):
    """Reject proposed match. Requires ADMIN or FINANCE_MANAGER."""
    org, _ = org_and_membership
    return await ReviewService.reject_match(
        db=db,
        organization_id=org.id,
        review_id=review_id,
        user_id=current_user.id,
        request=request,
    )


@router.post(
    "/{review_id}/unresolved",
    status_code=status.HTTP_200_OK,
    summary="Mark transaction as unresolved exception",
)
async def mark_unresolved(
    review_id: uuid.UUID,
    request: MarkUnresolvedRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    """Mark item as unresolved exception."""
    org, _ = org_and_membership
    return await ReviewService.mark_unresolved(
        db=db,
        organization_id=org.id,
        review_id=review_id,
        user_id=current_user.id,
        request=request,
    )


@router.post(
    "/{review_id}/remap",
    status_code=status.HTTP_200_OK,
    summary="Remap bank transaction to an alternative ledger candidate",
)
async def remap_candidate(
    review_id: uuid.UUID,
    request: RemapCandidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER"])
    ),
):
    """Remap match candidate. Enforces deterministic currency parity."""
    org, _ = org_and_membership
    return await ReviewService.remap_candidate(
        db=db,
        organization_id=org.id,
        review_id=review_id,
        user_id=current_user.id,
        request=request,
    )


@router.post(
    "/{review_id}/notes",
    response_model=ReviewNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an investigation note",
)
async def add_review_note(
    review_id: uuid.UUID,
    request: AddNoteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    """Add immutable review observation note."""
    org, _ = org_and_membership
    return await ReviewService.add_review_note(
        db=db,
        organization_id=org.id,
        review_id=review_id,
        user_id=current_user.id,
        request=request,
    )


@router.post(
    "/{review_id}/investigate",
    status_code=status.HTTP_200_OK,
    summary="Request deeper investigation on an exception",
)
async def request_investigation(
    review_id: uuid.UUID,
    request: RequestInvestigationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    """Escalate review item priority to HIGH and request investigation."""
    org, _ = org_and_membership
    return await ReviewService.request_investigation(
        db=db,
        organization_id=org.id,
        review_id=review_id,
        user_id=current_user.id,
        request=request,
    )


@router.post(
    "/{review_id}/adjustments/propose",
    response_model=AdjustmentProposalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Maker proposes financial adjustment",
)
async def propose_adjustment(
    review_id: uuid.UUID,
    request: ProposeAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER"])
    ),
):
    """Maker proposes variance or fee adjustment for dual authorization."""
    org, _ = org_and_membership
    return await ReviewService.propose_adjustment(
        db=db,
        organization_id=org.id,
        review_id=review_id,
        maker_id=current_user.id,
        request=request,
    )


@router.post(
    "/adjustments/{proposal_id}/decide",
    status_code=status.HTTP_200_OK,
    summary="Checker decides on adjustment proposal (maker != checker)",
)
async def decide_adjustment(
    proposal_id: uuid.UUID,
    request: DecideAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER"])
    ),
):
    """
    Checker approves or rejects financial adjustment.
    Maker-checker constraint enforced: maker_id != checker_id!
    """
    org, _ = org_and_membership
    return await ReviewService.decide_adjustment(
        db=db,
        organization_id=org.id,
        proposal_id=proposal_id,
        checker_id=current_user.id,
        request=request,
    )
