"""
User controller - handles HTTP requests for user management.
"""
from typing import List

from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import User, OAuthAccount
from src.schemas import UserResponse
from src.services import auth_service
from src.utils.token import verify_token


class UserResponseWithProviders(UserResponse):
    """User response that includes OAuth providers."""
    oauth_providers: List[str] = []


class UserController:
    """Controller for handling user HTTP requests."""
    
    @staticmethod
    def get_current_user(
        authorization: str = None,
        db: Session = Depends(get_db)
    ) -> UserResponseWithProviders:
        """Get current user's full profile including OAuth providers."""
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        
        token = authorization.replace("Bearer ", "")
        token_data = verify_token(token)
        
        if not token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        
        user = auth_service.get_user_by_id(db, token_data.user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has been deactivated",
            )
        
        # Get OAuth providers
        oauth_accounts = db.query(OAuthAccount).filter(
            OAuthAccount.user_id == user.id
        ).all()
        
        oauth_providers = [account.provider.value for account in oauth_accounts]
        
        response = UserResponseWithProviders.model_validate(user)
        response.oauth_providers = oauth_providers
        
        return response
    
    @staticmethod
    def get_user_profile(user_id: int, db: Session = Depends(get_db)) -> UserResponse:
        """Get a user's public profile by ID."""
        user = db.query(User).filter(User.id == user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        return UserResponse.model_validate(user)
