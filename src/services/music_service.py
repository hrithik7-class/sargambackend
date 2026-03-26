"""
Music synthesis service — supports Replicate (MiniMax), Fal.ai, and Hugging Face.
- Replicate: Full song with vocals from lyrics (MiniMax Music 2.5).
- Fal / Hugging Face: Instrumental music from text prompt (MusicGen).
"""
import os
import re
from pathlib import Path
from typing import Optional

import httpx

from src.config import settings

# Map internal language codes to natural language style labels
_LANG_STYLE: dict[str, str] = {
    "hindi": "Hindi Bollywood vocals",
    "english": "English vocals",
    "hinglish": "Hinglish Bollywood pop vocals",
    "punjabi": "Punjabi Bhangra vocals",
    "auto": "natural vocals",
}


def _style_prompt_for_instrumental(genre: str, language: str, lyrics: str) -> str:
    """Build a text prompt for MusicGen (instrumental) from genre, language, and lyrics theme."""
    vocal_hint = _LANG_STYLE.get(language.lower(), "melodic")
    # Take first non-tag line from lyrics as theme hint
    theme = ""
    for line in lyrics.strip().split("\n"):
        s = line.strip()
        if s and not re.match(r"^\[.+\]$", s):
            theme = s[:80]
            break
    if theme:
        return f"{genre} song, {vocal_hint} style, inspired by: {theme}, professional studio recording, radio-ready mix, 44.1kHz"
    return f"{genre} song, {vocal_hint} style, professional studio recording, radio-ready mix, 44.1kHz"


def _get_provider() -> str:
    """Return the active music provider based on config and available tokens."""
    preferred = (settings.MUSIC_PROVIDER or "").lower().strip()
    if preferred == "replicate" and settings.REPLICATE_API_TOKEN:
        return "replicate"
    if preferred == "fal" and settings.FAL_KEY:
        return "fal"
    if preferred == "huggingface" and settings.HUGGINGFACE_TOKEN:
        return "huggingface"
    # Fallback: prefer Fal (HF MusicGen was removed from free Inference API)
    if settings.REPLICATE_API_TOKEN:
        return "replicate"
    if settings.FAL_KEY:
        return "fal"
    if settings.HUGGINGFACE_TOKEN:
        return "huggingface"  # May return 410 — use Fal instead
    raise ValueError(
        "No music provider configured. Set one of: REPLICATE_API_TOKEN, FAL_KEY, or HUGGINGFACE_TOKEN. "
        "Replicate: https://replicate.com | Fal: https://fal.ai | HF: https://huggingface.co/settings/tokens"
    )


class MusicService:
    """Generate music via Replicate (vocals+lyrics), Fal.ai, or Hugging Face (instrumental)."""

    async def generate_audio(
        self,
        track_id: int,
        lyrics: str,
        genre: str,
        language: str,
    ) -> str:
        """
        Synthesize a song.

        Replicate: Full song with vocals singing the lyrics.
        Fal / Hugging Face: Instrumental track based on genre and lyrics theme.

        Returns:
            Relative URL path, e.g. "/media/tracks/42.mp3"
        """
        provider = _get_provider()

        if provider == "replicate":
            return await self._generate_replicate(track_id, lyrics, genre, language)
        if provider == "fal":
            return await self._generate_fal(track_id, lyrics, genre, language)
        if provider == "huggingface":
            return await self._generate_huggingface(track_id, lyrics, genre, language)

        raise ValueError(f"Unknown provider: {provider}")

    async def _generate_replicate(
        self, track_id: int, lyrics: str, genre: str, language: str
    ) -> str:
        """Replicate MiniMax Music 2.5 — full song with vocals."""
        if not settings.REPLICATE_API_TOKEN:
            raise ValueError(
                "REPLICATE_API_TOKEN is not set. "
                "Sign up at https://replicate.com (add credits at /account/billing)."
            )
        os.environ["REPLICATE_API_TOKEN"] = settings.REPLICATE_API_TOKEN

        vocal_style = _LANG_STYLE.get(language.lower(), "natural vocals")
        style_prompt = (
            f"{genre} song, {vocal_style}, professional studio recording, "
            "radio-ready mix, high-quality mastering, 44.1kHz"
        )

        import replicate

        output = await replicate.async_run(
            "minimax/music-2.5",
            input={
                "lyrics": lyrics.strip(),
                "prompt": style_prompt,
                "audio_format": "mp3",
                "sample_rate": 44100,
                "bitrate": 128000,
            },
        )

        if output is None:
            raise RuntimeError("Replicate returned no audio output")

        return await self._save_audio_from_output(track_id, output)

    async def _generate_fal(
        self, track_id: int, lyrics: str, genre: str, language: str
    ) -> str:
        """Fal.ai MusicGen — instrumental from text prompt. Free credits for new users."""
        if not settings.FAL_KEY:
            raise ValueError(
                "FAL_KEY is not set. Sign up at https://fal.ai for free credits."
            )

        prompt = _style_prompt_for_instrumental(genre, language, lyrics)

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://queue.fal.run/fal-ai/musicgen",
                headers={
                    "Authorization": f"Key {settings.FAL_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "prompt": prompt,
                    "duration": 30,
                    "model": "facebook/musicgen-stereo-medium",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        audio_url = data.get("audio_url") or data.get("audio", {})
        if isinstance(audio_url, dict):
            audio_url = audio_url.get("url")
        if not audio_url:
            raise RuntimeError("Fal.ai returned no audio URL")

        return await self._download_and_save(track_id, audio_url)

    async def _generate_huggingface(
        self, track_id: int, lyrics: str, genre: str, language: str
    ) -> str:
        """Hugging Face Inference API MusicGen — instrumental. Note: HF removed many models from free tier (410)."""
        if not settings.HUGGINGFACE_TOKEN:
            raise ValueError(
                "HUGGINGFACE_TOKEN is not set. Get one at https://huggingface.co/settings/tokens. "
                "Note: Hugging Face removed MusicGen from free Inference API. Use FAL_KEY instead (free credits at fal.ai)."
            )

        prompt = _style_prompt_for_instrumental(genre, language, lyrics)

        # Try musicgen-small (lighter model, may still be available)
        models_to_try = [
            "facebook/musicgen-small",
            "facebook/musicgen-stereo-small",
        ]

        async with httpx.AsyncClient(timeout=120.0) as client:
            last_error = None
            for model_id in models_to_try:
                resp = await client.post(
                    f"https://api-inference.huggingface.co/models/{model_id}",
                    headers={
                        "Authorization": f"Bearer {settings.HUGGINGFACE_TOKEN}",
                        "Content-Type": "application/json",
                    },
                    json={"inputs": prompt},
                )
                if resp.status_code == 200 and len(resp.content) > 100:
                    media_dir = Path(settings.MEDIA_DIR)
                    media_dir.mkdir(parents=True, exist_ok=True)
                    file_path = media_dir / f"{track_id}.mp3"
                    file_path.write_bytes(resp.content)
                    return f"/media/tracks/{track_id}.mp3"
                if resp.status_code == 503:
                    raise RuntimeError(
                        "Hugging Face model is loading. Wait a minute and try again."
                    )
                if resp.status_code == 410:
                    last_error = f"Model {model_id} has been removed from free Inference API (410 Gone)."
                    continue
                resp.raise_for_status()

        raise RuntimeError(
            f"Hugging Face MusicGen is no longer available on the free Inference API. "
            "Use FAL_KEY instead: sign up at https://fal.ai for free credits, add FAL_KEY to .env, and set MUSIC_PROVIDER=fal"
        )

    async def _save_audio_from_output(self, track_id: int, output) -> str:
        """Save Replicate output (FileOutput or URL) to local file."""
        media_dir = Path(settings.MEDIA_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)
        file_path = media_dir / f"{track_id}.mp3"

        if hasattr(output, "read"):
            data = output.read()
            file_path.write_bytes(data)
        else:
            return await self._download_and_save(track_id, str(output))
        return f"/media/tracks/{track_id}.mp3"

    async def _download_and_save(self, track_id: int, url: str) -> str:
        """Download audio from URL and save to media dir."""
        media_dir = Path(settings.MEDIA_DIR)
        media_dir.mkdir(parents=True, exist_ok=True)
        file_path = media_dir / f"{track_id}.mp3"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            file_path.write_bytes(response.content)

        return f"/media/tracks/{track_id}.mp3"


music_service = MusicService()
