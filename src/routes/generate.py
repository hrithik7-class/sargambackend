"""
Generation routes — lyrics, audio synthesis, copyright check.
All routes require a valid Bearer token.
"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy.orm import Session

from src.database import get_db
from src.schemas import (
    LyricsGenerateRequest,
    LyricsGenerateResponse,
    AudioGenerateRequest,
    AudioGenerateResponse,
    CopyrightCheckRequest,
    CopyrightCheckResponse,
)
from src.controllers.generate_controller import GenerateController
from src.controllers.auth_controller import _get_current_user_from_header
from src.limiter import limiter
from src.config import settings

router = APIRouter(prefix="/api/generate", tags=["Generation"])


@router.post("/lyrics", response_model=LyricsGenerateResponse)
@limiter.limit(settings.RATE_LIMIT_GENERATE)
async def generate_lyrics(
    request: Request,
    body: LyricsGenerateRequest,
    _user=Depends(_get_current_user_from_header),
):
    """
    Generate full structured song lyrics from rhyme words or partial lines.
    Synchronous — returns in ~2-4s.
    """
    return await GenerateController.generate_lyrics(body)


@router.post("/audio", response_model=AudioGenerateResponse, status_code=202)
@limiter.limit(settings.RATE_LIMIT_GENERATE)
async def generate_audio(
    request: Request,
    body: AudioGenerateRequest,
    background_tasks: BackgroundTasks,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """
    Start async audio synthesis (MiniMax Music 2.5 via Replicate).
    Returns immediately with track_id; poll GET /api/tracks/{id} for status.
    """
    return await GenerateController.generate_audio(body, user, db, background_tasks)


@router.post("/copyright-check", response_model=CopyrightCheckResponse)
@limiter.limit(settings.RATE_LIMIT_API)
async def copyright_check(
    request: Request,
    body: CopyrightCheckRequest,
    track_id: Optional[int] = Query(default=None, description="Persist result on this track"),
    _user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """
    Check if the provided lyrics are similar to existing copyrighted songs.
    Optionally pass track_id to persist the result on that track record.
    """
    return await GenerateController.check_copyright(body, track_id, db)
