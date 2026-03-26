"""
Services for the application.
"""
from src.services.auth_service import auth_service, AuthService
from src.services.oauth_service import oauth_service, OAuthService
from src.services.lyrics_service import lyrics_service, LyricsService
from src.services.music_service import music_service, MusicService
from src.services.copyright_service import copyright_service, CopyrightService
from src.services.track_service import track_service, TrackService

__all__ = [
    "auth_service",
    "AuthService",
    "oauth_service",
    "OAuthService",
    "lyrics_service",
    "LyricsService",
    "music_service",
    "MusicService",
    "copyright_service",
    "CopyrightService",
    "track_service",
    "TrackService",
]
