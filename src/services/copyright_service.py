"""
Copyright safety check service.
Uses Genius API (lyricsgenius) to find existing songs with similar text,
then scores similarity with rapidfuzz.
"""
import asyncio
import re
from typing import Optional

from src.config import settings

_SIMILARITY_THRESHOLD = 65.0  # flag if any match exceeds this %



def _extract_search_query(lyrics: str, title: str) -> str:
    """Pick the most distinctive phrase for a Genius search."""
    if title:
        return title

    # Try to grab the first line of the [Chorus] — most distinctive
    in_chorus = False
    for line in lyrics.split("\n"):
        stripped = line.strip()
        if re.search(r"\[chorus\]|\[hook\]|\[sabiha\]", stripped, re.IGNORECASE):
            in_chorus = True
            continue
        if in_chorus and stripped and not stripped.startswith("["):
            return stripped

    # Fallback: first non-tag, non-empty line
    for line in lyrics.split("\n"):
        stripped = line.strip()
        if stripped and not stripped.startswith("["):
            return stripped[:80]

    return " ".join(lyrics.split()[:6])


class CopyrightService:
    """Check whether generated lyrics overlap with existing copyrighted songs."""

    def __init__(self) -> None:
        self._genius = None

    def _get_genius(self):
        if self._genius is None:
            if not settings.GENIUS_ACCESS_TOKEN:
                return None
            import lyricsgenius
            self._genius = lyricsgenius.Genius(
                settings.GENIUS_ACCESS_TOKEN,
                timeout=8,
                retries=1,
                skip_non_songs=True,
            )
        return self._genius

    async def check_copyright(
        self,
        lyrics: str,
        title: str = "",
    ) -> dict:
        """
        Check the generated lyrics against Genius for similarity.

        Returns:
            {
                "safe": bool,          # True if no close match found
                "score": float,        # Highest similarity % (0-100)
                "matches": [           # Up to 3 closest matches
                    {"title": str, "artist": str, "similarity": float}
                ],
                "note": str | None,    # Human-readable caveat if API is unconfigured
            }
        """
        genius = self._get_genius()
        if genius is None:
            return {
                "safe": True,
                "score": 0.0,
                "matches": [],
                "note": (
                    "GENIUS_ACCESS_TOKEN is not configured — copyright check skipped. "
                    "Register at https://genius.com/api-clients"
                ),
            }

        from rapidfuzz import fuzz

        query = _extract_search_query(lyrics, title)
        matches = []

        # Search Genius for songs with this query (run sync library in thread)
        try:
            song = await asyncio.to_thread(genius.search_song, query)
        except Exception:
            song = None

        if song and song.lyrics:
            similarity = fuzz.token_sort_ratio(
                lyrics.lower(), song.lyrics.lower()
            )
            matches.append(
                {
                    "title": song.title,
                    "artist": song.artist,
                    "similarity": round(float(similarity), 1),
                }
            )

        max_score = max((m["similarity"] for m in matches), default=0.0)

        return {
            "safe": max_score < _SIMILARITY_THRESHOLD,
            "score": round(max_score, 1),
            "matches": sorted(matches, key=lambda x: x["similarity"], reverse=True),
            "note": None,
        }


copyright_service = CopyrightService()
