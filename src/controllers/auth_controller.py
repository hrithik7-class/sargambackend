"""
Authentication controller - handles HTTP requests for authentication.
"""
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status, Depends, Header, Request
from sqlalchemy.orm import Session
from typing import Optional, List

from src.database import get_db
from src.schemas import (
    SignupRequest,
    SigninRequest,
    TokenResponse,
    OAuthUrlResponse,
    MessageResponse,
    UserResponse,
    VerifyEmailRequest,
    ResendOtpRequest,
)
from src.services import auth_service, oauth_service
from src.services.auth_service import VerificationRequiredError
from src.utils.token import verify_token, decode_token_unverified, create_access_token
from src.cache import cache
from src.config import settings


def _extract_ip(request: Request) -> str:
    """Extract real client IP, honouring X-Forwarded-For when behind a proxy."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_current_user_from_header(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    """
    Dependency: extract and validate Bearer token from Authorization header.
    Returns the authenticated User or raises 401.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1]
    token_data = verify_token(token)

    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check blacklist
    if cache.is_token_blacklisted(token_data.jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_service.get_user_by_id(db, token_data.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated",
        )

    # Single-device enforcement for premium users
    if getattr(user, "is_premium", False):
        stored_jti = cache.get_active_session(user.id)
        if stored_jti and stored_jti != token_data.jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is active on another device",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return user


class AuthController:
    """Controller for handling authentication HTTP requests."""

    @staticmethod
    def signup(request: SignupRequest, db: Session, **kwargs):
        """Register a new user with email and password. Raises VerificationRequiredError if verification needed."""
        try:
            return auth_service.signup(
                db=db,
                email=request.email,
                full_name=request.full_name,
                password=request.password,
            )
        except VerificationRequiredError:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    @staticmethod
    def signin(request: SigninRequest, db: Session, http_request: Optional[Request] = None, **kwargs) -> TokenResponse:
        """Sign in with email and password, logging the event."""
        try:
            result = auth_service.signin(
                db=db,
                email=request.email,
                password=request.password,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            )

        # Log login event
        if http_request:
            user = auth_service.get_user_by_email(db, request.email)
            if user:
                ip = _extract_ip(http_request)
                ua = http_request.headers.get("User-Agent", "")
                cache.log_login_event(user.id, ip, ua)

                # Single-device enforcement for premium users
                if getattr(user, "is_premium", False):
                    token_data = decode_token_unverified(result.access_token)
                    if token_data:
                        new_jti = token_data.get("jti")
                        old_jti = cache.get_active_session(user.id)
                        if old_jti and old_jti != new_jti:
                            # Blacklist the previous device's token
                            cache.blacklist_token(old_jti, ttl_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
                        if new_jti:
                            cache.set_active_session(user.id, new_jti, ttl=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

        return result

    @staticmethod
    def refresh_token(refresh_token: str, db: Session = Depends(get_db)) -> TokenResponse:
        """Refresh access token using refresh token."""
        token_data = verify_token(refresh_token)

        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        # Check expiry explicitly
        if token_data.exp:
            exp_dt = (
                datetime.fromtimestamp(token_data.exp, tz=timezone.utc)
                if isinstance(token_data.exp, (int, float))
                else token_data.exp.replace(tzinfo=timezone.utc)
            )
            if exp_dt < datetime.now(tz=timezone.utc):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token has expired",
                )

        # Check blacklist
        if cache.is_token_blacklisted(token_data.jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        user = auth_service.get_user_by_id(db, token_data.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated",
            )

        # Blacklist the used refresh token before issuing new tokens
        cache.blacklist_token(
            jti=token_data.jti,
            ttl_seconds=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )

        new_result = auth_service.create_token_response(user)

        # Update active session for premium users
        if getattr(user, "is_premium", False):
            new_token_data = decode_token_unverified(new_result.access_token)
            if new_token_data:
                new_jti = new_token_data.get("jti")
                if new_jti:
                    cache.set_active_session(user.id, new_jti, ttl=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

        return new_result

    @staticmethod
    def get_me(user=Depends(_get_current_user_from_header)) -> UserResponse:
        """Return the authenticated user's profile."""
        return UserResponse.model_validate(user)

    @staticmethod
    def get_login_history(user) -> dict:
        """Return the last 10 login events for the authenticated user."""
        events = cache.get_login_history(user.id)
        return {"events": events, "count": len(events)}

    @staticmethod
    def get_google_oauth_url() -> OAuthUrlResponse:
        """Get Google OAuth authorization URL."""
        if not oauth_service.google_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth is not configured",
            )

        state = secrets.token_urlsafe(32)

        try:
            url = oauth_service.get_google_auth_url(state)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )

        return OAuthUrlResponse(url=url, state=state)

    @staticmethod
    def get_facebook_oauth_url() -> OAuthUrlResponse:
        """Get Facebook OAuth authorization URL."""
        if not oauth_service.facebook_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Facebook OAuth is not configured",
            )

        state = secrets.token_urlsafe(32)

        try:
            url = oauth_service.get_facebook_auth_url(state)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(e),
            )

        return OAuthUrlResponse(url=url, state=state)

    @staticmethod
    async def google_callback(code: str, db: Session, request: Optional[Request] = None, **kwargs) -> TokenResponse:
        """Handle Google OAuth callback."""
        if not oauth_service.google_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google OAuth is not configured",
            )

        try:
            access_token, _ = await oauth_service.exchange_google_code(code)
            userinfo = await oauth_service.get_google_userinfo(access_token)
            user = oauth_service.process_google_user(db, userinfo)

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account has been deactivated",
                )

            result = auth_service.create_token_response(user)

            if request:
                ip = _extract_ip(request)
                ua = request.headers.get("User-Agent", "")
                cache.log_login_event(user.id, ip, ua)

                if getattr(user, "is_premium", False):
                    token_data = decode_token_unverified(result.access_token)
                    if token_data:
                        new_jti = token_data.get("jti")
                        old_jti = cache.get_active_session(user.id)
                        if old_jti and old_jti != new_jti:
                            cache.blacklist_token(old_jti, ttl_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
                        if new_jti:
                            cache.set_active_session(user.id, new_jti, ttl=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

            return result

        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process Google OAuth callback: {str(e)}",
            )

    @staticmethod
    async def facebook_callback(code: str, db: Session, request: Optional[Request] = None, **kwargs) -> TokenResponse:
        """Handle Facebook OAuth callback."""
        if not oauth_service.facebook_config:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Facebook OAuth is not configured",
            )

        try:
            access_token, _ = await oauth_service.exchange_facebook_code(code)
            userinfo = await oauth_service.get_facebook_userinfo(access_token)
            user = oauth_service.process_facebook_user(db, userinfo)

            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your account has been deactivated",
                )

            result = auth_service.create_token_response(user)

            if request:
                ip = _extract_ip(request)
                ua = request.headers.get("User-Agent", "")
                cache.log_login_event(user.id, ip, ua)

                if getattr(user, "is_premium", False):
                    token_data = decode_token_unverified(result.access_token)
                    if token_data:
                        new_jti = token_data.get("jti")
                        old_jti = cache.get_active_session(user.id)
                        if old_jti and old_jti != new_jti:
                            cache.blacklist_token(old_jti, ttl_seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
                        if new_jti:
                            cache.set_active_session(user.id, new_jti, ttl=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

            return result

        except HTTPException:
            raise
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process Facebook OAuth callback: {str(e)}",
            )

    @staticmethod
    def verify_email(body: VerifyEmailRequest, db: Session, **kwargs) -> TokenResponse:
        """Verify email OTP and return tokens."""
        try:
            return auth_service.verify_email(db, body.email, body.otp)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    @staticmethod
    def resend_otp(body: ResendOtpRequest, db: Session, **kwargs) -> MessageResponse:
        """Resend OTP to email. Rate limited to 1/min per email."""
        try:
            auth_service.resend_otp(db, body.email)
            return MessageResponse(message="Verification code sent")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    @staticmethod
    def logout(authorization: Optional[str] = Header(None)) -> MessageResponse:
        """
        Log out user by blacklisting the access token's jti in Redis.
        The token can no longer be used even before it expires.
        """
        if not authorization or not authorization.startswith("Bearer "):
            return MessageResponse(message="Successfully logged out")

        token = authorization.split(" ", 1)[1]
        payload = decode_token_unverified(token)

        if payload:
            jti = payload.get("jti")
            exp = payload.get("exp")
            user_id = payload.get("sub")

            if jti and exp:
                now_ts = int(datetime.now(tz=timezone.utc).timestamp())
                ttl = max(int(exp) - now_ts, 1)
                cache.blacklist_token(jti=jti, ttl_seconds=ttl)
                cache.delete_session(payload.get("email", ""))

            # Clear premium active session
            if user_id:
                try:
                    cache.clear_active_session(int(user_id))
                except (ValueError, TypeError):
                    pass

        return MessageResponse(message="Successfully logged out")
