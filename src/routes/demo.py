"""
Public demo route — lets an anonymous visitor generate ONE real song (lyrics + AI
vocals) without an account, to showcase the product on the marketing site.

No DB record is created (no user to attach it to); the audio file is written
directly to the public media dir under a random id. Rate-limited hard per IP
to control cost/abuse of the underlying paid music-generation API.
"""
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status

from src.schemas import LyricsGenerateRequest
from src.services.lyrics_service import lyrics_service
from src.services.music_service import music_service
from src.limiter import limiter
from src.config import settings

router = APIRouter(prefix="/api/demo", tags=["Demo"])

# Anonymous demo generation is expensive (real Replicate call) and unauthenticated,
# so it gets its own tight, dedicated limit rather than RATE_LIMIT_GENERATE.
DEMO_RATE_LIMIT = "1/day"


@router.post("/generate", status_code=status.HTTP_200_OK)
@limiter.limit(DEMO_RATE_LIMIT)
async def generate_demo(request: Request, body: LyricsGenerateRequest):
    """
    One-shot, unauthenticated: generate lyrics then synthesize a full song with
    vocals. Returns once the audio is ready (synchronous — no polling needed for
    a single demo track). Limited to one call per IP per day.
    """
    try:
        lyrics_result = await lyrics_service.generate_lyrics(
            input_prompt=body.input_prompt,
            language=body.language,
            genre=body.genre,
            title=body.title or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lyrics generation failed: {exc}")

    demo_id = f"demo-{uuid4().hex}"
    try:
        audio_url = await music_service.generate_audio(
            track_id=demo_id,
            lyrics=lyrics_result["lyrics"],
            genre=body.genre,
            language=body.language,
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Audio generation failed: {exc}")

    return {
        "title": lyrics_result["title"],
        "lyrics": lyrics_result["lyrics"],
        "language": lyrics_result["language"],
        "genre": lyrics_result["genre"],
        "audio_url": audio_url,
    }
