"""
JWT token utilities for authentication.
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from pydantic import BaseModel

from src.config import settings


class TokenData(BaseModel):
    """Token payload data."""
    user_id: int
    email: str
    jti: str
    exp: Optional[datetime] = None


class Token(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


def create_access_token(user_id: int, email: str) -> str:
    """Create a JWT access token with a unique jti for blacklisting."""
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + expires_delta

    to_encode = {
        "user_id": user_id,
        "email": email,
        "exp": expire,
        "type": "access",
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: int, email: str) -> str:
    """Create a JWT refresh token with a unique jti for blacklisting."""
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.utcnow() + expires_delta

    to_encode = {
        "user_id": user_id,
        "email": email,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }

    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> Optional[TokenData]:
    """Verify and decode a JWT token. Returns None if invalid or expired."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )

        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        jti: str = payload.get("jti")

        if user_id is None or email is None or jti is None:
            return None

        return TokenData(
            user_id=user_id,
            email=email,
            jti=jti,
            exp=payload.get("exp"),
        )

    except JWTError:
        return None


def decode_token_unverified(token: str) -> Optional[dict]:
    """Decode a JWT token without verifying the signature (for logout cleanup)."""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_signature": False},
        )
    except JWTError:
        return None
