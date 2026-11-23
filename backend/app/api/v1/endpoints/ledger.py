"""
General Ledger Ingestion and Query API Endpoints.
Provides endpoints for ledger CSV upload preview, double-entry validation,
confirmation, and querying entries by account code or journal.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_current_user,
    get_current_org_membership,
    require_role,
)
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.schemas.ledger import (
    LedgerUploadResponse,
    LedgerBatchResponse,
    LedgerEntryResponse,
    LedgerSchemaDocItem,
)
from app.services.ingestion.ledger_service import LedgerService

router = APIRouter(prefix="/ledger", tags=["General Ledger"])


@router.get(
    "/schema",
    response_model=List[LedgerSchemaDocItem],
    summary="Get ledger CSV schema and alias documentation",
)
def get_ledger_schema_documentation():
    """
    Returns the supported field definitions, required flags, examples,
    and recognized column aliases for internal ledger CSV ingestion.
    """
    return LedgerService.get_schema_documentation()


@router.post(
    "/upload",
    response_model=LedgerUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload ledger CSV for preview and validation",
)
async def upload_ledger_csv(
    file: UploadFile = File(...),
    source_system: str = Form("ERP"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    """
    Upload a general ledger CSV export.
    Validates mandatory fields, checks for duplicate entry IDs, computes
    double-entry journal balances, and stages records in PREVIEW status.
    Does NOT finalize ledger entries until confirmed.
    """
    org, _ = org_and_membership
    content = await file.read()

    res = await LedgerService.upload_ledger_csv(
        db=db,
        organization_id=org.id,
        user_id=current_user.id,
        file_name=file.filename or "ledger_upload.csv",
        file_bytes=content,
        source_system=source_system,
    )
    return res


@router.post(
    "/{batch_id}/confirm",
    response_model=LedgerBatchResponse,
    summary="Confirm staged ledger batch and persist entries",
)
async def confirm_ledger_import(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    """
    Confirm staged ledger batch. Inserts all valid records into ledger_entries
    preserving raw imported strings verbatim. Status is updated to CONFIRMED.
    """
    org, _ = org_and_membership
    batch = await LedgerService.confirm_ledger_import(
        db=db,
        organization_id=org.id,
        batch_id=batch_id,
    )
    return batch


@router.get(
    "/batches",
    response_model=List[LedgerBatchResponse],
    summary="List past ledger import batches",
)
async def list_ledger_batches(
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    List all ledger import batches for the active organization.
    """
    org, _ = org_and_membership
    batches = await LedgerService.get_ledger_batches(db=db, organization_id=org.id)
    return batches


@router.get(
    "/batches/{batch_id}",
    response_model=LedgerBatchResponse,
    summary="Get ledger batch by ID",
)
async def get_ledger_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    Retrieve single ledger batch details, status, and error logs.
    """
    org, _ = org_and_membership
    batch = await LedgerService.get_ledger_batch(
        db=db,
        organization_id=org.id,
        batch_id=batch_id,
    )
    if not batch:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ledger batch not found.",
        )
    return batch


@router.get(
    "/entries",
    response_model=List[LedgerEntryResponse],
    summary="Query confirmed ledger entries",
)
async def list_ledger_entries(
    batch_id: Optional[uuid.UUID] = None,
    account_code: Optional[str] = None,
    journal_id: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    Query confirmed ledger entries with optional filters by batch, GL account code, or journal.
    """
    org, _ = org_and_membership
    entries = await LedgerService.get_ledger_entries(
        db=db,
        organization_id=org.id,
        batch_id=batch_id,
        account_code=account_code,
        journal_id=journal_id,
        limit=limit,
        offset=offset,
    )
    return entries
