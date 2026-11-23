"""
FastAPI Dependency Injection and Authentication Verification.
Enforces multi-tenant isolation, role-based access control, and token parsing.
"""
import uuid
from typing import AsyncGenerator, Callable, List, Optional
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.core.security import decode_access_token
from app.models.user import User
from app.models.organization import Organization, OrganizationMembership
from app.services.org_service import OrgService

security_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injecting an active database session into endpoints."""
    async for session in get_db_session():
        yield session


async def get_current_user(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Extract access token from Bearer header or access_token cookie,
    decode payload, and verify user existence and active status.
    """
    token: Optional[str] = None
    if auth:
        token = auth.credentials
    elif "access_token" in request.cookies:
        token = request.cookies["access_token"]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = uuid.UUID(payload["sub"])
    user = await db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated.",
        )

    return user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure current user has verified their email address."""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified.",
        )
    return current_user


async def get_current_org_membership(
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[Organization, OrganizationMembership]:
    """
    Strict Tenant Isolation Dependency.
    Extracts X-Organization-Id header and verifies that the current authenticated
    user has an ACTIVE membership in that organization.
    Never trusts organization_id without active database membership proof.
    """
    if not x_organization_id:
        user_orgs = await OrgService.get_user_organizations(db, current_user.id)
        if user_orgs:
            return user_orgs[0]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-Organization-Id header and no active organization found.",
        )

    try:
        org_id = uuid.UUID(x_organization_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid X-Organization-Id UUID format.",
        )

    org, membership = await OrgService.get_organization_by_id(db, org_id, current_user.id)
    return org, membership


def require_role(allowed_roles: List[str]) -> Callable:
    """
    Dependency factory asserting that the user's role in the active
    organization matches one of the allowed roles.
    Includes CONTROLLER as an authorized finance managerial role.
    """
    normalized_allowed = {r.upper() for r in allowed_roles}
    if "FINANCE_MANAGER" in normalized_allowed or "ACCOUNTANT" in normalized_allowed:
        normalized_allowed.add("CONTROLLER")

    async def role_checker(
        org_and_membership: tuple[Organization, OrganizationMembership] = Depends(get_current_org_membership),
    ) -> tuple[Organization, OrganizationMembership]:
        _, membership = org_and_membership
        user_role = (membership.role or "").upper()

        if user_role == "ADMIN" or user_role in normalized_allowed:
            return org_and_membership

        if user_role == "CONTROLLER" and (
            "FINANCE_MANAGER" in normalized_allowed
            or "CONTROLLER" in normalized_allowed
            or "ACCOUNTANT" in normalized_allowed
        ):
            return org_and_membership

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}.",
        )

    return role_checker
