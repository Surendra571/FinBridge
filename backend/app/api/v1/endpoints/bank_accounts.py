"""
Bank Account Management API Endpoints.
Allows organizations to configure checking, savings, and operational accounts.
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_org_membership, require_role
from app.models.organization import Organization, OrganizationMembership
from app.schemas.financial import BankAccountCreateRequest, BankAccountResponse
from app.services.ingestion.statement_service import StatementService

router = APIRouter(prefix="/bank-accounts", tags=["Bank Accounts"])


@router.post(
    "",
    response_model=BankAccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new bank account",
)
async def create_bank_account(
    data: BankAccountCreateRequest,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        require_role(["ADMIN", "FINANCE_MANAGER", "ACCOUNTANT"])
    ),
):
    """
    Register a new institutional bank account under the active organization.
    Requires ADMIN, FINANCE_MANAGER, or ACCOUNTANT role.
    """
    org, _ = org_and_membership
    account = await StatementService.create_bank_account(db, org.id, data)
    return account


@router.get(
    "",
    response_model=List[BankAccountResponse],
    summary="List organization bank accounts",
)
async def list_bank_accounts(
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    Retrieve all active bank accounts for the current tenant.
    Accessible to all organization members including AUDITOR.
    """
    org, _ = org_and_membership
    accounts = await StatementService.get_bank_accounts(db, org.id)
    return accounts


@router.get(
    "/{account_id}",
    response_model=BankAccountResponse,
    summary="Get bank account by ID",
)
async def get_bank_account(
    account_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_and_membership: tuple[Organization, OrganizationMembership] = Depends(
        get_current_org_membership
    ),
):
    """
    Retrieve single bank account details by ID with strict tenant isolation.
    """
    org, _ = org_and_membership
    account = await StatementService.get_bank_account(db, org.id, account_id)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bank account not found.",
        )
    return account
