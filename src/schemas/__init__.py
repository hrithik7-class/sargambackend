"""
Pydantic schemas for authentication and generation.
"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
import bleach


def _sanitize(value: str) -> str:
    """Strip all HTML tags and attributes from a string to prevent stored XSS."""
    return bleach.clean(value, tags=[], attributes={}, strip=True).strip()


# Request schemas
class SignupRequest(BaseModel):
    """Request schema for user signup."""
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)

    @field_validator("full_name", mode="before")
    @classmethod
    def sanitize_full_name(cls, v: str) -> str:
        return _sanitize(v)


class SigninRequest(BaseModel):
    """Request schema for user signin."""
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh."""
    refresh_token: str


class OAuthCallbackRequest(BaseModel):
    """Request schema for OAuth callback."""
    code: str
    state: Optional[str] = None


class VerifyEmailRequest(BaseModel):
    """Request schema for email OTP verification."""
    email: EmailStr
    otp: str = Field(..., min_length=1, max_length=10)

    @field_validator("otp", mode="before")
    @classmethod
    def normalize_otp(cls, v: str) -> str:
        """Strip to digits only (handles paste with spaces/dashes like 123 456)."""
        digits = "".join(c for c in str(v) if c.isdigit())
        if len(digits) != 6:
            raise ValueError("OTP must be 6 digits")
        return digits


class ResendOtpRequest(BaseModel):
    """Request schema for resending OTP."""
    email: EmailStr


# Response schemas
class UserResponse(BaseModel):
    """Response schema for user data."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """Response schema for authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class MessageResponse(BaseModel):
    """Response schema for simple messages."""
    message: str


class VerificationRequiredResponse(BaseModel):
    """Response when signup requires email verification."""
    message: str = "Verification required"
    email: str


class ErrorResponse(BaseModel):
    """Response schema for errors."""
    error: str
    detail: Optional[str] = None


# OAuth schemas
class OAuthUrlResponse(BaseModel):
    """Response schema for OAuth authorization URL."""
    url: str
    state: str


class ProviderEnum(str):
    """OAuth provider type."""
    GOOGLE = "google"
    FACEBOOK = "facebook"


# ─── Generation Schemas ───────────────────────────────────────────────────────

class LyricsGenerateRequest(BaseModel):
    """Request to generate song lyrics from rhyme words / partial lyrics."""
    input_prompt: str = Field(..., min_length=5, max_length=2000,
                              description="Rhyme words, themes, or partial lines")
    language: str = Field(default="english",
                          description="'english' | 'hindi' | 'hinglish' | 'punjabi' | 'auto'")
    genre: str = Field(default="Pop", max_length=100)
    title: Optional[str] = Field(default=None, max_length=255)

    @field_validator("input_prompt", "genre", mode="before")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return _sanitize(v)

    @field_validator("title", mode="before")
    @classmethod
    def sanitize_title(cls, v: Optional[str]) -> Optional[str]:
        return _sanitize(v) if v else v


class LyricsGenerateResponse(BaseModel):
    """Generated lyrics with metadata."""
    lyrics: str
    title: str
    language: str
    genre: str


class AudioGenerateRequest(BaseModel):
    """Request to generate a full singing track from structured lyrics."""
    lyrics: str = Field(..., min_length=30, description="Structured lyrics with [Section] tags")
    title: str = Field(..., min_length=1, max_length=255)
    input_prompt: str = Field(default="", max_length=2000)
    language: str = Field(default="english")
    genre: str = Field(default="Pop", max_length=100)

    @field_validator("title", "input_prompt", "genre", mode="before")
    @classmethod
    def sanitize_text(cls, v: str) -> str:
        return _sanitize(v)


class AudioGenerateResponse(BaseModel):
    """Immediate response when audio generation starts (async)."""
    track_id: int
    status: str


class CopyrightCheckRequest(BaseModel):
    """Request to check if lyrics are too similar to existing songs."""
    lyrics: str = Field(..., min_length=10)
    title: Optional[str] = Field(default=None)


class CopyrightMatch(BaseModel):
    title: str
    artist: str
    similarity: float


class CopyrightCheckResponse(BaseModel):
    """Copyright similarity check result."""
    safe: bool
    score: float
    matches: List[CopyrightMatch]
    note: Optional[str] = None


# ─── Track Schemas ────────────────────────────────────────────────────────────

class TrackResponse(BaseModel):
    """Full track record returned to the client."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    input_prompt: str
    language: str
    genre: str
    generated_lyrics: Optional[str] = None
    audio_url: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    copyright_safe: Optional[bool] = None
    copyright_score: Optional[float] = None
    duration_seconds: Optional[float] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class TrackListResponse(BaseModel):
    """Paginated track list."""
    tracks: List[TrackResponse]
    total: int


# Payment schemas
class CheckoutRequest(BaseModel):
    """Request for creating a checkout (plan slug)."""
    plan: str = Field(..., pattern="^(pro|studio)$")


class LemonSqueezyCheckoutResponse(BaseModel):
    """Response with Lemon Squeezy checkout URL."""
    checkout_url: str


class RazorpayOrderResponse(BaseModel):
    """Response with Razorpay order details for frontend."""
    order_id: str
    key_id: str
    amount: int
    currency: str


class SubscriptionResponse(BaseModel):
    """Current user subscription."""
    plan_slug: str
    provider: str
    current_period_ends_at: Optional[datetime] = None
