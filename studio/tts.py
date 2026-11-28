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


class VoiceServiceError(RuntimeError):
    """Microsoft's voice service could not be reached (usually the internet): the scene would be silent."""


class UnknownVoice(RuntimeError):
    """The voice service answered but made no sound: the voice does not exist (or cannot say this text)."""


_FEMALE_VOICE_NAMES = {"neerja", "swara", "jenny", "aria", "ana", "sonia", "elvira", "dalia", "denise", "katja",
                       "nanami", "ananya", "aarti", "kavya", "pallavi", "shruti", "michelle", "libby", "natasha",
                       "clara", "emma", "ava", "sara", "jane", "nancy", "aashi", "aditi", "kajal", "isha"}


def usable_voice(voice_id: str) -> str:
    """A voice that exists: this one when it is in the catalogue, else one of the same language and the same
    gender (e.g. the made-up 'hi-IN-NeerjaNeural' → 'hi-IN-SwaraNeural')."""
    if any(v["id"] == voice_id for v in VOICE_CATALOG):
        return voice_id
    vid = str(voice_id or "")
    name = vid.split("-")[-1].replace("Neural", "").lower()
    gender = "female" if name in _FEMALE_VOICE_NAMES else "male"
    cands = [v for v in VOICE_CATALOG if v["id"].startswith(vid[:5])] or list_voices(vid[:2]) or list_voices("en")
    same = [v for v in cands if v["gender"] == gender] or cands
    return same[0]["id"]


async def _stream_tts_chunk(chunk_text: str, voice_id: str, retries: int = 5, rate: str = "+0%",
                            pitch: str = "+0Hz") -> tuple[bytes, list[dict], float]:
    """Synthesizes a single chunk with automatic retry and word boundary capture.
    Raises UnknownVoice when the service makes no sound for this voice, VoiceServiceError when it cannot be
    reached after waiting about half a minute (2, 4, 8, 16 s between tries)."""
    last = None
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
            last = UnknownVoice("no audio")
        except Exception as e:
            log.warning("TTS chunk attempt %d failed for voice %s: %s", attempt + 1, voice_id, e)
            last = UnknownVoice(str(e)) if "No audio was received" in str(e) else e
        if isinstance(last, UnknownVoice) and attempt >= 1:   # asked twice, no sound: not the internet
            raise last
        if attempt < retries - 1:
            await asyncio.sleep(2.0 * 2 ** attempt if not isinstance(last, UnknownVoice) else 1.0)
    if isinstance(last, UnknownVoice):
        raise last
    raise VoiceServiceError(f"Could not reach the voice service: {last}")


async def _stream_tts(text: str, voice_id: str, out_audio: Path, rate: str = "+0%", pitch: str = "+0Hz") -> list[dict]:
    """Robust multi-chunk TTS stream processing with offset-tracked word boundaries."""
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    chunks = _split_into_tts_chunks(text, max_chars=320)
    all_words = []
    current_time_offset = 0.0

    with open(out_audio, "wb") as f_out:
        for chunk in chunks:
            raw_audio, chunk_words, chunk_duration = await _stream_tts_chunk(chunk, voice_id, rate=rate, pitch=pitch)
            if raw_audio:   # (a chunk that fails raises: a line is never left half-said)
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
    except UnknownVoice:
        # a voice that does not exist (an AI may invent one): a real voice of the same language and gender
        alt = usable_voice(voice_id)
        if alt != voice_id:
            log.warning("voice %s does not exist; using %s", voice_id, alt)
            try:
                return asyncio.run(_stream_tts(text, alt, out_audio, rate=_pct(rate), pitch=_hz(pitch)))
            except UnknownVoice:
                pass
        log.error("no sound for this line with voice %s: %.40s", voice_id, text)
        return []
    except VoiceServiceError:
        raise   # no internet: the caller stops instead of making silent scenes
    except Exception as e:  # noqa: BLE001
        log.error("TTS synthesis error with voice %s: %s", voice_id, e)
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
    from studio import animals
    out_audio.parent.mkdir(parents=True, exist_ok=True)
    parts, words, spans = [], [], []      # parts: (file, length, pause after it)
    t = 0.0
    for i, ln in enumerate(lines):
        text = animals.stage_free(ln.get("text") or "")     # "(धीरे से)" and "[laughs]" are directions, not words
        if not text:
            continue
        start = t
        said = text
        # an animal's noises ("भौं-भौं!", "म्याऊँ") are its real sound, then whatever it says in words
        if ln.get("animal"):
            noises, said = animals.split_line(text, ln["animal"])
            clip, marks = animals.noise_clip(noises) if noises else (None, [])
            if clip is not None and len(clip):
                import soundfile as _sf
                part = out_audio.with_name(f"{out_audio.stem}_l{i:02d}_animal.wav")
                _sf.write(str(part), clip, animals.sfx.SR, subtype="PCM_16")
                dur = len(clip) / animals.sfx.SR
                # the noise shows as a word (captions, the mouth moves with each bark) but is not a sound cue again
                words += [{"w": w, "s": round(s + t, 3), "e": round(e + t, 3), "fx": True} for w, s, e in marks]
                parts.append((part, dur, 0.18 if said else gap))
                t += dur + (0.18 if said else gap)
        if said:
            rate, pitch = ln.get("rate", "+0%"), ln.get("pitch", "+0Hz")
            emo = EMOTION_PROSODY.get(str(ln.get("emotion", "")).lower())
            if emo:
                rate, pitch = _add(rate, emo[0], "%"), _add(pitch, emo[1], "Hz")
            part = out_audio.with_name(f"{out_audio.stem}_l{i:02d}.mp3")
            w = synthesize_scene_voice(said, ln.get("voice_id") or "en-US-ChristopherNeural", part, rate=rate, pitch=pitch)
            if part.is_file() and part.stat().st_size >= 500:
                dur = _get_duration(part) or (max((x["e"] for x in w), default=0.0) + 0.3)
                words += [{"w": x["w"], "s": round(x["s"] + t, 3), "e": round(x["e"] + t, 3)} for x in w]
                parts.append((part, dur, gap))
                t += dur + gap
        if t > start:
            spans.append((round(start, 3), round(t - gap, 3)))
    if not parts:
        return [], []
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for p, _d, _g in parts:
        cmd += ["-i", str(p)]
    chain = "".join(f"[{i}:a]aresample=48000,aformat=channel_layouts=mono,apad=pad_dur={parts[i][2] if i < len(parts) - 1 else 0.01}[a{i}];"
                    for i in range(len(parts)))
    chain += "".join(f"[a{i}]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1[out]"
    cmd += ["-filter_complex", chain, "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "128k", str(out_audio)]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=180)
    if r.returncode != 0:
        log.error("joining scene lines failed: %s", r.stderr[-300:])
        return [], []
    for p, _d, _g in parts:
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


_OLD = re.compile(r"\b(old|elder|aged|grand\w*)\b|दादा|दादी|नाना|नानी|बूढ़|बुजुर्ग", re.I)
_BIG = re.compile(r"bear|elephant|lion|tiger|bull|cow|gorilla|giant|dragon|dino|wolf|भालू|हाथी|शेर|बाघ|बैल|गाय|दानव", re.I)
_SMALL = re.compile(r"mouse|rat|bird|chick|rabbit|bunny|squirrel|kitten|puppy|fairy|spirit|frog|duck|"
                    r"चूहा|चिड़िया|खरगोश|गिलहरी|परी|मेंढक", re.I)


def cast_voice(lang: str, hint: str = "", used: list | None = None) -> dict:
    """Cast a voice for a character: a voice in the language that matches who they are, plus their own pitch and
    speed (a big bear deeper and slower, a child or a mouse higher and quicker). Languages with few voices
    (Hindi has two) still give every character a different sound: repeats of a voice are shifted apart.
    used: the {voice_id, voice_rate, voice_pitch} already given to the rest of the cast."""
    used = list(used or [])
    voices = list_voices(lang) or list_voices("en")
    want = guess_gender(hint)
    child, old = bool(_CHILD.search(hint or "")), bool(_OLD.search(hint or ""))
    big, small = bool(_BIG.search(hint or "")), bool(_SMALL.search(hint or ""))
    same_gender = [v for v in voices if v["gender"] == want] or voices
    if child:   # a child voice when the language has one; otherwise a lifted female voice, as cartoons do
        kids = [v for v in voices if "Child" in v["name"] or "Boyish" in v["name"]]
        same_gender = kids or [v for v in voices if v["gender"] == "female"] or same_gender
    counts = {v["id"]: sum(1 for u in used if u.get("voice_id") == v["id"]) for v in same_gender}
    voice = min(same_gender, key=lambda v: (counts[v["id"]], same_gender.index(v)))["id"]
    rate, pitch = 0, 0
    if big:
        rate, pitch = -8, -14
    elif small:
        rate, pitch = 10, 22
    elif child:
        rate, pitch = 8, 16 if want == "male" else 12
    elif old:
        rate, pitch = -12, -4
    taken = {(u.get("voice_id"), u.get("voice_rate"), u.get("voice_pitch")) for u in used}
    k = 0
    while (voice, _pct(rate), _hz(pitch)) in taken and k < 8:   # same voice and sound: move it apart
        k += 1
        pitch += 7 if k % 2 else -14
        rate += 3
    return {"voice_id": voice, "voice_rate": _pct(rate), "voice_pitch": _hz(pitch)}
