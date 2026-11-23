"""
Authentication and Session Endpoints.
Implements registration, email activation, secure login with HttpOnly refresh cookies,
session rotation, and enumeration-protected password resets.
"""
from typing import Optional
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user, get_current_verified_user
from app.core.config import settings
from app.core.rate_limit import auth_rate_limiter
from app.models.user import User
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    EmailVerifyRequest,
    OTPVerifyRequest,
    OTPResendRequest,
    PasswordResetRequest,
    PasswordResetConfirmRequest,
    UserProfileResponse,
    OrgMembershipBrief,
    GenericSuccessResponse,
)
from app.services.auth_service import AuthService
from app.services.org_service import OrgService

router = APIRouter(prefix="/auth", tags=["Authentication & Sessions"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
async def register(
    request: Request,
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Register new account, generate activation token, and dispatch email."""
    # Apply rate limiting per IP
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.check_or_raise(f"register:{client_ip}", max_requests=10, window_seconds=60)

    user, otp = await AuthService.register_user(
        db=db,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
    )
    user_resp = UserResponse.model_validate(user)
    user_resp.otp = otp
    return user_resp


@router.post(
    "/verify-otp",
    response_model=TokenResponse,
    summary="Verify user email with 6-digit OTP",
)
async def verify_otp(
    request: Request,
    response: Response,
    data: OTPVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify email via 6-digit OTP and establish active session."""
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent")
    user, access_token, raw_refresh_token = await AuthService.verify_otp(
        db=db,
        email=data.email,
        otp=data.otp,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/resend-otp",
    response_model=GenericSuccessResponse,
    summary="Resend 6-digit verification OTP",
)
async def resend_otp(
    data: OTPResendRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate and dispatch a new 6-digit OTP."""
    otp = await AuthService.resend_otp(db=db, email=data.email)
    msg = f"A new verification OTP has been sent to {data.email}."
    if settings.DEBUG or settings.ENVIRONMENT != "production":
        msg += f" (Dev OTP: {otp})"
    return GenericSuccessResponse(status="success", message=msg)


@router.post(
    "/logout",
    response_model=GenericSuccessResponse,
    summary="Sign out and clear session",
)
async def logout(
    response: Response,
):
    """Clear HttpOnly session cookies."""
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return GenericSuccessResponse(status="success", message="Successfully signed out.")


@router.post(
    "/verify-email",
    response_model=GenericSuccessResponse,
    summary="Verify user email address",
)
async def verify_email(
    data: EmailVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify email via one-time cryptographically secure token."""
    await AuthService.verify_email(db=db, raw_token=data.token)
    return GenericSuccessResponse(
        status="success",
        message="Email successfully verified. You may now log in.",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and establish session",
)
async def login(
    request: Request,
    response: Response,
    data: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with credentials, issue access token, and set HttpOnly refresh cookie."""
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.check_or_raise(f"login:{client_ip}:{data.email}", max_requests=5, window_seconds=60)

    user_agent = request.headers.get("user-agent")
    user, access_token, raw_refresh_token = await AuthService.authenticate_user(
        db=db,
        email=data.email,
        password=data.password,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    # Set secure HttpOnly cookie for refresh token
    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue fresh access token",
)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Rotate refresh token family and issue new access token."""
    raw_refresh = request.cookies.get("refresh_token")
    if not raw_refresh:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    user_agent = request.headers.get("user-agent")
    client_ip = request.client.host if request.client else "unknown"

    user, access_token, new_refresh = await AuthService.refresh_session(
        db=db,
        raw_refresh_token=raw_refresh,
        user_agent=user_agent,
        ip_address=client_ip,
    )

    is_prod = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/logout",
    response_model=GenericSuccessResponse,
    summary="Revoke session and clear cookies",
)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Revoke active session and delete refresh cookie."""
    raw_refresh = request.cookies.get("refresh_token")
    await AuthService.logout(db=db, raw_refresh_token=raw_refresh)

    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return GenericSuccessResponse(status="success", message="Successfully logged out.")


@router.post(
    "/forgot-password",
    response_model=GenericSuccessResponse,
    summary="Request password reset email",
)
async def forgot_password(
    request: Request,
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request password reset link. Response is constant to prevent user enumeration."""
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.check_or_raise(f"pwd_reset:{client_ip}", max_requests=5, window_seconds=60)

    await AuthService.request_password_reset(db=db, email=data.email)
    return GenericSuccessResponse(
        status="success",
        message="If an account exists with this email address, password reset instructions have been sent.",
    )


@router.post(
    "/reset-password",
    response_model=GenericSuccessResponse,
    summary="Reset password using one-time token",
)
async def reset_password(
    data: PasswordResetConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset with token."""
    await AuthService.reset_password(
        db=db,
        raw_token=data.token,
        new_password=data.new_password,
    )
    return GenericSuccessResponse(
        status="success",
        message="Password has been reset successfully. Please log in with your new password.",
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get current user profile and memberships",
)
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return authenticated user profile and all active organization memberships."""
    memberships = await OrgService.get_user_organizations(db, current_user.id)
    org_briefs = [
        OrgMembershipBrief(
            organization_id=org.id,
            organization_name=org.name,
            organization_slug=org.slug,
            role=mem.role,
            is_active=mem.is_active,
        )
        for org, mem in memberships
    ]

    active_org_id = org_briefs[0].organization_id if org_briefs else None

    return UserProfileResponse(
        user=UserResponse.model_validate(current_user),
        memberships=org_briefs,
        active_organization_id=active_org_id,
    )
