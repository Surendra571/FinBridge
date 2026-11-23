"""
Bank Statement Ingestion and Lifecycle API Endpoints.
Implements secure upload, validation, parsing preview, confirmation, and error reporting.
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
from app.schemas.financial import (
    StatementUploadResponse,
    StatementResponse,
    BankTransactionResponse,
)
from app.services.ingestion.statement_service import StatementService

router = APIRouter(prefix="/statements", tags=["Bank Statements"])


@router.post(
    "/upload",
    response_model=StatementUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload bank statement for preview and validation",
)
async def upload_statement(
    bank_account_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    """
    Upload a bank statement file (CSV or digital text PDF).
    Performs format checks, SHA-256 deduplication, raw preservation,
    and returns parsed transaction previews and validation errors.
    Does NOT finalize transactions until confirmed.
    """
    org, _ = org_and_membership
    content = await file.read()

    upload_result = await StatementService.upload_statement(
        db=db,
        organization_id=org.id,
        user_id=current_user.id,
        bank_account_id=bank_account_id,
        file_name=file.filename or "statement_upload",
        file_bytes=content,
    )
    return upload_result


@router.post(
    "/{statement_id}/confirm",
    response_model=StatementResponse,
    summary="Confirm statement import and persist transactions",
)
async def confirm_statement(
    statement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    """
    Confirm staged statement. Persists all valid rows into bank_transactions
    with raw imported strings preserved verbatim and status set to UNMATCHED.
    """
    org, _ = org_and_membership
    statement = await StatementService.confirm_statement(
        db=db,
        organization_id=org.id,
        statement_id=statement_id,
    )
    return statement


@router.get(
    "",
    response_model=List[StatementResponse],
    summary="List imported statements",
)
async def list_statements(
    bank_account_id: Optional[uuid.UUID] = None,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    List all statements for active organization, optionally filtered by bank account.
    """
    org, _ = org_and_membership
    statements = await StatementService.get_statements(
        db=db,
        organization_id=org.id,
        bank_account_id=bank_account_id,
    )
    return statements


@router.get(
    "/{statement_id}",
    response_model=StatementResponse,
    summary="Get statement by ID",
)
async def get_statement(
    statement_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    Retrieve single statement details, status, and parsing error logs.
    """
    org, _ = org_and_membership
    statement = await StatementService.get_statement(
        db=db,
        organization_id=org.id,
        statement_id=statement_id,
    )
    if not statement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Statement not found.",
        )
    return statement


@router.get(
    "/{statement_id}/transactions",
    response_model=List[BankTransactionResponse],
    summary="Get confirmed statement transactions",
)
async def get_statement_transactions(
    statement_id: uuid.UUID,
    limit: int = 200,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    List persisted bank transactions for a statement with preserved raw strings.
    """
    org, _ = org_and_membership
    transactions = await StatementService.get_statement_transactions(
        db=db,
        organization_id=org.id,
        statement_id=statement_id,
        limit=limit,
        offset=offset,
    )
    return transactions
