"""
Track CRUD service — database operations for generated tracks.
"""
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from src.models import Track, TrackStatus
from src.config import settings


class TrackService:
    """Database operations for Track records."""

    @staticmethod
    def create(
        db: Session,
        user_id: int,
        title: str,
        input_prompt: str,
        language: str,
        genre: str,
        generated_lyrics: Optional[str] = None,
    ) -> Track:
        track = Track(
            user_id=user_id,
            title=title,
            input_prompt=input_prompt,
            language=language,
            genre=genre,
            generated_lyrics=generated_lyrics,
            status=TrackStatus.PENDING,
        )
        db.add(track)
        db.commit()
        db.refresh(track)
        return track

    @staticmethod
    def get(db: Session, track_id: int, user_id: Optional[int] = None) -> Optional[Track]:
        q = db.query(Track).filter(Track.id == track_id)
        if user_id is not None:
            q = q.filter(Track.user_id == user_id)
        return q.first()

    @staticmethod
    def list_for_user(
        db: Session, user_id: int, skip: int = 0, limit: int = 50
    ) -> list[Track]:
        return (
            db.query(Track)
            .filter(Track.user_id == user_id)
            .order_by(Track.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    @staticmethod
    def update_status(
        db: Session,
        track_id: int,
        status: TrackStatus,
        **fields,
    ) -> Optional[Track]:
        track = db.query(Track).filter(Track.id == track_id).first()
        if not track:
            return None
        track.status = status
        for key, value in fields.items():
            setattr(track, key, value)
        db.commit()
        db.refresh(track)
        return track

    @staticmethod
    def update_copyright(
        db: Session,
        track_id: int,
        safe: bool,
        score: float,
    ) -> Optional[Track]:
        track = db.query(Track).filter(Track.id == track_id).first()
        if not track:
            return None
        track.copyright_safe = safe
        track.copyright_score = score
        db.commit()
        db.refresh(track)
        return track

    @staticmethod
    def delete(db: Session, track_id: int, user_id: int) -> bool:
        track = db.query(Track).filter(
            Track.id == track_id, Track.user_id == user_id
        ).first()
        if not track:
            return False
        # Remove local audio file
        if track.audio_url:
            file_path = Path(settings.MEDIA_DIR) / f"{track_id}.mp3"
            if file_path.exists():
                file_path.unlink(missing_ok=True)
        db.delete(track)
        db.commit()
        return True


track_service = TrackService()
