"""
User routes - HTTP endpoints for user management.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas import UserResponse
from src.controllers import UserController
from src.controllers.user_controller import UserResponseWithProviders

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me/full", response_model=UserResponseWithProviders)
def get_current_user_full(
    authorization: str = None,
    db: Session = Depends(get_db)
):
    """Get current user's full profile including OAuth providers."""
    return UserController.get_current_user(authorization, db)


@router.get("/profile/{user_id}", response_model=UserResponse)
def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    """Get a user's public profile by ID."""
    return UserController.get_user_profile(user_id, db)
