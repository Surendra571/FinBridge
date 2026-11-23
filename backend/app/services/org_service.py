"""
Organization Management and Membership Service.
Enforces multi-tenant scoping and role permissions.
"""
import uuid
from typing import List, Optional, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.organization import Organization, OrganizationMembership
from app.models.user import User
from app.schemas.organization import (
    OrganizationCreateRequest,
    OrganizationUpdateRequest,
    MemberResponse,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


class OrgService:
    @staticmethod
    async def create_organization(
        db: AsyncSession,
        creator: User,
        data: OrganizationCreateRequest,
    ) -> Tuple[Organization, OrganizationMembership]:
        """
        Create a new organization and grant the creator the ADMIN role.
        """
        # Ensure slug uniqueness
        query = select(Organization).where(Organization.slug == data.slug)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Organization with slug '{data.slug}' already exists.",
            )

        org = Organization(
            name=data.name.strip(),
            slug=data.slug,
            base_currency=data.base_currency,
            settings=data.settings or {},
            is_active=True,
        )
        db.add(org)
        await db.flush()

        # Add creator as ADMIN
        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=creator.id,
            role="ADMIN",
            is_active=True,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(org)
        await db.refresh(membership)

        logger.info("Organization created", org_id=str(org.id), creator_id=str(creator.id))
        return org, membership

    @staticmethod
    async def get_user_organizations(
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[Tuple[Organization, OrganizationMembership]]:
        """List all organizations where user is an active member."""
        query = (
            select(Organization, OrganizationMembership)
            .join(OrganizationMembership, Organization.id == OrganizationMembership.organization_id)
            .where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.is_active.is_(True),
                Organization.is_active.is_(True),
            )
            .order_by(Organization.created_at.asc())
        )
        result = await db.execute(query)
        return list(result.all())

    @staticmethod
    async def get_organization_by_id(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Tuple[Organization, OrganizationMembership]:
        """
        Retrieve organization by ID, strictly verifying that the user has membership.
        """
        query = (
            select(Organization, OrganizationMembership)
            .join(OrganizationMembership, Organization.id == OrganizationMembership.organization_id)
            .where(
                Organization.id == org_id,
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.is_active.is_(True),
                Organization.is_active.is_(True),
            )
        )
        result = await db.execute(query)
        pair = result.first()

        if not pair:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found or you do not have permission to access it.",
            )

        return pair

    @staticmethod
    async def update_organization(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        data: OrganizationUpdateRequest,
    ) -> Organization:
        """Update organization details (requires ADMIN role)."""
        org, membership = await OrgService.get_organization_by_id(db, org_id, user_id)
        if membership.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Organization Admins can modify organization settings.",
            )

        if data.name is not None:
            org.name = data.name.strip()
        if data.base_currency is not None:
            org.base_currency = data.base_currency.strip().upper()
        if data.settings is not None:
            current_settings = dict(org.settings or {})
            current_settings.update(data.settings)
            org.settings = current_settings

        await db.commit()
        await db.refresh(org)
        return org

    @staticmethod
    async def list_members(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> List[MemberResponse]:
        """List all members of an organization."""
        # Verify caller membership
        await OrgService.get_organization_by_id(db, org_id, user_id)

        query = (
            select(OrganizationMembership, User)
            .join(User, OrganizationMembership.user_id == User.id)
            .where(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.is_active.is_(True),
            )
            .order_by(OrganizationMembership.created_at.asc())
        )
        result = await db.execute(query)
        records = result.all()

        return [
            MemberResponse(
                id=membership.id,
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=membership.role,
                is_active=membership.is_active,
                created_at=membership.created_at,
            )
            for membership, user in records
        ]

    @staticmethod
    async def invite_or_add_member(
        db: AsyncSession,
        org_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        target_email: str,
        role: str,
    ) -> MemberResponse:
        """Invite or add user to an organization with a specific role (ADMIN only)."""
        _, admin_membership = await OrgService.get_organization_by_id(db, org_id, admin_user_id)
        if admin_membership.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Organization Admins can add or invite members.",
            )

        # Look up target user
        user_query = select(User).where(User.email == target_email.lower().strip())
        user_res = await db.execute(user_query)
        target_user = user_res.scalar_one_or_none()

        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User with this email not found. They must register an account first.",
            )

        # Check existing membership
        mem_query = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == target_user.id,
        )
        mem_res = await db.execute(mem_query)
        existing_mem = mem_res.scalar_one_or_none()

        if existing_mem:
            if existing_mem.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="User is already a member of this organization.",
                )
            existing_mem.is_active = True
            existing_mem.role = role
            membership = existing_mem
        else:
            membership = OrganizationMembership(
                organization_id=org_id,
                user_id=target_user.id,
                role=role,
                is_active=True,
            )
            db.add(membership)

        await db.commit()
        await db.refresh(membership)

        return MemberResponse(
            id=membership.id,
            user_id=target_user.id,
            email=target_user.email,
            full_name=target_user.full_name,
            role=membership.role,
            is_active=membership.is_active,
            created_at=membership.created_at,
        )

    @staticmethod
    async def update_member_role(
        db: AsyncSession,
        org_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        new_role: str,
    ) -> MemberResponse:
        """Update role of an organization member (ADMIN only)."""
        _, admin_membership = await OrgService.get_organization_by_id(db, org_id, admin_user_id)
        if admin_membership.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Organization Admins can modify member roles.",
            )

        # Retrieve target membership
        query = (
            select(OrganizationMembership, User)
            .join(User, OrganizationMembership.user_id == User.id)
            .where(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.user_id == target_user_id,
                OrganizationMembership.is_active.is_(True),
            )
        )
        result = await db.execute(query)
        record = result.first()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found in this organization.",
            )

        membership, target_user = record
        membership.role = new_role
        await db.commit()
        await db.refresh(membership)

        return MemberResponse(
            id=membership.id,
            user_id=target_user.id,
            email=target_user.email,
            full_name=target_user.full_name,
            role=membership.role,
            is_active=membership.is_active,
            created_at=membership.created_at,
        )

    @staticmethod
    async def remove_member(
        db: AsyncSession,
        org_id: uuid.UUID,
        admin_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
    ) -> None:
        """Remove member from organization (ADMIN only; cannot remove self if sole admin)."""
        _, admin_membership = await OrgService.get_organization_by_id(db, org_id, admin_user_id)
        if admin_membership.role != "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Organization Admins can remove members.",
            )

        if admin_user_id == target_user_id:
            # Check if there are other admins
            admin_count_q = select(OrganizationMembership).where(
                OrganizationMembership.organization_id == org_id,
                OrganizationMembership.role == "ADMIN",
                OrganizationMembership.is_active.is_(True),
            )
            admin_count = len((await db.execute(admin_count_q)).all())
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot leave organization: you are the sole administrator.",
                )

        query = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == target_user_id,
        )
        result = await db.execute(query)
        membership = result.scalar_one_or_none()
        if membership:
            membership.is_active = False
            await db.commit()
