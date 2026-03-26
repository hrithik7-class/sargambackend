"""
Authentication service - handles business logic for authentication.
"""
import logging
import secrets
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from src.models import User, OAuthAccount

logger = logging.getLogger(__name__)
from src.utils.password import hash_password, verify_password
from src.utils.token import create_access_token, create_refresh_token
from src.schemas import TokenResponse, UserResponse, VerificationRequiredResponse
from src.cache import cache


class VerificationRequiredError(Exception):
    """Raised when signup succeeds but email verification is pending."""
    def __init__(self, email: str):
        self.email = email
        super().__init__(f"Verification required for {email}")


class AuthService:
    """Service for handling authentication logic."""
    
    @staticmethod
    def create_token_response(user: User) -> TokenResponse:
        """Create token response for a user."""
        access_token = create_access_token(user.id, user.email)
        refresh_token = create_refresh_token(user.id, user.email)
        
        # Store session in Redis
        cache.set_session(
            session_id=user.email,
            user_data={
                "user_id": user.id,
                "email": user.email,
                "full_name": user.full_name,
            },
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user),
        )
    
    @staticmethod
    def signup(db: Session, email: str, full_name: str, password: str) -> TokenResponse:
        """Register a new user with email and password. Sends OTP; raises VerificationRequiredError."""
        # Check if user already exists
        existing_user = db.query(User).filter(
            or_(User.email == email)
        ).first()
        
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Check if user has OAuth account with same email
        oauth_account = db.query(OAuthAccount).join(User).filter(
            User.email == email
        ).first()
        
        if oauth_account:
            raise ValueError(
                "An account with this email already exists. Please sign in with your OAuth provider."
            )
        
        # Create new user
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            is_verified=False,
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Generate OTP, store in Redis, send email
        otp = "".join(secrets.choice("0123456789") for _ in range(6))
        if not cache.set_otp(email, otp):
            raise ValueError("Unable to store verification code. Please try again.")

        from src.config import settings
        from src.services.email_service import send_verification_email

        try:
            send_verification_email(email, otp)
        except ValueError as e:
            # SMTP not configured — in DEBUG mode, auto-verify and return tokens for local dev
            if settings.DEBUG:
                user.is_verified = True
                db.commit()
                db.refresh(user)
                cache.delete_otp(email)
                return AuthService.create_token_response(user)
            cache.delete_otp(email)
            raise
        except Exception as e:
            cache.delete_otp(email)
            raise ValueError(f"Failed to send verification email: {e}")

        raise VerificationRequiredError(email)
    
    @staticmethod
    def signin(db: Session, email: str, password: str) -> TokenResponse:
        """Sign in with email and password."""
        # Find user by email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            raise ValueError("Invalid email or password")
        
        # Check if user has password
        if not user.hashed_password:
            raise ValueError("Please sign in with your OAuth provider")
        
        # Verify password
        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")
        
        # Block unverified email users
        if not user.is_verified:
            raise ValueError("Please verify your email. Check your inbox for the OTP.")
        
        # Check if user is active
        if not user.is_active:
            raise ValueError("Your account has been deactivated")
        
        return AuthService.create_token_response(user)
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """Get user by ID."""
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """Get user by email."""
        return db.query(User).filter(User.email == email).first()
    
    @staticmethod
    def logout(user_email: str) -> bool:
        """Logout user by removing session from Redis."""
        return cache.delete_session(user_email)

    @staticmethod
    def verify_email(db: Session, email: str, otp: str) -> TokenResponse:
        """Verify OTP and return tokens. Raises ValueError if invalid."""
        from src.config import settings
        email_lower = email.strip().lower()
        user = db.query(User).filter(func.lower(User.email) == email_lower).first()
        if not user:
            raise ValueError("Invalid email or OTP")
        if settings.DEBUG:
            found = cache.get_otp(email) is not None
            logger.debug("OTP verify: email=%s*** found=%s", email[:3] if len(email) >= 3 else "?", found)
        if not cache.verify_otp(email, otp):
            raise ValueError("Invalid or expired OTP")
        user.is_verified = True
        db.commit()
        db.refresh(user)
        return AuthService.create_token_response(user)

    @staticmethod
    def resend_otp(db: Session, email: str) -> None:
        """Regenerate OTP and resend email. Rate limit: 1/min per email."""
        from src.services.email_service import send_verification_email
        email_lower = email.strip().lower()
        cooldown_key = f"resend_otp_cooldown:{email_lower}"
        if cache.exists(cooldown_key):
            raise ValueError("Please wait a minute before requesting another code.")
        user = db.query(User).filter(func.lower(User.email) == email_lower).first()
        if not user:
            raise ValueError("No account found with this email")
        if user.is_verified:
            raise ValueError("Email is already verified")
        otp = "".join(secrets.choice("0123456789") for _ in range(6))
        cache.set_otp(user.email, otp)  # Use stored email for consistency
        cache.set(cooldown_key, "1", expire=60)
        send_verification_email(user.email, otp)


# Create singleton instance
auth_service = AuthService()
