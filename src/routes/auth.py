"""
Authentication routes - HTTP endpoints for authentication.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional

from src.database import get_db
from src.schemas import (
    SignupRequest,
    SigninRequest,
    TokenResponse,
    OAuthUrlResponse,
    MessageResponse,
    UserResponse,
    VerificationRequiredResponse,
    VerifyEmailRequest,
    ResendOtpRequest,
)
from src.controllers import AuthController
from src.controllers.auth_controller import _get_current_user_from_header
from src.services.auth_service import VerificationRequiredError
from src.limiter import limiter
from src.config import settings

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/signup")
@limiter.limit(settings.RATE_LIMIT_AUTH)
def signup(request: Request, body: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user with email and password. Returns 202 if verification required."""
    try:
        result = AuthController.signup(body, db)
        return result
    except VerificationRequiredError as e:
        return JSONResponse(
            status_code=202,
            content=VerificationRequiredResponse(message="Verification required", email=e.email).model_dump(),
        )


@router.post("/verify-email", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def verify_email(request: Request, body: VerifyEmailRequest, db: Session = Depends(get_db)):
    """Verify email OTP and return tokens."""
    return AuthController.verify_email(body, db)


@router.post("/resend-otp", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def resend_otp(request: Request, body: ResendOtpRequest, db: Session = Depends(get_db)):
    """Resend OTP to email. Rate limited to 1/min per email."""
    return AuthController.resend_otp(body, db)


@router.get("/debug/otp-exists")
def debug_otp_exists(request: Request, email: str = Query("")):
    """DEBUG only: Check if OTP exists for email. Returns 404 when DEBUG is false."""
    if not settings.DEBUG or not email:
        raise HTTPException(status_code=404, detail="Not found")
    from src.cache import cache
    exists = cache.get_otp(email) is not None
    return {"email": email[:3] + "***", "otp_exists": exists}


@router.post("/signin", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
def signin(request: Request, body: SigninRequest, db: Session = Depends(get_db)):
    """Sign in with email and password."""
    return AuthController.signin(body, db, http_request=request)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def refresh_token(request: Request, refresh_token: str, db: Session = Depends(get_db)):
    """Refresh access token using refresh token."""
    return AuthController.refresh_token(refresh_token, db)


@router.get("/me", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def get_me(request: Request, user=Depends(_get_current_user_from_header)):
    """Return the currently authenticated user's profile."""
    return UserResponse.model_validate(user)


# OAuth Routes
@router.get("/oauth/google", response_model=OAuthUrlResponse)
def get_google_oauth_url():
    """Get Google OAuth authorization URL."""
    return AuthController.get_google_oauth_url()


@router.get("/oauth/facebook", response_model=OAuthUrlResponse)
def get_facebook_oauth_url():
    """Get Facebook OAuth authorization URL."""
    return AuthController.get_facebook_oauth_url()


@router.get("/callback/google", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def google_callback(request: Request, code: str, db: Session = Depends(get_db)):
    """Handle Google OAuth callback."""
    return await AuthController.google_callback(code, db, request=request)


@router.post("/oauth/google/token", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def google_token_signin(request: Request, body: dict, db: Session = Depends(get_db)):
    """Sign in with a Google access token (used by NextAuth after it handles the OAuth flow)."""
    from src.services.oauth_service import oauth_service
    from src.services.auth_service import auth_service
    from fastapi import HTTPException, status
    access_token = body.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="access_token required")
    try:
        userinfo = await oauth_service.get_google_userinfo(access_token)
        user = oauth_service.process_google_user(db, userinfo)
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your account has been deactivated")
        return auth_service.create_token_response(user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Google sign-in failed: {e}")


@router.get("/callback/facebook", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_AUTH)
async def facebook_callback(request: Request, code: str, db: Session = Depends(get_db)):
    """Handle Facebook OAuth callback."""
    return await AuthController.facebook_callback(code, db, request=request)


@router.post("/logout", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def logout(request: Request, authorization: Optional[str] = Header(None)):
    """Log out user — blacklists the access token jti in Redis."""
    return AuthController.logout(authorization)


@router.get("/login-history")
@limiter.limit(settings.RATE_LIMIT_API)
def login_history(request: Request, user=Depends(_get_current_user_from_header)):
    """Return the last 10 login events for the authenticated user."""
    return AuthController.get_login_history(user)
