"""Neural Text-to-Speech Engine for PeakCut/Clipper.
Uses edge-tts to generate studio-grade multi-character voiceovers
and extracts millisecond-exact word boundaries for animated subtitles.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import edge_tts

log = logging.getLogger("peakcut.tts")

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi (हिंदी)",
    "es": "Spanish (Español)",
    "fr": "French (Français)",
    "de": "German (Deutsch)",
    "ja": "Japanese (日本語)"
}

VOICE_CATALOG = [
    # English (US, GB, IN)
    {"id": "en-US-ChristopherNeural", "name": "Christopher (Friendly Narrator)", "lang": "en", "gender": "male"},
    {"id": "en-US-JennyNeural", "name": "Jenny (Warm Female / Motherly)", "lang": "en", "gender": "female"},
    {"id": "en-US-AnaNeural", "name": "Ana (Cute Child / Toddler)", "lang": "en", "gender": "female"},
    {"id": "en-US-EricNeural", "name": "Eric (Playful / Boyish)", "lang": "en", "gender": "male"},
    {"id": "en-US-GuyNeural", "name": "Guy (Casual / Dynamic)", "lang": "en", "gender": "male"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia (British Storybook)", "lang": "en", "gender": "female"},
    {"id": "en-IN-NeerjaNeural", "name": "Neerja (Indian English Female)", "lang": "en", "gender": "female"},
    {"id": "en-IN-PrabhatNeural", "name": "Prabhat (Indian English Male)", "lang": "en", "gender": "male"},
    # Hindi (हिंदी)
    {"id": "hi-IN-MadhurNeural", "name": "Madhur (मधुर - Warm Hindi Narrator)", "lang": "hi", "gender": "male"},
    {"id": "hi-IN-SwaraNeural", "name": "Swara (स्वरा - Expressive Hindi Female)", "lang": "hi", "gender": "female"},
    # Spanish
    {"id": "es-ES-AlvaroNeural", "name": "Alvaro (Spanish Male)", "lang": "es", "gender": "male"},
    {"id": "es-ES-ElviraNeural", "name": "Elvira (Spanish Female)", "lang": "es", "gender": "female"},
    {"id": "es-MX-DaliaNeural", "name": "Dalia (Mexican Spanish Female)", "lang": "es", "gender": "female"},
    # French
    {"id": "fr-FR-HenriNeural", "name": "Henri (French Male)", "lang": "fr", "gender": "male"},
    {"id": "fr-FR-DeniseNeural", "name": "Denise (French Female)", "lang": "fr", "gender": "female"},
    # German
    {"id": "de-DE-ConradNeural", "name": "Conrad (German Male)", "lang": "de", "gender": "male"},
    {"id": "de-DE-KatjaNeural", "name": "Katja (German Female)", "lang": "de", "gender": "female"},
    # Japanese
    {"id": "ja-JP-KeitaNeural", "name": "Keita (Japanese Male)", "lang": "ja", "gender": "male"},
    {"id": "ja-JP-NanamiNeural", "name": "Nanami (Japanese Female)", "lang": "ja", "gender": "female"},
]


def list_voices(lang: str | None = None) -> list[dict]:
    """Returns curated voices for character dialogues and narration."""
    if not lang or lang.lower() == "all":
        return VOICE_CATALOG
    tgt = lang.lower()
    return [v for v in VOICE_CATALOG if v["lang"].lower() == tgt or tgt in v["id"].lower()]


def default_voice_for_lang(lang: str = "en") -> str:
    """Returns the primary recommended narrator voice for a given language."""
    voices = list_voices(lang)
    if voices:
        return voices[0]["id"]
    return "en-US-ChristopherNeural"


async def _stream_tts(text: str, voice_id: str, out_audio: Path) -> list[dict]:
    """Internal coroutine for Edge-TTS stream processing with word boundary capture."""
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    communicate = edge_tts.Communicate(text, voice_id, boundary="WordBoundary")
    words = []
    
    with open(out_audio, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset and duration are in 100ns units -> divide by 10,000,000 for seconds
                st = chunk["offset"] / 10_000_000.0
                dur = chunk["duration"] / 10_000_000.0
                words.append({
                    "w": chunk["text"],
                    "s": round(st, 3),
                    "e": round(st + dur, 3)
                })
    return words


def synthesize_scene_voice(text: str, voice_id: str, out_audio: Path) -> list[dict]:
    """Synchronous wrapper to synthesize speech and extract word boundaries."""
    if not text.strip():
        return []
    try:
        return asyncio.run(_stream_tts(text, voice_id, out_audio))
    except Exception as e:
        log.error("TTS synthesis error with voice %s: %s", voice_id, e)
        # Try fallback voice if specified voice fails
        if voice_id != "en-US-ChristopherNeural":
            try:
                return asyncio.run(_stream_tts(text, "en-US-ChristopherNeural", out_audio))
            except Exception:
                pass
        return []


def synthesize_narrative_audio(text: str, voice_id: str, out_audio: Path) -> Path | None:
    """Synthesizes a director / showrunner context walkthrough into an MP3 audio file."""
    if not text or not text.strip():
        return None
    try:
        out_audio.parent.mkdir(parents=True, exist_ok=True)
        synthesize_scene_voice(text, voice_id, out_audio)
        if out_audio.is_file() and out_audio.stat().st_size > 1000:
            return out_audio
    except Exception as e:
        log.error("Failed to synthesize narrative audio: %s", e)
    return None

