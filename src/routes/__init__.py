"""
Routes for the application.
"""
from src.routes.auth import router as auth_router
from src.routes.users import router as users_router
from src.routes.generate import router as generate_router
from src.routes.tracks import router as tracks_router
from src.routes.analytics import router as analytics_router
from src.routes.payments import router as payments_router

__all__ = [
    "auth_router",
    "users_router",
    "generate_router",
    "tracks_router",
    "analytics_router",
    "payments_router",
]
