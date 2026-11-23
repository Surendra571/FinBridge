"""
Simulated Integrations, Reliability & DLQ Endpoints (Phase 12).
Provides APIs for triggering failure simulations, querying integration telemetry,
managing dead-letter queues, and processing deduplicated webhooks.
Clearly labeled as SIMULATED integrations.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.api.deps import (
    get_db,
    get_current_user,
    require_role,
)
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.models.integration import Integration, IntegrationRequest
from app.schemas.integration import (
    SimulateIntegrationRequest,
    SimulateIntegrationResponse,
    IntegrationResponse,
    IntegrationRequestItem,
    SimulatedWebhookRequest,
    SimulatedWebhookResponse,
    DeadLetterRecoveryRequest,
)
from app.services.integrations.client import ReliableIntegrationClient

router = APIRouter(prefix="/integrations", tags=["Reliable Integrations"])


@router.get(
    "",
    response_model=List[IntegrationResponse],
    summary="List simulated integrations and health status",
)
async def list_integrations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])
    ),
):
    org, _ = org_and_membership
    # Ensure standard simulated integrations exist for this organization
    await ReliableIntegrationClient.get_or_create_integration(
        db=db,
        organization_id=org.id,
        provider_name="SIMULATED_CORE_BANKING_CHASE",
        provider_type="CORE_BANKING",
    )
    await ReliableIntegrationClient.get_or_create_integration(
        db=db,
        organization_id=org.id,
        provider_name="SIMULATED_ERP_NETSUITE",
        provider_type="ERP_LEDGER",
    )

    q = select(Integration).where(Integration.organization_id == org.id).order_by(Integration.provider_name.asc())
    records = (await db.execute(q)).scalars().all()
    return records


@router.post(
    "/simulate",
    response_model=SimulateIntegrationResponse,
    summary="Dispatch simulated integration request with induced failure mode",
)
async def simulate_integration_request(
    request: SimulateIntegrationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    org, _ = org_and_membership
    return await ReliableIntegrationClient.dispatch_with_retry(
        db=db,
        organization_id=org.id,
        request=request,
    )


@router.get(
    "/requests",
    response_model=List[IntegrationRequestItem],
    summary="Query recent outbound integration requests and error telemetry",
)
async def list_integration_requests(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    error_category: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT", "AUDITOR"])
    ),
):
    org, _ = org_and_membership
    filters = [IntegrationRequest.organization_id == org.id]
    if status_filter:
        filters.append(IntegrationRequest.status == status_filter)
    if error_category:
        filters.append(IntegrationRequest.error_category == error_category)

    q = (
        select(IntegrationRequest)
        .where(and_(*filters))
        .order_by(IntegrationRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    records = (await db.execute(q)).scalars().all()
    return records


@router.get(
    "/dead-letter",
    response_model=List[IntegrationRequestItem],
    summary="List dead-letter queue (DLQ) requests requiring manual review or recovery",
)
async def list_dead_letter_requests(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    org, _ = org_and_membership
    q = (
        select(IntegrationRequest)
        .where(
            and_(
                IntegrationRequest.organization_id == org.id,
                IntegrationRequest.status == "DEAD_LETTER",
            )
        )
        .order_by(IntegrationRequest.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    records = (await db.execute(q)).scalars().all()
    return records


@router.post(
    "/dead-letter/{request_id}/recover",
    summary="Recover and safely replay a dead-lettered job",
)
async def recover_dead_letter_job(
    request_id: uuid.UUID,
    payload: DeadLetterRecoveryRequest = DeadLetterRecoveryRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER"])
    ),
):
    org, _ = org_and_membership
    return await ReliableIntegrationClient.recover_dead_letter_job(
        db=db,
        organization_id=org.id,
        request_id=request_id,
        resolution_notes=payload.resolution_notes,
    )


@router.post(
    "/webhook/simulate",
    response_model=SimulatedWebhookResponse,
    summary="Simulate incoming core banking webhook with deduplication",
)
async def simulate_incoming_webhook(
    request: SimulatedWebhookRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    org, _ = org_and_membership
    return await ReliableIntegrationClient.process_incoming_webhook(
        db=db,
        organization_id=org.id,
        request=request,
    )
