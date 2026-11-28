"""Soundtrack engine: background music, ambience and the final audio mix of a generated video.

Music comes from your own library first:  <data>/music/<mood>/*.mp3|wav|m4a|ogg  (any royalty-free tracks you own).
When a mood has no tracks, a seamless loop is synthesised locally (numpy), so every format has a fitting bed
with no downloads and no licence worries:

    calm, playful, wonder, lullaby, epic, horror, tension, emotional, upbeat, synth, chiptune, quirky, jazz_noir

Ambience beds (also synthesised): rain, wind, night, hum.

mix_video() lays music + ambience under the dialogue, ducks the music whenever someone speaks (sidechain
compression) and normalises the result to -14 LUFS, the loudness YouTube, TikTok and Reels play at.

Theme music (build_score): every format has a theme (THEMES): which mood plays when a scene is calm, tense,
sad, happy or full of wonder, and which stingers it uses. Each scene gets its own mood from its lines' emotions
(or the script's "music" for the scene); scenes cross-fade into each other, the same mood carries on without
restarting, a short series tune opens every episode, and the music dips to near silence just before a scare.
Sound effects (footsteps, doors, cars, stingers) come from studio/sfx.py and are mixed in the same pass.
"""
from __future__ import annotations

import logging
import random
import subprocess
from pathlib import Path

import numpy as np

from studio import config

log = logging.getLogger("peakcut.soundtrack")
NO_WINDOW = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
SR = 32000
MUSIC_DIR = config.DATA_DIR / "music"
CACHE_DIR = config.DATA_DIR / "series" / "_sound_cache"
AUDIO_EXT = (".mp3", ".wav", ".m4a", ".ogg", ".flac")

MOODS = ["calm", "playful", "wonder", "lullaby", "epic", "horror", "tension", "emotional", "upbeat", "synth",
         "chiptune", "quirky", "jazz_noir"]
AMBIENCES = ["rain", "wind", "night", "hum", "birds", "water", "crowd", "traffic", "train", "underwater"]


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


# chords as MIDI notes, one bar each; tempo in BPM; voice = pad | pluck | square
_RECIPES = {
    "calm":      dict(chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]], bpm=60, voice="pad", bass=True),
    "playful":   dict(chords=[[60, 64, 67], [65, 69, 72], [67, 71, 74], [60, 64, 67]], bpm=112, voice="pluck", bass=True, pad=0.25),
    "wonder":    dict(chords=[[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 67]], bpm=70, voice="pad", sparkle=True),
    "lullaby":   dict(chords=[[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]], bpm=56, voice="pluck", soft=True, pad=0.3),
    "epic":      dict(chords=[[50, 57, 62], [46, 53, 58], [48, 55, 60], [45, 52, 57]], bpm=76, voice="pad", bass=True, drums="taiko"),
    "horror":    dict(chords=[[36, 37], [36, 42], [35, 36], [36, 43]], bpm=40, voice="drone", stabs=True),
    "tension":   dict(chords=[[45, 48, 52], [45, 48, 51], [44, 47, 51], [45, 48, 52]], bpm=90, voice="pulse", bass=True),
    "emotional": dict(chords=[[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]], bpm=66, voice="pluck", pad=0.45),
    "upbeat":    dict(chords=[[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]], bpm=118, voice="pluck", bass=True, drums="pop", pad=0.2),
    "synth":     dict(chords=[[45, 52, 57], [41, 48, 53], [43, 50, 55], [40, 47, 52]], bpm=96, voice="pulse", bass=True, pad=0.35),
    "chiptune":  dict(chords=[[60, 64, 67], [57, 60, 64], [65, 69, 72], [67, 71, 74]], bpm=132, voice="square", bass=True, drums="pop"),
    "quirky":    dict(chords=[[60, 63, 67], [62, 65, 69], [60, 63, 67], [58, 62, 65]], bpm=104, voice="pluck", bass=True),
    "jazz_noir": dict(chords=[[50, 53, 57, 60], [55, 59, 62, 65], [48, 52, 55, 59], [45, 49, 52, 55]], bpm=62, voice="pad", bass=True, soft=True),
}


def _shape_noise(n: int, rng, tilt: float = 1.0, lo: float = 0.0, hi: float = 20000.0) -> np.ndarray:
    """Coloured noise made in the frequency domain: periodic, so it loops with no seam."""
    spec = rng.normal(size=n // 2 + 1) + 1j * rng.normal(size=n // 2 + 1)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = 1.0
    spec *= 1.0 / f ** (tilt / 2)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / (np.max(np.abs(x)) + 1e-9)


def _tone(freq: float, t: np.ndarray, kind: str = "sine") -> np.ndarray:
    ph = 2 * np.pi * freq * t
    if kind == "square":
        return np.sign(np.sin(ph)) * 0.5
    if kind == "warm":  # a few soft harmonics
        return np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph)
    return np.sin(ph)


def _synth_music(mood: str, seed: int = 0) -> np.ndarray:
    r = _RECIPES.get(mood, _RECIPES["calm"])
    rng = np.random.default_rng(seed)
    beat = 60.0 / r["bpm"]
    bar = beat * 4
    bars = len(r["chords"]) * 2
    n = int(round(bar * bars * SR))
    t = np.arange(n) / SR
    out = np.zeros(n)
    voice = r["voice"]

    for b in range(bars):
        chord = r["chords"][b % len(r["chords"])]
        s0, s1 = int(b * bar * SR), int((b + 1) * bar * SR)
        tb = t[s0:s1] - t[s0]
        L = s1 - s0
        if voice in ("pad", "drone") or r.get("pad"):
            # raised-cosine crossfade at the bar edges: no clicks, and the loop end meets its start
            fade = int(min(0.25 * bar, 0.6) * SR)
            env = np.ones(L)
            env[:fade] = np.linspace(0, 1, fade)
            env[-fade:] = np.linspace(1, 0, fade)
            amt = r.get("pad", 1.0) if voice not in ("pad", "drone") else 1.0
            for note in chord:
                for det in (-0.12, 0.12):
                    f = _hz(note + det)
                    kind = "sine" if voice == "drone" else "warm"
                    out[s0:s1] += amt * 0.18 * env * _tone(f, t[s0:s1], kind) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.2 * tb))
        if voice in ("pluck", "square", "pulse"):
            steps = 8
            step = bar / steps
            pattern = [0, 1, 2, 1, 0, 2, 1, 2] if voice != "pulse" else [0] * 8
            for k in range(steps):
                a0 = s0 + int(k * step * SR)
                a1 = min(s1, a0 + int(step * SR * (1.6 if voice == "pluck" else 0.9)))
                tt = (np.arange(a1 - a0)) / SR
                note = chord[pattern[k] % len(chord)] + (12 if voice != "pulse" else 0)
                decay = 5.0 if voice == "pluck" else 9.0
                kind = "square" if voice == "square" else ("warm" if voice == "pulse" else "sine")
                gain = 0.16 if not r.get("soft") else 0.09
                out[a0:a1] += gain * np.exp(-decay * tt) * _tone(_hz(note), tt + a0 / SR, kind)
        if r.get("bass"):
            root = chord[0] - 12
            for k in range(4 if voice != "pad" else 2):
                a0 = s0 + int(k * (bar / (4 if voice != "pad" else 2)) * SR)
                a1 = min(s1, a0 + int(beat * SR * 0.9))
                tt = np.arange(a1 - a0) / SR
                out[a0:a1] += 0.22 * np.exp(-3.0 * tt) * np.sin(2 * np.pi * _hz(root) * tt)
        if r.get("drums"):
            for k in range(4):
                a0 = s0 + int(k * beat * SR)
                kl = min(s1, a0 + int(0.25 * SR))
                tt = np.arange(kl - a0) / SR
                if r["drums"] == "taiko" and k in (0, 2):
                    out[a0:kl] += 0.5 * np.exp(-9 * tt) * np.sin(2 * np.pi * (70 - 30 * tt) * tt)
                elif r["drums"] == "pop":
                    if k in (0, 2):
                        out[a0:kl] += 0.45 * np.exp(-14 * tt) * np.sin(2 * np.pi * (110 - 60 * tt) * tt)
                    h0 = a0 + int(beat * 0.5 * SR)
                    h1 = min(s1, h0 + int(0.05 * SR))
                    if h1 > h0:
                        out[h0:h1] += 0.06 * rng.normal(size=h1 - h0) * np.exp(-60 * np.arange(h1 - h0) / SR)
        if r.get("sparkle") and b % 2 == 1:
            a0 = s0 + int(bar * 0.5 * SR)
            a1 = min(s1, a0 + int(1.2 * SR))
            tt = np.arange(a1 - a0) / SR
            out[a0:a1] += 0.05 * np.exp(-3 * tt) * np.sin(2 * np.pi * _hz(chord[-1] + 24) * tt)
        if r.get("stabs") and b % 4 == 3:
            a0 = s0 + int(bar * 0.3 * SR)
            a1 = min(s1, a0 + int(bar * 0.6 * SR))
            tt = np.arange(a1 - a0) / SR
            env = np.sin(np.pi * tt / tt[-1]) if len(tt) > 1 else 1
            out[a0:a1] += 0.07 * env * (np.sin(2 * np.pi * _hz(78) * tt) + np.sin(2 * np.pi * _hz(84) * tt))

    if voice == "drone":
        out += 0.25 * _shape_noise(n, rng, tilt=2.0, lo=30, hi=900) * (0.6 + 0.4 * np.sin(2 * np.pi * t / (bar * 2)))
    out = np.tanh(out * 1.2)
    return (out / (np.max(np.abs(out)) + 1e-9) * 0.7).astype(np.float32)


def _synth_ambience(kind: str, seed: int = 0, seconds: float = 30.0) -> np.ndarray:
    rng = np.random.default_rng(seed + 7)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    if kind == "rain":
        x = 0.7 * _shape_noise(n, rng, tilt=0.6, lo=300, hi=9000)
        drops = np.zeros(n)
        for pos in rng.integers(0, n - 400, size=int(seconds * 25)):
            drops[pos:pos + 300] += rng.uniform(0.1, 0.35) * np.exp(-np.arange(300) / 40) * rng.normal(size=300)
        x += drops
    elif kind == "wind":
        x = _shape_noise(n, rng, tilt=2.0, lo=60, hi=2500)
        gust = 0.5 + 0.5 * np.sin(2 * np.pi * t / seconds * 3) * np.sin(2 * np.pi * t / seconds * 2 + 1)
        x *= 0.4 + 0.6 * gust
    elif kind == "night":
        x = 0.35 * _shape_noise(n, rng, tilt=1.0, lo=80, hi=3000)
        for start in np.arange(0, seconds, 2.4):
            for k in range(3):
                a0 = int((start + k * 0.09) * SR)
                a1 = min(n, a0 + int(0.05 * SR))
                tt = np.arange(a1 - a0) / SR
                x[a0:a1] += 0.12 * np.sin(2 * np.pi * 4300 * tt) * np.sin(np.pi * tt / 0.05)
    elif kind == "birds":       # a quiet outdoor day: soft air and birds now and then
        x = 0.25 * _shape_noise(n, rng, tilt=1.8, lo=80, hi=2000)
        for start in rng.uniform(0, seconds - 1.5, size=int(seconds / 2.2)):
            f0 = rng.uniform(2300, 3600)
            for k in range(int(rng.integers(2, 5))):
                a0 = int((start + k * rng.uniform(0.12, 0.2)) * SR)
                ln = int(rng.uniform(0.06, 0.11) * SR)
                if a0 + ln >= n:
                    break
                tt = np.arange(ln) / SR
                f = f0 + (rng.uniform(800, 1600)) * tt / tt[-1]
                x[a0:a0 + ln] += 0.22 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1])
    elif kind == "water":       # a river, the sea, a waterfall: rushing water that swells
        x = _shape_noise(n, rng, tilt=1.1, lo=120, hi=6000)
        x *= 0.7 + 0.3 * np.sin(2 * np.pi * t / seconds * 4) * np.sin(2 * np.pi * t / seconds * 3 + 0.5)
        for pos in rng.integers(0, n - 2000, size=int(seconds * 6)):      # little splashes
            x[pos:pos + 1600] += rng.uniform(0.1, 0.3) * np.exp(-np.arange(1600) / 300) * _shape_noise(1600, rng, 0.5, 800, 5000)
    elif kind == "crowd":       # a busy market or station: many voices far off, murmuring
        x = np.zeros(n)
        for _ in range(14):
            v = _shape_noise(n, rng, tilt=1.0, lo=250, hi=1800)
            syll = np.sin(2 * np.pi * rng.uniform(2.5, 5.0) * t + rng.uniform(0, 6)) > rng.uniform(-0.2, 0.4)
            x += v * (0.3 + 0.7 * syll) * (0.5 + 0.5 * np.sin(2 * np.pi * t / seconds * rng.integers(1, 4) + rng.uniform(0, 6)))
        x += 0.5 * _shape_noise(n, rng, tilt=2.0, lo=60, hi=900)
    elif kind == "traffic":     # a road: a low rumble and cars passing by
        x = 0.5 * _shape_noise(n, rng, tilt=2.2, lo=40, hi=900)
        for c in rng.uniform(0, seconds - 4, size=int(seconds / 5)):
            a0, ln = int(c * SR), int(rng.uniform(2.5, 4.0) * SR)
            tt = np.arange(ln) / SR
            x[a0:a0 + ln] += 0.6 * _shape_noise(ln, rng, 1.6, 60, 2500) * np.sin(np.pi * tt / tt[-1]) ** 3
    elif kind == "train":       # inside a moving train: rumble and the clack of the rails
        x = 0.55 * _shape_noise(n, rng, tilt=2.0, lo=30, hi=700)
        for start in np.arange(0, seconds, 1.3):
            for off in (0.0, 0.16):
                a0 = int((start + off) * SR)
                ln = min(int(0.07 * SR), n - a0)
                if ln > 0:
                    x[a0:a0 + ln] += 0.7 * _shape_noise(ln, rng, 1.2, 200, 3000) * np.exp(-np.arange(ln) / (0.015 * SR))
    elif kind == "underwater":  # deep and muffled, with bubbles
        x = 0.6 * _shape_noise(n, rng, tilt=2.4, lo=20, hi=400)
        for pos in rng.integers(0, n - 3000, size=int(seconds * 3)):
            ln = 2400
            tt = np.arange(ln) / SR
            x[pos:pos + ln] += 0.25 * np.sin(2 * np.pi * np.cumsum(rng.uniform(300, 600) + 2500 * tt) / SR) * np.exp(-tt / 0.02)
    else:  # hum: a ship / machine room tone
        x = 0.5 * np.sin(2 * np.pi * 55 * t) + 0.25 * np.sin(2 * np.pi * 110.3 * t)
        x += 0.4 * _shape_noise(n, rng, tilt=1.5, lo=40, hi=1200)
    return (x / (np.max(np.abs(x)) + 1e-9) * 0.6).astype(np.float32)


def _write_wav(samples: np.ndarray, path: Path) -> Path:
    import soundfile as sf
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), samples, SR, subtype="PCM_16")
    return path


def music_track(mood: str, seed: int = 0) -> Path | None:
    """A loopable music file for a mood: a track from your library, else a synthesised loop."""
    if not mood or mood == "none":
        return None
    lib = MUSIC_DIR / mood
    if lib.is_dir():
        tracks = sorted(p for p in lib.iterdir() if p.suffix.lower() in AUDIO_EXT)
        if tracks:
            return random.Random(seed).choice(tracks)
    out = CACHE_DIR / f"music_{mood}_{seed % 4}.wav"
    if not out.is_file():
        try:
            _write_wav(_synth_music(mood, seed % 4), out)
        except Exception as e:  # noqa: BLE001
            log.warning("music synth %s failed: %s", mood, e)
            return None
    return out


def ambience_track(kind: str, seed: int = 0) -> Path | None:
    if not kind or kind == "none":
        return None
    lib = MUSIC_DIR / "ambience" / kind
    if lib.is_dir():
        tracks = sorted(p for p in lib.iterdir() if p.suffix.lower() in AUDIO_EXT)
        if tracks:
            return random.Random(seed).choice(tracks)
    out = CACHE_DIR / f"amb_{kind}.wav"
    if not out.is_file():
        try:
            _write_wav(_synth_ambience(kind), out)
        except Exception as e:  # noqa: BLE001
            log.warning("ambience synth %s failed: %s", kind, e)
            return None
    return out


# ---------------------------------------------------------------- theme music
# per theme: the mood for each feeling, the stingers (studio/sfx.py names) and whether footsteps are heard
THEMES = {
    "kids":       dict(calm="lullaby", tense="quirky", sad="emotional", happy="upbeat", wonder="wonder",
                       stings={"surprise": "sparkle", "bounce": "pop", "end": "tada"}),
    "comedy":     dict(calm="quirky", tense="quirky", sad="emotional", happy="upbeat", wonder="playful",
                       stings={"surprise": "boing", "funny": "rimshot", "bounce": "boing", "end": "slide_whistle"}),
    "bedtime":    dict(calm="lullaby", tense="wonder", sad="lullaby", happy="lullaby", wonder="wonder",
                       stings={"surprise": "sparkle"}),
    "horror":     dict(calm="tension", tense="horror", sad="emotional", happy="tension", wonder="tension",
                       stings={"scared": "heartbeat", "surprise": "horror_hit"}, dip=True),
    "thriller":   dict(calm="jazz_noir", tense="tension", sad="emotional", happy="calm", wonder="tension",
                       stings={"surprise": "whisper_swell", "scared": "heartbeat"}, dip=True),
    "noir":       dict(calm="jazz_noir", tense="tension", sad="jazz_noir", happy="jazz_noir", wonder="jazz_noir",
                       stings={"surprise": "whisper_swell"}),
    "epic":       dict(calm="wonder", tense="tension", sad="emotional", happy="epic", wonder="wonder",
                       stings={"surprise": "whoosh"}),
    "scifi":      dict(calm="synth", tense="tension", sad="emotional", happy="synth", wonder="wonder",
                       stings={"surprise": "whoosh"}),
    "retro":      dict(calm="chiptune", tense="chiptune", sad="emotional", happy="chiptune", wonder="chiptune",
                       stings={"surprise": "pop", "bounce": "pop", "end": "tada"}),
    "doc":        dict(calm="calm", tense="tension", sad="emotional", happy="upbeat", wonder="wonder",
                       stings={}, steps=False),
    "drama":      dict(calm="calm", tense="tension", sad="emotional", happy="upbeat", wonder="wonder",
                       stings={"surprise": "whisper_swell"}),
    "motivation": dict(calm="emotional", tense="epic", sad="emotional", happy="epic", wonder="epic",
                       stings={}, steps=False),
}
FORMAT_THEME = {
    "kids_3d": "kids", "pixar_family": "kids", "cartoon_2d": "kids", "chhota_bheem": "kids", "claymation": "comedy",
    "comedy": "comedy", "bedtime": "bedtime", "horror": "horror", "scary_narration": "horror",
    "thriller": "thriller", "true_crime": "thriller", "noir": "noir", "anime": "epic", "fantasy": "epic",
    "mythology": "epic", "scifi": "scifi", "pixel": "retro", "history_doc": "doc", "explainer": "doc",
    "photoreal_drama": "drama", "motivational": "motivation", "sports_drama": "epic",
}
CATEGORY_THEME = {"Kids & Family": "kids", "Horror & Thriller": "horror", "Anime & Stylised": "epic",
                  "Documentary & Education": "doc", "Cinematic Fiction": "drama", "Faceless Channels": "motivation"}
LEVEL_GAIN = {1: 0.55, 2: 0.8, 3: 1.0}
_TENSE = {"scared", "fear", "afraid", "terrified", "angry", "mysterious", "whisper", "tense", "worried"}
_SAD = {"sad", "crying", "lonely", "hurt"}
_HAPPY = {"happy", "excited", "joy", "laughing", "funny", "proud"}
_WONDER = {"surprised", "curious", "amazed", "shocked", "wonder"}
_CALM = {"calm", "gentle", "soft", "relieved"}


def theme_for(fmt: dict, episode_mood: str = "") -> dict:
    """The format's music theme; its base mood is the format's own music (or the script's mood for the episode)."""
    name = FORMAT_THEME.get(fmt.get("id", "")) or CATEGORY_THEME.get(fmt.get("category", ""), "drama")
    th = dict(THEMES[name], name=name)
    base = episode_mood if episode_mood in MOODS else (fmt.get("sound") or {}).get("music", "calm")
    th["base"] = base if base in MOODS else "calm"
    return th


def scene_mood(lines: list[dict], theme: dict, override: str = "") -> tuple[str, int]:
    """(mood, level 1-3) for one scene: the script's choice, else the feeling its lines carry most."""
    if override in MOODS:
        return override, 2
    count = {"tense": 0, "sad": 0, "happy": 0, "wonder": 0, "calm": 0}
    for ln in lines:
        e = str(ln.get("emotion") or "").lower()
        for k, group in (("tense", _TENSE), ("sad", _SAD), ("happy", _HAPPY), ("wonder", _WONDER), ("calm", _CALM)):
            if e in group:
                count[k] += 1
    feel, n = max(count.items(), key=lambda kv: kv[1])
    if not n:
        return theme["base"], 2
    level = 3 if feel == "tense" and n >= 2 else 1 if feel in ("calm", "sad") else 2
    return theme.get(feel, theme["base"]), level


def _loop(mood: str, seed: int) -> np.ndarray | None:
    f = music_track(mood, seed)
    if not f:
        return None
    from studio import sfx
    return sfx._decode(f)


def _motif(theme: dict, seed: int) -> np.ndarray:
    """The series tune: five notes from the theme's base chords, the same in every episode of the series."""
    r = _RECIPES.get(theme["base"], _RECIPES["calm"])
    rng = np.random.default_rng(seed)
    tones = sorted({n + 12 for c in r["chords"][:2] for n in c})
    notes = [tones[i] for i in rng.integers(0, len(tones), size=5)]
    notes[-1] = r["chords"][0][0] + 12
    step = max(0.22, min(0.42, 60.0 / r["bpm"] * 0.5))
    out = np.zeros(int((step * 5 + 1.6) * SR))
    for k, m in enumerate(notes):
        a0 = int(k * step * SR)
        t = np.arange(int((1.6 if k == 4 else step * 2.2) * SR)) / SR
        f = _hz(m)
        y = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(4 * np.pi * f * t)) * np.exp(-t * (2.0 if k == 4 else 4.0))
        y *= np.clip(t / 0.005, 0, 1)
        out[a0:a0 + len(y)] += y[: len(out) - a0]
    return out / (np.max(np.abs(out)) + 1e-9)


def build_score(segments: list[tuple[float, float, str, int]], total: float, seed: int, theme: dict,
                dips: list[float] = (), motif: bool = True) -> np.ndarray | None:
    """The music for the whole episode: [(start, end, mood, level)] per scene → one track as long as the episode.
    The same mood carries on across scenes without restarting; a change of mood cross-fades over 1.5 s."""
    n = int(total * SR)
    if n <= 0 or not segments:
        return None
    out = np.zeros(n, dtype=np.float32)
    loops: dict[str, np.ndarray | None] = {}
    xf = int(1.5 * SR)
    for i, (s0, s1, mood, level) in enumerate(segments):
        if mood not in loops:
            loops[mood] = _loop(mood, seed)
        loop = loops[mood]
        if loop is None or not len(loop):
            continue
        a0 = max(0, int(s0 * SR) - (xf // 2 if i else 0))
        a1 = min(n, int(s1 * SR) + (xf // 2 if i < len(segments) - 1 else 0))
        if a1 <= a0:
            continue
        seg = loop[np.arange(a0, a1) % len(loop)] * LEVEL_GAIN.get(level, 0.8)
        w = np.ones(a1 - a0, dtype=np.float32)
        same_prev = i and segments[i - 1][2] == mood
        same_next = i < len(segments) - 1 and segments[i + 1][2] == mood
        k = min(xf, (a1 - a0) // 2)
        if i and k:     # equal-power fade in (a plain join when the mood does not change: the loop is continuous)
            w[:k] = np.sin(np.linspace(0, np.pi / 2, k)) if not same_prev else np.linspace(0, 1, k) ** 0.5
        if i < len(segments) - 1 and k:
            w[-k:] = np.cos(np.linspace(0, np.pi / 2, k)) if not same_next else np.linspace(1, 0, k) ** 0.5
        out[a0:a1] += seg * w
    if not np.any(out):
        return None
    fi, fo = int(min(1.0, total / 4) * SR), int(min(2.5, total / 3) * SR)
    out[:fi] *= np.linspace(0, 1, fi)
    out[-fo:] *= np.linspace(1, 0, fo)
    if theme.get("dip"):      # near silence just before a scare, then back
        g = np.ones(n, dtype=np.float32)
        for t in dips:
            d0, d1, d2 = int((t - 0.9) * SR), int((t - 0.15) * SR), int((t + 1.2) * SR)
            if d0 < 0 or d2 > n:
                continue
            g[d0:d1] = np.minimum(g[d0:d1], np.linspace(1, 0.12, d1 - d0))
            g[d1:d2] = np.minimum(g[d1:d2], np.linspace(0.12, 1, d2 - d1))
        out *= g
    if motif:
        m = _motif(theme, seed) * 0.55
        a0 = int(0.4 * SR)
        out[a0:a0 + len(m)] += m[: n - a0]
    return (out / (np.max(np.abs(out)) + 1e-9) * 0.7).astype(np.float32)


def _lowpass(x: np.ndarray, hz: float) -> np.ndarray:
    """Sound heard through a wall or a window: only the low part gets through."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    spec *= 1.0 / (1.0 + (f / hz) ** 4)
    return np.fft.irfft(spec, len(x)).astype(np.float32)


def _bed(kind: str, seed: int) -> np.ndarray | None:
    """The samples of one background sound (your own file in music/ambience/<kind>/, else made here)."""
    p = ambience_track(kind, seed)
    if not p:
        return None
    try:
        import soundfile as sf
        x, sr = sf.read(str(p), dtype="float32", always_2d=False)
        if x.ndim > 1:
            x = x.mean(axis=1)
        if sr != SR:
            x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x).astype(np.float32)
        if len(x) <= SR:
            return None
        # every background at its own steady loudness (by its average, not its loudest raindrop): rain clearly
        # there, birds and crickets soft, a machine hum low
        rms = float(np.sqrt(np.mean(x ** 2))) or 1.0
        x = x * (BED_LEVEL.get(kind, 0.1) / rms)
        return np.tanh(x * 1.2).astype(np.float32) / 1.2
    except Exception as e:  # noqa: BLE001
        log.warning("ambience %s unreadable: %s", kind, e)
        return None


BED_LEVEL = {"rain": 0.16, "wind": 0.12, "night": 0.07, "birds": 0.07, "crowd": 0.11, "traffic": 0.1, "train": 0.13,
             "water": 0.13, "underwater": 0.12, "hum": 0.07}


def build_ambience(segments: list, total: float, seed: int = 0) -> np.ndarray | None:
    """The background sounds of the whole episode, scene by scene: segments = [(start, end, [(kind, level,
    muffled)])]. Each scene's sounds fade in and out over 0.8 s, so rain starts where the rainy scene starts."""
    n = int(total * SR)
    if n <= 0 or not any(beds for _s, _e, beds in segments):
        return None
    out = np.zeros(n, dtype=np.float32)
    cache: dict = {}
    fade = int(0.8 * SR)
    for s, e, beds in segments:
        a0, a1 = int(max(0.0, s) * SR), min(n, int(e * SR) + fade // 2)
        if a1 - a0 < SR // 4:
            continue
        ln = a1 - a0
        ramp = np.ones(ln, dtype=np.float32)
        k = min(fade, ln // 2)
        ramp[:k] = np.linspace(0, 1, k)
        ramp[-k:] = np.linspace(1, 0, k)
        for kind, level, muffled in beds:
            key = (kind, muffled)
            if key not in cache:
                b = _bed(kind, seed)
                if b is not None and muffled:
                    b = _lowpass(b, 700) * 1.6
                cache[key] = b
            b = cache[key]
            if b is None:
                continue
            start = int((a0 * 7919) % len(b))          # a different stretch of the loop in each scene
            idx = (np.arange(ln) + start) % len(b)
            out[a0:a1] += float(level) * b[idx] * ramp
    peak = float(np.max(np.abs(out)))
    if peak > 0.95:
        out *= 0.95 / peak
    return out


def mix_video(video_in: Path, out_mp4: Path, mood: str = "calm", ambience: str = "", music_db: float = -20,
              ambience_db: float = -30, seed: int = 0, on_frac=None, music_file: Path | None = None,
              sfx_file: Path | None = None, sfx_db: float = -3, ambience_file: Path | None = None) -> bool:
    """Dialogue + ducked music + ambience (+ sound effects), normalised to -14 LUFS. Video is copied, not re-encoded.
    music_file: a score as long as the video (build_score); without it the mood's loop is repeated."""
    music = music_file or music_track(mood, seed)
    amb = ambience_file or ambience_track(ambience, seed)
    if not music and not amb and not sfx_file:
        return False
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video_in)]
    parts = ["[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[dlg][key]"]
    mix_in = ["[dlg]"]
    idx = 1
    if music:
        cmd += (["-i", str(music)] if music_file else ["-stream_loop", "-1", "-i", str(music)])
        parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={music_db}dB[mus]")
        # gentle, quick ducking: the music dips about 6 dB under speech and is back within a short pause
        # (it used to dip so far and come back so slowly that with talky 1-minute scenes it was never heard)
        parts.append("[mus][key]sidechaincompress=threshold=0.05:ratio=3:attack=40:release=250:makeup=1[duck]")
        mix_in.append("[duck]")
        idx += 1
    else:
        parts[0] = "[0:a]aresample=48000,aformat=channel_layouts=stereo[dlg]"
    if amb:
        cmd += (["-i", str(amb)] if ambience_file else ["-stream_loop", "-1", "-i", str(amb)])
        parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={ambience_db}dB[amb]")
        mix_in.append("[amb]")
        idx += 1
    if sfx_file:   # effects are not ducked: they belong to the action, like the voices
        cmd += ["-i", str(sfx_file)]
        parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={sfx_db}dB[fx]")
        mix_in.append("[fx]")
    parts.append(f"{''.join(mix_in)}amix=inputs={len(mix_in)}:normalize=0:duration=first,"
                 "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out_mp4)]
    try:
        from studio import concat, progress as prog
        p = prog.ffmpeg(cmd, concat._get_duration(video_in), on_frac, timeout=900)
        if p.returncode != 0:
            log.warning("soundtrack mix failed: %s", p.stderr[-400:])
        return p.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        log.warning("soundtrack mix error: %s", e)
        return False
