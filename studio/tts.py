"""Neural Text-to-Speech Engine for PeakCut/Clipper.
Uses edge-tts to generate studio-grade multi-character voiceovers
and extracts millisecond-exact word boundaries for animated subtitles.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import re
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


def _split_into_tts_chunks(text: str, max_chars: int = 320) -> list[str]:
    """Splits long text by sentence boundaries into manageable chunks for robust TTS delivery."""
    raw_sentences = re.split(r'([।!?\.\n]+)', text)
    sentences = []
    curr = ""
    for s in raw_sentences:
        if re.match(r'^[।!?\.\n]+$', s):
            curr += s
            if curr.strip():
                sentences.append(curr.strip())
            curr = ""
        else:
            if curr.strip():
                sentences.append(curr.strip())
            curr = s
    if curr.strip():
        sentences.append(curr.strip())

    chunks = []
    current_chunk = ""
    for s in sentences:
        if not s:
            continue
        if len(current_chunk) + len(s) + 1 <= max_chars:
            current_chunk = f"{current_chunk} {s}".strip() if current_chunk else s
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = s
    if current_chunk:
        chunks.append(current_chunk)
    return chunks if chunks else [text]


MP3_BYTES_PER_SEC = 48000 / 8  # edge-tts sends 24 kHz 48 kbit/s mono MP3


async def _stream_tts_chunk(chunk_text: str, voice_id: str, retries: int = 3, rate: str = "+0%",
                            pitch: str = "+0Hz") -> tuple[bytes, list[dict], float]:
    """Synthesizes a single chunk with automatic retry and word boundary capture."""
    for attempt in range(retries):
        try:
            communicate = edge_tts.Communicate(chunk_text, voice_id, rate=rate, pitch=pitch, boundary="WordBoundary")
            audio_bytes = bytearray()
            words = []
            max_end = 0.0
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_bytes.extend(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    st = chunk["offset"] / 10_000_000.0
                    dur = chunk["duration"] / 10_000_000.0
                    end = st + dur
                    if end > max_end:
                        max_end = end
                    words.append({
                        "w": chunk["text"],
                        "s": round(st, 3),
                        "e": round(end, 3)
                    })
            if audio_bytes:
                # the real length of the audio (it ends in silence after the last word), so the next chunk's
                # words line up with the sound instead of drifting earlier and earlier
                return bytes(audio_bytes), words, max(max_end, len(audio_bytes) / MP3_BYTES_PER_SEC)
        except Exception as e:
            log.warning("TTS chunk attempt %d failed for voice %s: %s", attempt + 1, voice_id, e)
            if attempt < retries - 1:
                await asyncio.sleep(1.0 * (attempt + 1))
    return b"", [], 0.0


async def _stream_tts(text: str, voice_id: str, out_audio: Path, rate: str = "+0%", pitch: str = "+0Hz") -> list[dict]:
    """Robust multi-chunk TTS stream processing with offset-tracked word boundaries."""
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    chunks = _split_into_tts_chunks(text, max_chars=320)
    all_words = []
    current_time_offset = 0.0

    with open(out_audio, "wb") as f_out:
        for chunk in chunks:
            raw_audio, chunk_words, chunk_duration = await _stream_tts_chunk(chunk, voice_id, rate=rate, pitch=pitch)
            if raw_audio:
                f_out.write(raw_audio)
                for w in chunk_words:
                    all_words.append({
                        "w": w["w"],
                        "s": round(w["s"] + current_time_offset, 3),
                        "e": round(w["e"] + current_time_offset, 3)
                    })
                current_time_offset += chunk_duration
            else:
                log.error("Failed to synthesize chunk: %s", chunk[:40])

    return all_words


def synthesize_scene_voice(text: str, voice_id: str, out_audio: Path, rate: str = "+0%", pitch: str = "+0Hz") -> list[dict]:
    """Synchronous wrapper to synthesize speech and extract word boundaries."""
    if not text.strip():
        return []
    try:
        return asyncio.run(_stream_tts(text, voice_id, out_audio, rate=_pct(rate), pitch=_hz(pitch)))
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



# ---------------------------------------------------------------- multi-speaker scenes

def _pct(v) -> str:
    """'-8%', -8, '−8' -> '-8%' (what edge-tts accepts)."""
    try:
        n = int(round(float(str(v).replace("%", "").replace("−", "-").strip() or 0)))
    except ValueError:
        n = 0
    n = max(-50, min(50, n))
    return f"{n:+d}%"


def _hz(v) -> str:
    try:
        n = int(round(float(str(v).lower().replace("hz", "").replace("−", "-").strip() or 0)))
    except ValueError:
        n = 0
    n = max(-40, min(40, n))
    return f"{n:+d}Hz"


def _add(a: str, b: str, unit: str) -> str:
    conv = _pct if unit == "%" else _hz
    return conv(int(conv(a)[:-len(unit)]) + int(conv(b)[:-len(unit)]))


EMOTION_PROSODY = {  # small, believable nudges on top of the voice's own settings
    "whisper": ("-12%", "-4Hz"), "scared": ("+8%", "+6Hz"), "excited": ("+10%", "+5Hz"), "sad": ("-10%", "-3Hz"),
    "angry": ("+6%", "-2Hz"), "calm": ("-6%", "+0Hz"), "happy": ("+5%", "+3Hz"), "mysterious": ("-8%", "-3Hz"),
}


def synthesize_lines(lines: list[dict], out_audio: Path, gap: float = 0.35) -> tuple[list[dict], list[tuple[float, float]]]:
    """Speak a scene line by line, each in its own voice, joined with short natural pauses.

    lines: [{"text", "voice_id", "rate"?, "pitch"?, "emotion"?}]
    Returns (words with times on the joined track, [(start, end) of every line]).
    """
    from studio.concat import NO_WINDOW, _get_duration
    import subprocess
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    parts, words, spans = [], [], []
    t = 0.0
    for i, ln in enumerate(lines):
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        rate, pitch = ln.get("rate", "+0%"), ln.get("pitch", "+0Hz")
        emo = EMOTION_PROSODY.get(str(ln.get("emotion", "")).lower())
        if emo:
            rate, pitch = _add(rate, emo[0], "%"), _add(pitch, emo[1], "Hz")
        part = out_audio.with_name(f"{out_audio.stem}_l{i:02d}.mp3")
        w = synthesize_scene_voice(text, ln.get("voice_id") or "en-US-ChristopherNeural", part, rate=rate, pitch=pitch)
        if not part.is_file() or part.stat().st_size < 500:
            continue
        dur = _get_duration(part) or (max((x["e"] for x in w), default=0.0) + 0.3)
        words += [{"w": x["w"], "s": round(x["s"] + t, 3), "e": round(x["e"] + t, 3)} for x in w]
        spans.append((round(t, 3), round(t + dur, 3)))
        parts.append((part, dur))
        t += dur + gap
    if not parts:
        return [], []
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for p, _ in parts:
        cmd += ["-i", str(p)]
    chain = "".join(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,apad=pad_dur={gap if i < len(parts) - 1 else 0.01}[a{i}];"
                    for i in range(len(parts)))
    chain += "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]"
    cmd += ["-filter_complex", chain, "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "128k", str(out_audio)]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=180)
    if r.returncode != 0:
        log.error("joining scene lines failed: %s", r.stderr[-300:])
        return [], []
    for p, _ in parts:
        p.unlink(missing_ok=True)
    return words, spans


_FEMALE = re.compile(r"\b(woman|women|girl|female|she|her|mother|mom|mum|maa|aunt|queen|princess|lady|sister|"
                     r"grandma|granny|daughter|wife|witch|goddess|actress|hen|cow|mare|didi|ladki|aurat|rani)\b", re.I)
_CHILD = re.compile(r"\b(child|kid|baby|toddler|little|tiny|cub|chick|puppy|kitten|bachcha|chhota|chhotu)\b", re.I)


def guess_gender(*texts: str) -> str:
    t = " ".join(x for x in texts if x)
    return "female" if _FEMALE.search(t) else "male"


def pick_voice(lang: str, hint: str = "", taken: set | None = None) -> str:
    """A voice in the language that suits the character (female/male/child from its description) and is not
    already used by someone else in the cast, so every character sounds different."""
    taken = taken or set()
    voices = list_voices(lang) or list_voices("en")
    want = guess_gender(hint)
    child = bool(_CHILD.search(hint or ""))
    ranked = sorted(voices, key=lambda v: (v["id"] in taken, v["gender"] != want,
                                           child != ("Child" in v["name"] or "Boyish" in v["name"])))
    return ranked[0]["id"] if ranked else default_voice_for_lang(lang)
