"""
Lyrics generation service using Groq API (Llama 3.3-70B).
Produces MiniMax Music 2.5 compatible structured lyrics.
"""
import asyncio
from typing import Optional

from src.config import settings

LYRICS_SYSTEM_PROMPT = """You are a professional lyricist and Grammy-winning songwriter.
Your task: write complete, original, singable song lyrics based on the user's input (rhyme words, themes, or partial lines).

STRICT OUTPUT FORMAT — use EXACTLY these section tags (required for music synthesis):

[Intro]
<2-4 lines>

[Verse 1]
<4-8 lines>

[Chorus]
<4-6 lines — the catchy, repeatable hook>

[Verse 2]
<4-8 lines — different from Verse 1, same rhyme scheme>

[Chorus]
<same chorus as above>

[Bridge]
<4-6 lines — emotional shift, contrast>

[Outro]
<2-4 lines>

RULES:
- Output ONLY the lyrics with the section tags above. No explanations, no extra text.
- Lines must rhyme naturally and flow musically when sung.
- Write ONLY in the requested language.
- Make the lyrics 100% original — do not copy or closely paraphrase existing songs.
- Each line should be 5-12 syllables for natural singing.
- The chorus must be simple, memorable, and emotionally resonant."""

TITLE_SYSTEM_PROMPT = "You are a music A&R executive. Suggest one short, catchy song title (3-5 words). Reply with ONLY the title, no quotes, no punctuation at the end."

LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "hindi": (
        "Write EXCLUSIVELY in Hindi using Devanagari script. "
        "The style should feel authentic Bollywood/Desi — emotional, poetic, and rhythmic. "
        "Use natural colloquial Hindi, not formal textbook Hindi."
    ),
    "english": "Write EXCLUSIVELY in English.",
    "hinglish": (
        "Write in Hinglish — a natural mix of Hindi and English as spoken in modern Bollywood pop. "
        "Hindi phrases in Devanagari, English phrases in Latin script. "
        "Example: 'Dil mera beats for you, baby, har raat yaad aati hai.'"
    ),
    "punjabi": (
        "Write EXCLUSIVELY in Punjabi (Gurmukhi script). "
        "Feel should be energetic Bhangra/Pop fusion."
    ),
    "auto": "Detect the language from the user's input and write entirely in that language.",
}


class LyricsService:
    """Generate structured song lyrics via Groq API."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        if self._client is None:
            if not settings.GROQ_API_KEY:
                raise ValueError(
                    "GROQ_API_KEY is not set. Sign up free at https://console.groq.com/"
                )
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        return self._client

    async def generate_lyrics(
        self,
        input_prompt: str,
        language: str = "english",
        genre: str = "Pop",
        title: Optional[str] = None,
    ) -> dict:
        """
        Generate full structured song lyrics.

        Args:
            input_prompt: User's rhyme words, themes, or partial lines.
            language: "english" | "hindi" | "hinglish" | "punjabi" | "auto"
            genre: Music genre, e.g. "Pop", "Rock", "Bollywood"
            title: Optional suggested title; if None, one is auto-generated.

        Returns:
            dict with keys: lyrics, title, language, genre
        """
        client = self._get_client()
        lang_key = language.lower().strip()
        lang_instruction = LANGUAGE_INSTRUCTIONS.get(lang_key, f"Write exclusively in {language}.")

        user_message = (
            f"Write a complete {genre} song.\n\n"
            f"Language: {lang_instruction}\n\n"
            f"User input (rhyme words / partial lyrics / theme):\n{input_prompt}\n\n"
            + (f"Suggested title: {title}\n\n" if title else "")
            + "Generate the full structured lyrics now:"
        )

        response = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": LYRICS_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.88,
            max_tokens=1600,
        )

        lyrics = response.choices[0].message.content.strip()

        # Auto-generate a title if the user didn't supply one
        if not title:
            title = await self._suggest_title(client, lyrics, genre)

        return {
            "lyrics": lyrics,
            "title": title,
            "language": language,
            "genre": genre,
        }

    async def _suggest_title(self, client, lyrics: str, genre: str) -> str:
        """Use a fast small model to suggest a song title from the first few lines."""
        preview = "\n".join(lyrics.split("\n")[:8])
        try:
            resp = await client.chat.completions.create(
                model="llama-3.1-8b-instant",  # fast, cheap, free on Groq
                messages=[
                    {"role": "system", "content": TITLE_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": (
                            f"Genre: {genre}\n\nLyrics excerpt:\n{preview}\n\nSuggest a title:"
                        ),
                    },
                ],
                temperature=0.7,
                max_tokens=20,
            )
            return resp.choices[0].message.content.strip().strip('"').strip("'")
        except Exception:
            # Fallback: extract first non-tag, non-empty line
            for line in lyrics.split("\n"):
                line = line.strip()
                if line and not line.startswith("["):
                    return line[:50]
            return "My Song"


lyrics_service = LyricsService()
