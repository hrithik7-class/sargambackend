"""
OAuth authentication service for Google and Facebook.
"""
from typing import Tuple
from urllib.parse import urlencode
import httpx
from sqlalchemy.orm import Session

from src.config import settings
from src.models import User, OAuthAccount, OAuthProvider
from src.services.auth_service import auth_service


# Google OAuth configuration
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# Facebook OAuth configuration
FACEBOOK_AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
FACEBOOK_TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
FACEBOOK_USERINFO_URL = "https://graph.facebook.com/v18.0/me"


class OAuthService:
    """Service for handling OAuth authentication."""
    
    def __init__(self):
        self.google_config = settings.google_oauth_config
        self.facebook_config = settings.facebook_oauth_config
    
    def get_google_auth_url(self, state: str) -> str:
        """Get Google OAuth authorization URL."""
        if not self.google_config:
            raise ValueError("Google OAuth is not configured")
        
        params = {
            "client_id": self.google_config["client_id"],
            "redirect_uri": f"{settings.FRONTEND_URL}/api/auth/callback/google",
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    
    def get_facebook_auth_url(self, state: str) -> str:
        """Get Facebook OAuth authorization URL."""
        if not self.facebook_config:
            raise ValueError("Facebook OAuth is not configured")
        
        params = {
            "client_id": self.facebook_config["client_id"],
            "redirect_uri": f"{settings.FRONTEND_URL}/api/auth/callback/facebook",
            "response_type": "code",
            "scope": "email,public_profile",
            "state": state,
        }
        
        return f"{FACEBOOK_AUTH_URL}?{urlencode(params)}"
    
    async def exchange_google_code(self, code: str) -> Tuple[str, str]:
        """Exchange Google authorization code for access token."""
        if not self.google_config:
            raise ValueError("Google OAuth is not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.google_config["client_id"],
                    "client_secret": self.google_config["client_secret"],
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": f"{settings.FRONTEND_URL}/api/auth/callback/google",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            return data["access_token"], data.get("refresh_token", "")
    
    async def exchange_facebook_code(self, code: str) -> Tuple[str, str]:
        """Exchange Facebook authorization code for access token."""
        if not self.facebook_config:
            raise ValueError("Facebook OAuth is not configured")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                FACEBOOK_TOKEN_URL,
                params={
                    "client_id": self.facebook_config["client_id"],
                    "client_secret": self.facebook_config["client_secret"],
                    "code": code,
                    "redirect_uri": f"{settings.FRONTEND_URL}/api/auth/callback/facebook",
                },
            )
            response.raise_for_status()
            data = response.json()
            
            return data["access_token"], data.get("refresh_token", "")
    
    async def get_google_userinfo(self, access_token: str) -> dict:
        """Get user info from Google."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return response.json()
    
    async def get_facebook_userinfo(self, access_token: str) -> dict:
        """Get user info from Facebook."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                FACEBOOK_USERINFO_URL,
                params={
                    "fields": "id,name,email,picture",
                    "access_token": access_token,
                },
            )
            response.raise_for_status()
            return response.json()
    
    def process_google_user(self, db: Session, userinfo: dict) -> User:
        """Process Google user and create/update in database."""
        email = userinfo.get("email")
        name = userinfo.get("name", "")
        
        if not email:
            raise ValueError("Email not provided by Google")
        
        return self._process_oauth_user(
            db=db,
            provider=OAuthProvider.GOOGLE,
            provider_user_id=userinfo.get("id"),
            email=email,
            full_name=name,
        )
    
    def process_facebook_user(self, db: Session, userinfo: dict) -> User:
        """Process Facebook user and create/update in database."""
        email = userinfo.get("email")
        name = userinfo.get("name", "")
        
        if not email:
            raise ValueError("Email not provided by Facebook")
        
        return self._process_oauth_user(
            db=db,
            provider=OAuthProvider.FACEBOOK,
            provider_user_id=userinfo.get("id"),
            email=email,
            full_name=name,
        )
    
    def _process_oauth_user(
        self,
        db: Session,
        provider: OAuthProvider,
        provider_user_id: str,
        email: str,
        full_name: str,
    ) -> User:
        """Process OAuth user - find existing or create new."""
        # Check if OAuth account exists
        oauth_account = db.query(OAuthAccount).filter(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_user_id == provider_user_id,
        ).first()
        
        if oauth_account:
            user = oauth_account.user
            user.full_name = full_name
            db.commit()
            return user
        
        # Check if user with email already exists
        existing_user = db.query(User).filter(User.email == email).first()
        
        if existing_user:
            oauth_account = OAuthAccount(
                user_id=existing_user.id,
                provider=provider,
                provider_user_id=provider_user_id,
            )
            db.add(oauth_account)
            db.commit()
            return existing_user
        
        # Create new user
        user = User(
            email=email,
            full_name=full_name,
            is_verified=True,
        )
        db.add(user)
        db.flush()
        
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_user_id=provider_user_id,
        )
        db.add(oauth_account)
        db.commit()
        db.refresh(user)
        
        return user


# Create singleton instance
oauth_service = OAuthService()
