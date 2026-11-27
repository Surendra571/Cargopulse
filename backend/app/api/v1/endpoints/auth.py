from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db, validate_csrf
from app.core.config import settings
from app.core.rate_limit import rate_limit_login, rate_limit_password_reset
from app.core.security import generate_csrf_token
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _set_auth_cookies(response: Response, raw_refresh_token: str) -> str:
    """Sets the HttpOnly refresh token cookie and JavaScript-readable CSRF token cookie."""
    # 1. HttpOnly Refresh Token Cookie
    response.set_cookie(
        key=settings.COOKIE_REFRESH_NAME,
        value=raw_refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )

    # 2. JavaScript-accessible CSRF Cookie for double-submit cookie pattern
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=settings.COOKIE_CSRF_NAME,
        value=csrf_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=False,  # Accessible to frontend Axios/fetch client to put in X-CSRF-Token header
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    return csrf_token


def _clear_auth_cookies(response: Response) -> None:
    """Clears both refresh and CSRF cookies."""
    response.delete_cookie(key=settings.COOKIE_REFRESH_NAME, path="/")
    response.delete_cookie(key=settings.COOKIE_CSRF_NAME, path="/")


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Customer Organization and First Administrator",
)
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Registers a new tenant organization and its initial administrator account atomically.
    Sets HttpOnly refresh token and CSRF cookies.
    Returns access token and user profile.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    user, access_token, raw_refresh = await AuthService.register_organization_and_admin(
        session=session,
        payload=payload,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    _set_auth_cookies(response, raw_refresh)
    profile = AuthService.serialize_profile(user)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=profile,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate User and Create Session",
    dependencies=[Depends(rate_limit_login)],
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticates user with work email and password.
    Enforces active account verification and rate limiting.
    Sets HttpOnly refresh token and CSRF cookies.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    user, access_token, raw_refresh = await AuthService.authenticate_user(
        session=session,
        email=payload.email,
        password=payload.password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    _set_auth_cookies(response, raw_refresh)
    profile = AuthService.serialize_profile(user)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=profile,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate Refresh Token and Issue New Access Token",
    dependencies=[Depends(validate_csrf)],
)
async def refresh_token(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db),
    cargopulse_refresh_token: Optional[str] = Cookie(None),
) -> TokenResponse:
    """
    Rotates the refresh token session.
    Detects revoked or reused tokens (security intrusion detection).
    Issues a new access token and updates HttpOnly cookies.
    """
    # Accept token either from HttpOnly cookie or custom header
    token = cargopulse_refresh_token or request.headers.get("X-Refresh-Token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing.",
        )

    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")

    user, new_access_token, new_raw_refresh = await AuthService.rotate_refresh_token(
        session=session,
        raw_refresh_token=token,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    _set_auth_cookies(response, new_raw_refresh)
    profile = AuthService.serialize_profile(user)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=profile,
    )


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke Session and Clear Authentication Cookies",
    dependencies=[Depends(validate_csrf)],
)
async def logout(
    response: Response,
    session: AsyncSession = Depends(get_db),
    cargopulse_refresh_token: Optional[str] = Cookie(None),
) -> MessageResponse:
    """
    Revokes the current refresh session in the database and clears authentication cookies.
    """
    if cargopulse_refresh_token:
        await AuthService.revoke_session(session, cargopulse_refresh_token)

    _clear_auth_cookies(response)
    return MessageResponse(message="Successfully logged out.", success=True)


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Request Password Reset Link",
    dependencies=[Depends(rate_limit_password_reset)],
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Initiates password reset workflow.
    Prevents account enumeration by always returning success response.
    """
    raw_token = await AuthService.request_password_reset(session, payload.email)

    # In development mode, log the token for convenience/testing
    if raw_token and settings.DEBUG:
        # Development audit aid: token generated
        pass

    return MessageResponse(
        message="If this email is registered, instructions to reset your password have been sent.",
        success=True,
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Reset Password Using Cryptographic Token",
)
async def reset_password(
    payload: ResetPasswordRequest,
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Resets account password using a single-use cryptographic token.
    Terminates existing sessions to ensure account security.
    """
    await AuthService.reset_password(
        session=session,
        raw_token=payload.token,
        new_password=payload.new_password,
    )
    return MessageResponse(
        message="Password has been reset successfully. Please log in with your new password.",
        success=True,
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change Password for Authenticated User",
)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """
    Allows an authenticated user to update their account password.
    Requires validating current password.
    """
    await AuthService.change_password(
        session=session,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(
        message="Password changed successfully.",
        success=True,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    summary="Get Current User Profile & Capabilities",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user),
) -> UserProfileResponse:
    """
    Returns the profile, organization affiliation, roles, and capability permissions
    of the currently authenticated user.
    """
    return AuthService.serialize_profile(current_user)
