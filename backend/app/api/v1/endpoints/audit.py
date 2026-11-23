"""
Audit Trail & Cryptographic Verification Endpoints (Phase 11).
Provides REST APIs for audit log exploration, entity timelines,
and on-demand cryptographic chain integrity verification.
"""
import uuid
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_current_user,
    require_role,
)
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.schemas.audit import (
    AuditEventCreateRequest,
    AuditEventResponse,
    AuditEventsListResponse,
    AuditIntegrityVerificationResponse,
    AuditIntegrityCheckResponse,
)
from app.services.audit.audit_service import AuditService

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get(
    "/events",
    response_model=AuditEventsListResponse,
    summary="List paginated and filtered audit events",
)
async def list_audit_events(
    event_type: Optional[str] = Query(default=None),
    entity_type: Optional[str] = Query(default=None),
    actor_type: Optional[str] = Query(default=None),
    actor_id: Optional[uuid.UUID] = Query(default=None),
    correlation_id: Optional[str] = Query(default=None),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])
    ),
):
    org, _ = org_and_membership
    return await AuditService.get_audit_events(
        db=db,
        organization_id=org.id,
        event_type=event_type,
        entity_type=entity_type,
        actor_type=actor_type,
        actor_id=actor_id,
        correlation_id=correlation_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/events/{event_id}",
    response_model=AuditEventResponse,
    summary="Fetch single audit event details",
)
async def get_audit_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])
    ),
):
    org, _ = org_and_membership
    return await AuditService.get_event_by_id(
        db=db,
        organization_id=org.id,
        event_id=event_id,
    )


@router.get(
    "/events/entity/{entity_type}/{entity_id}",
    response_model=List[AuditEventResponse],
    summary="Fetch chronological audit timeline for a specific entity",
)
async def get_entity_audit_trail(
    entity_type: str,
    entity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])
    ),
):
    org, _ = org_and_membership
    return await AuditService.get_entity_history(
        db=db,
        organization_id=org.id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


@router.post(
    "/events",
    response_model=AuditEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an append-only audit event",
)
async def record_audit_event(
    request: AuditEventCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    org, _ = org_and_membership
    if not request.actor_id:
        request.actor_id = current_user.id
    event = await AuditService.record_event(
        db=db,
        organization_id=org.id,
        request=request,
    )
    return await AuditService.get_event_by_id(db=db, organization_id=org.id, event_id=event.id)


@router.post(
    "/integrity/verify",
    response_model=AuditIntegrityVerificationResponse,
    summary="Run cryptographic hash chain integrity scan",
)
async def verify_chain_integrity(
    start_seq: Optional[int] = Query(default=None, ge=1),
    end_seq: Optional[int] = Query(default=None, ge=1),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "AUDITOR"])
    ),
):
    org, _ = org_and_membership
    return await AuditService.verify_chain_integrity(
        db=db,
        organization_id=org.id,
        performed_by=current_user.id,
        start_seq=start_seq,
        end_seq=end_seq,
    )


@router.get(
    "/integrity/history",
    response_model=List[AuditIntegrityCheckResponse],
    summary="Fetch past cryptographic chain verification reports",
)
async def get_integrity_history(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])
    ),
):
    org, _ = org_and_membership
    return await AuditService.get_integrity_history(
        db=db,
        organization_id=org.id,
        limit=limit,
    )


@router.get(
    "/limitation-disclosure",
    summary="Cryptographic audit immutability controls and limitation disclosure",
)
async def get_limitation_disclosure():
    """
    Returns formal architectural disclosure explaining cryptographic guarantees and boundaries.
    """
    return {
        "title": "FinBridge Audit Immutability & Hash Chaining Architectural Disclosure",
        "guarantees": [
            "SHA-256 forward hash chaining guarantees detection of unauthorized row modifications.",
            "Monotonic sequence numbers prevent silent row deletion or insertion of forged past transactions.",
            "ORM-level and database privilege constraints prohibit UPDATE and DELETE mutations from normal business services.",
            "Before and after state snapshots record complete mutation history.",
        ],
        "boundaries_and_limitations": [
            "Hash chaining detects tampering after creation but does NOT make a compromised database with superuser/root access physically impossible to tamper with.",
            "A malicious actor with direct write access to database tables could recompute all subsequent forward hashes unless anchored to external WORM compliance stores.",
            "For full legal immutability compliance, periodic chain checkpoints should be published to external append-only targets (e.g. AWS S3 Object Lock in Compliance Mode or RFC 3161 cryptographic timestamping).",
        ],
        "recommended_hardening": [
            "REVOKE UPDATE, DELETE ON audit_events FROM finbridge_app_role;",
            "Ship cryptographic chain hashes to an external immutable bucket on daily cron schedule.",
        ],
    }
