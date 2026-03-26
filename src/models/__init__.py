"""
Database models for the application.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Text, Float, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class OAuthProvider(str, enum.Enum):
    """OAuth provider types."""
    GOOGLE = "google"
    FACEBOOK = "facebook"


class TrackStatus(str, enum.Enum):
    """Status of a generated track."""
    PENDING = "pending"
    GENERATING_AUDIO = "generating_audio"
    COMPLETED = "completed"
    FAILED = "failed"


class PaymentProvider(str, enum.Enum):
    """Payment provider for subscriptions."""
    LEMON_SQUEEZY = "lemonsqueezy"
    RAZORPAY = "razorpay"


class SubscriptionStatus(str, enum.Enum):
    """Subscription status."""
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    PAST_DUE = "past_due"


class User(Base):
    """User model for authentication."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(
        "OAuthAccount", back_populates="user", cascade="all, delete-orphan"
    )
    tracks: Mapped[list["Track"]] = relationship(
        "Track", back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class OAuthAccount(Base):
    """OAuth account model for social login."""
    __tablename__ = "oauth_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[OAuthProvider] = mapped_column(SQLEnum(OAuthProvider), nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="oauth_accounts")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:
        return f"<OAuthAccount(provider={self.provider}, provider_user_id={self.provider_user_id})>"


class Track(Base):
    """AI-generated music track model."""
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # The raw input the user gave (rhyme words / partial lyrics)
    input_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), default="english", nullable=False)
    genre: Mapped[str] = mapped_column(String(100), default="Pop", nullable=False)
    generated_lyrics: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Relative path served by FastAPI static files, e.g. /media/tracks/42.mp3
    audio_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[TrackStatus] = mapped_column(
        SQLEnum(TrackStatus, name="trackstatus"), default=TrackStatus.PENDING, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Copyright: True = safe, False = potential match, None = not checked
    copyright_safe: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # 0–100: highest similarity score found (lower is safer)
    copyright_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="tracks")

    def __repr__(self) -> str:
        return f"<Track(id={self.id}, title={self.title!r}, status={self.status})>"


class Subscription(Base):
    """Subscription from Lemon Squeezy or Razorpay."""
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[PaymentProvider] = mapped_column(
        SQLEnum(PaymentProvider, name="paymentprovider"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    plan_slug: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[SubscriptionStatus] = mapped_column(
        SQLEnum(SubscriptionStatus, name="subscriptionstatus"), default=SubscriptionStatus.ACTIVE, nullable=False
    )
    current_period_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="subscriptions")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, provider={self.provider}, plan={self.plan_slug})>"
