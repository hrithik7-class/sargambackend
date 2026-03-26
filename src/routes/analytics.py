"""
Analytics routes — aggregated stats for the authenticated user's tracks.
"""
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func

from src.database import get_db
from src.models import Track, TrackStatus
from src.controllers.auth_controller import _get_current_user_from_header
from src.limiter import limiter
from src.config import settings
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


class GenreCount(BaseModel):
    genre: str
    count: int


class LanguageCount(BaseModel):
    language: str
    count: int


class DayCount(BaseModel):
    date: str  # ISO date string YYYY-MM-DD
    count: int


class AnalyticsResponse(BaseModel):
    total: int
    completed: int
    in_progress: int
    failed: int
    copyright_safe_count: int
    copyright_unsafe_count: int
    avg_copyright_score: Optional[float]
    by_genre: List[GenreCount]
    by_language: List[LanguageCount]
    by_day: List[DayCount]


@router.get("", response_model=AnalyticsResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def get_analytics(
    request: Request,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Return aggregated analytics for the authenticated user's tracks."""
    tracks = db.query(Track).filter(Track.user_id == user.id).all()

    total = len(tracks)
    completed = sum(1 for t in tracks if t.status == TrackStatus.COMPLETED)
    in_progress = sum(
        1 for t in tracks
        if t.status in (TrackStatus.PENDING, TrackStatus.GENERATING_AUDIO)
    )
    failed = sum(1 for t in tracks if t.status == TrackStatus.FAILED)
    copyright_safe_count = sum(1 for t in tracks if t.copyright_safe is True)
    copyright_unsafe_count = sum(1 for t in tracks if t.copyright_safe is False)

    scores = [t.copyright_score for t in tracks if t.copyright_score is not None]
    avg_copyright_score = round(sum(scores) / len(scores), 1) if scores else None

    # By genre
    genre_map: dict[str, int] = defaultdict(int)
    for t in tracks:
        genre_map[t.genre] += 1
    by_genre = [
        GenreCount(genre=g, count=c)
        for g, c in sorted(genre_map.items(), key=lambda x: -x[1])
    ]

    # By language
    lang_map: dict[str, int] = defaultdict(int)
    for t in tracks:
        lang_map[t.language] += 1
    by_language = [
        LanguageCount(language=l, count=c)
        for l, c in sorted(lang_map.items(), key=lambda x: -x[1])
    ]

    # By day — last 30 days
    today = datetime.utcnow().date()
    day_map: dict[str, int] = defaultdict(int)
    for t in tracks:
        d = t.created_at.date()
        if d >= today - timedelta(days=29):
            day_map[d.isoformat()] += 1

    by_day = [
        DayCount(date=(today - timedelta(days=i)).isoformat(), count=day_map.get((today - timedelta(days=i)).isoformat(), 0))
        for i in range(29, -1, -1)
    ]

    return AnalyticsResponse(
        total=total,
        completed=completed,
        in_progress=in_progress,
        failed=failed,
        copyright_safe_count=copyright_safe_count,
        copyright_unsafe_count=copyright_unsafe_count,
        avg_copyright_score=avg_copyright_score,
        by_genre=by_genre,
        by_language=by_language,
        by_day=by_day,
    )
