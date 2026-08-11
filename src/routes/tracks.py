"""
Tracks routes — list, get, delete, publish user-generated tracks.
All routes require a valid Bearer token.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException, Request
import httpx
from sqlalchemy.orm import Session

from src.database import get_db
from src.models import Track
from src.schemas import TrackResponse, TrackListResponse, MessageResponse
from src.controllers.track_controller import TrackController
from src.controllers.auth_controller import _get_current_user_from_header
from src.limiter import limiter
from src.config import settings

router = APIRouter(prefix="/api/tracks", tags=["Tracks"])


@router.get("", response_model=TrackListResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def list_tracks(
    request: Request,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Return all tracks for the authenticated user, newest first."""
    return TrackController.list_tracks(user, db, skip=skip, limit=limit)


@router.get("/{track_id}", response_model=TrackResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def get_track(
    request: Request,
    track_id: int,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Get a single track by ID (must belong to the authenticated user)."""
    return TrackController.get_track(track_id, user, db)


@router.delete("/{track_id}", response_model=MessageResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def delete_track(
    request: Request,
    track_id: int,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Delete a track and its associated audio file."""
    return TrackController.delete_track(track_id, user, db)


@router.post("/{track_id}/publish", response_model=TrackResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def publish_track(
    request: Request,
    track_id: int,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Publish a track — sets published_at to the current UTC time."""
    track = db.query(Track).filter(Track.id == track_id, Track.user_id == user.id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    track.published_at = datetime.utcnow()
    db.commit()
    db.refresh(track)
    return track


@router.post("/{track_id}/unpublish", response_model=TrackResponse)
@limiter.limit(settings.RATE_LIMIT_API)
def unpublish_track(
    request: Request,
    track_id: int,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Unpublish a track — clears published_at."""
    track = db.query(Track).filter(Track.id == track_id, Track.user_id == user.id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    track.published_at = None
    db.commit()
    db.refresh(track)
    return track


@router.post("/{track_id}/generate-cover", response_model=TrackResponse)
@limiter.limit("5/minute")
async def generate_cover(
    request: Request,
    track_id: int,
    user=Depends(_get_current_user_from_header),
    db: Session = Depends(get_db),
):
    """Generate AI cover art for a track using Replicate flux-schnell."""
    track = db.query(Track).filter(Track.id == track_id, Track.user_id == user.id).first()
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    if not settings.REPLICATE_API_TOKEN:
        raise HTTPException(status_code=503, detail="Image generation not configured")

    prompt = (
        f"Album cover art for a {track.genre} song titled '{track.title}'. "
        f"Cinematic, professional music album artwork, no text, no words, "
        f"vivid colors, artistic, high quality digital art."
    )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.replicate.com/v1/models/black-forest-labs/flux-schnell/predictions",
            headers={
                "Authorization": f"Bearer {settings.REPLICATE_API_TOKEN}",
                "Content-Type": "application/json",
                "Prefer": "wait",
            },
            json={"input": {"prompt": prompt, "num_outputs": 1, "aspect_ratio": "1:1", "output_format": "webp"}},
        )
        if resp.status_code not in (200, 201):
            raise HTTPException(status_code=502, detail="Image generation failed")

        data = resp.json()
        if data.get("status") not in ("succeeded",):
            poll_url = data.get("urls", {}).get("get")
            for _ in range(30):
                import asyncio
                await asyncio.sleep(2)
                poll = await client.get(
                    poll_url,
                    headers={"Authorization": f"Bearer {settings.REPLICATE_API_TOKEN}"},
                )
                data = poll.json()
                if data.get("status") == "succeeded":
                    break
                if data.get("status") == "failed":
                    raise HTTPException(status_code=502, detail="Image generation failed")

        output = data.get("output")
        image_url = output[0] if isinstance(output, list) and output else None
        if not image_url:
            raise HTTPException(status_code=502, detail="No image returned")

    track.cover_image_url = image_url
    db.commit()
    db.refresh(track)
    return track
