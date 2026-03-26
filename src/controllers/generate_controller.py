"""
Generation controller — orchestrates lyrics, audio, and copyright checks.
"""
from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import TrackStatus
from src.schemas import (
    LyricsGenerateRequest,
    LyricsGenerateResponse,
    AudioGenerateRequest,
    AudioGenerateResponse,
    CopyrightCheckRequest,
    CopyrightCheckResponse,
    CopyrightMatch,
)
from src.services.lyrics_service import lyrics_service
from src.services.music_service import music_service
from src.services.copyright_service import copyright_service
from src.services.track_service import track_service


async def _audio_background_task(
    track_id: int,
    lyrics: str,
    genre: str,
    language: str,
) -> None:
    """
    Background coroutine: generates audio via Replicate and updates track status.
    Creates its own DB session since request session is closed after response.
    """
    db = SessionLocal()
    try:
        track_service.update_status(db, track_id, TrackStatus.GENERATING_AUDIO)

        audio_url = await music_service.generate_audio(
            track_id=track_id,
            lyrics=lyrics,
            genre=genre,
            language=language,
        )

        track_service.update_status(
            db,
            track_id,
            TrackStatus.COMPLETED,
            audio_url=audio_url,
        )
    except Exception as exc:
        track_service.update_status(
            db,
            track_id,
            TrackStatus.FAILED,
            error_message=str(exc),
        )
    finally:
        db.close()


class GenerateController:
    """Handles AI generation HTTP requests."""

    @staticmethod
    async def generate_lyrics(
        request: LyricsGenerateRequest,
    ) -> LyricsGenerateResponse:
        """Generate structured lyrics via Groq."""
        try:
            result = await lyrics_service.generate_lyrics(
                input_prompt=request.input_prompt,
                language=request.language,
                genre=request.genre,
                title=request.title or None,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lyrics generation failed: {exc}",
            )
        return LyricsGenerateResponse(**result)

    @staticmethod
    async def generate_audio(
        request: AudioGenerateRequest,
        user,
        db: Session,
        background_tasks: BackgroundTasks,
    ) -> AudioGenerateResponse:
        """
        Create a Track record and start async audio synthesis.
        Returns immediately with track_id; client polls for status.
        """
        track = track_service.create(
            db=db,
            user_id=user.id,
            title=request.title,
            input_prompt=request.input_prompt or request.lyrics[:200],
            language=request.language,
            genre=request.genre,
            generated_lyrics=request.lyrics,
        )

        background_tasks.add_task(
            _audio_background_task,
            track_id=track.id,
            lyrics=request.lyrics,
            genre=request.genre,
            language=request.language,
        )

        return AudioGenerateResponse(track_id=track.id, status=track.status)

    @staticmethod
    async def check_copyright(
        request: CopyrightCheckRequest,
        track_id: int | None,
        db: Session,
    ) -> CopyrightCheckResponse:
        """Run copyright similarity check and optionally persist the result."""
        try:
            result = await copyright_service.check_copyright(
                lyrics=request.lyrics,
                title=request.title or "",
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Copyright check failed: {exc}",
            )

        # Persist result on the track if track_id provided
        if track_id is not None:
            track_service.update_copyright(
                db,
                track_id=track_id,
                safe=result["safe"],
                score=result["score"],
            )

        return CopyrightCheckResponse(
            safe=result["safe"],
            score=result["score"],
            matches=[CopyrightMatch(**m) for m in result["matches"]],
            note=result.get("note"),
        )
