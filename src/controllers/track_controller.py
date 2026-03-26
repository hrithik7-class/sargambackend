"""
Track controller — CRUD for user-generated tracks.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.schemas import TrackResponse, TrackListResponse
from src.services.track_service import track_service


class TrackController:
    """Handles track HTTP requests."""

    @staticmethod
    def list_tracks(user, db: Session, skip: int = 0, limit: int = 50) -> TrackListResponse:
        tracks = track_service.list_for_user(db, user.id, skip=skip, limit=limit)
        return TrackListResponse(
            tracks=[TrackResponse.model_validate(t) for t in tracks],
            total=len(tracks),
        )

    @staticmethod
    def get_track(track_id: int, user, db: Session) -> TrackResponse:
        track = track_service.get(db, track_id=track_id, user_id=user.id)
        if not track:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        return TrackResponse.model_validate(track)

    @staticmethod
    def delete_track(track_id: int, user, db: Session):
        deleted = track_service.delete(db, track_id=track_id, user_id=user.id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Track not found",
            )
        return {"message": "Track deleted"}
