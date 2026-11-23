"""
Organization Management and Multi-Tenant Isolation Endpoints.
Enforces that users can only view and manage organizations they belong to.
"""
import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_db,
    get_current_verified_user,
    get_current_org_membership,
    require_role,
)
from app.core.security import create_access_token
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.schemas.auth import GenericSuccessResponse, TokenResponse, UserResponse
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    OrganizationResponse,
    MemberInviteRequest,
    MemberRoleUpdateRequest,
    MemberResponse,
    OrganizationMemberListResponse,
)
from app.services.org_service import OrgService

router = APIRouter(prefix="/organizations", tags=["Organizations & Tenants"])


@router.get(
    "",
    response_model=List[OrganizationResponse],
    summary="List user's active organizations",
)
async def list_organizations(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all organizations where current user has an active membership."""
    org_pairs = await OrgService.get_user_organizations(db, current_user.id)
    return [OrganizationResponse.model_validate(org) for org, _ in org_pairs]


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
async def create_organization(
    data: OrganizationCreateRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an organization and assign the creator as Admin."""
    org, _ = await OrgService.create_organization(
        db=db,
        creator=current_user,
        data=data,
    )
    return OrganizationResponse.model_validate(org)


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Get organization details",
)
async def get_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Get organization by ID (strictly verifies caller membership)."""
    org, _ = await OrgService.get_organization_by_id(db, org_id, current_user.id)
    return OrganizationResponse.model_validate(org)


@router.patch(
    "/{org_id}",
    response_model=OrganizationResponse,
    summary="Update organization settings (Admin only)",
)
async def update_organization(
    org_id: uuid.UUID,
    data: OrganizationUpdateRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Update settings for an organization (restricted to Admin role)."""
    updated_org = await OrgService.update_organization(
        db=db,
        org_id=org_id,
        user_id=current_user.id,
        data=data,
    )
    return OrganizationResponse.model_validate(updated_org)


@router.get(
    "/{org_id}/members",
    response_model=OrganizationMemberListResponse,
    summary="List organization members",
)
async def list_members(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """List members and assigned roles in this organization."""
    org, _ = await OrgService.get_organization_by_id(db, org_id, current_user.id)
    members = await OrgService.list_members(db, org_id, current_user.id)
    return OrganizationMemberListResponse(
        organization=OrganizationResponse.model_validate(org),
        members=members,
    )


@router.post(
    "/{org_id}/members",
    response_model=MemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add or invite member (Admin only)",
)
async def add_member(
    org_id: uuid.UUID,
    data: MemberInviteRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Add existing registered user to organization with specified role."""
    member = await OrgService.invite_or_add_member(
        db=db,
        org_id=org_id,
        admin_user_id=current_user.id,
        target_email=data.email,
        role=data.role,
    )
    return member


@router.patch(
    "/{org_id}/members/{target_user_id}",
    response_model=MemberResponse,
    summary="Update member role (Admin only)",
)
async def update_member_role(
    org_id: uuid.UUID,
    target_user_id: uuid.UUID,
    data: MemberRoleUpdateRequest,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Change member's role (Admin only)."""
    member = await OrgService.update_member_role(
        db=db,
        org_id=org_id,
        admin_user_id=current_user.id,
        target_user_id=target_user_id,
        new_role=data.role,
    )
    return member


@router.delete(
    "/{org_id}/members/{target_user_id}",
    response_model=GenericSuccessResponse,
    summary="Remove member (Admin only)",
)
async def remove_member(
    org_id: uuid.UUID,
    target_user_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove member from organization (Admin only)."""
    await OrgService.remove_member(
        db=db,
        org_id=org_id,
        admin_user_id=current_user.id,
        target_user_id=target_user_id,
    )
    return GenericSuccessResponse(status="success", message="Member removed.")


@router.post(
    "/{org_id}/switch",
    response_model=TokenResponse,
    summary="Switch active organization context",
)
async def switch_organization(
    org_id: uuid.UUID,
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Switch active tenant context.
    Strictly verifies user has active membership before issuing fresh JWT bound to this org.
    """
    await OrgService.get_organization_by_id(db, org_id, current_user.id)

    token_payload = {
        "sub": str(current_user.id),
        "email": current_user.email,
        "org_id": str(org_id),
    }
    new_token = create_access_token(token_payload)

    return TokenResponse(
        access_token=new_token,
        token_type="bearer",
        expires_in=900,
        user=UserResponse.model_validate(current_user),
    )
