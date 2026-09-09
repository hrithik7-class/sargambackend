"""
Application configuration using Pydantic Settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/sargamdb"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 10
    
    # JWT Settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # OAuth - Google
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    
    # OAuth - Facebook
    FACEBOOK_CLIENT_ID: Optional[str] = None
    FACEBOOK_CLIENT_SECRET: Optional[str] = None
    
    # Frontend URL
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Server
    DEBUG: bool = False
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # AI — Lyrics generation (Groq)
    # Sign up free at https://console.groq.com/
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # AI — Music synthesis (choose one provider)
    # MUSIC_PROVIDER: replicate | fal | huggingface (default: first with valid token)
    MUSIC_PROVIDER: str = ""
    # Replicate — MiniMax Music 2.5 (lyrics → full song with vocals). Paid after free credits.
    REPLICATE_API_TOKEN: Optional[str] = None
    # Fal.ai — MusicGen (text → instrumental). Free credits for new signups. https://fal.ai
    FAL_KEY: Optional[str] = None
    # Hugging Face — MusicGen (text → instrumental). Free tier. https://huggingface.co/settings/tokens
    HUGGINGFACE_TOKEN: Optional[str] = None

    # Copyright check (Genius API)
    # Register at https://genius.com/api-clients
    GENIUS_ACCESS_TOKEN: Optional[str] = None

    # Local storage for generated audio files
    MEDIA_DIR: str = "media/tracks"

    # Rate limiting (slowapi format: "N/period")
    RATE_LIMIT_AUTH: str = "5/minute"       # signup, signin, OAuth callbacks
    RATE_LIMIT_GENERATE: str = "10/minute"  # lyrics + audio generation
    RATE_LIMIT_API: str = "60/minute"       # general authenticated endpoints

    # Lemon Squeezy — https://docs.lemonsqueezy.com/
    LEMON_SQUEEZY_API_KEY: Optional[str] = None
    LEMON_SQUEEZY_STORE_ID: Optional[str] = None
    LEMON_SQUEEZY_WEBHOOK_SECRET: Optional[str] = None
    LEMON_SQUEEZY_VARIANT_PRO: Optional[str] = None   # variant ID for Pro plan
    LEMON_SQUEEZY_VARIANT_STUDIO: Optional[str] = None  # variant ID for Studio plan

    # SMTP for email verification (OTP) — Gmail: use App Password
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: str = "noreply@sargamai.com"

    # Razorpay — https://razorpay.com/docs/
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    RAZORPAY_PLAN_PRO_AMOUNT: int = 1200   # Pro plan amount in paise (1200 = 12 INR or 12 USD cents if currency allows)
    RAZORPAY_PLAN_STUDIO_AMOUNT: int = 2900  # Studio plan in paise (2900 = 29 INR)
    RAZORPAY_CURRENCY: str = "INR"
    
    @property
    def google_oauth_config(self) -> Optional[dict]:
        """Get Google OAuth configuration if available."""
        if self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET:
            return {
                "client_id": self.GOOGLE_CLIENT_ID,
                "client_secret": self.GOOGLE_CLIENT_SECRET,
            }
        return None
    
    @property
    def facebook_oauth_config(self) -> Optional[dict]:
        """Get Facebook OAuth configuration if available."""
        if self.FACEBOOK_CLIENT_ID and self.FACEBOOK_CLIENT_SECRET:
            return {
                "client_id": self.FACEBOOK_CLIENT_ID,
                "client_secret": self.FACEBOOK_CLIENT_SECRET,
            }
        return None


# Create singleton instance
settings = Settings()
