"""Soundtrack engine: background music, ambience and the final audio mix of a generated video.

Music comes from your own library first:  <data>/music/<mood>/*.mp3|wav|m4a|ogg  (any royalty-free tracks you own).
When a mood has no tracks, a seamless loop is synthesised locally (numpy), so every format has a fitting bed
with no downloads and no licence worries:

    calm, playful, wonder, lullaby, epic, horror, tension, emotional, upbeat, synth, chiptune, quirky, jazz_noir

Ambience beds (also synthesised): rain, wind, night, hum.

mix_video() lays music + ambience under the dialogue, ducks the music whenever someone speaks (sidechain
compression) and normalises the result to -14 LUFS, the loudness YouTube, TikTok and Reels play at.
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
AMBIENCES = ["rain", "wind", "night", "hum"]


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


def mix_video(video_in: Path, out_mp4: Path, mood: str = "calm", ambience: str = "", music_db: float = -20,
              ambience_db: float = -30, seed: int = 0) -> bool:
    """Dialogue + ducked music + ambience, normalised to -14 LUFS. Video is copied, not re-encoded."""
    music = music_track(mood, seed)
    amb = ambience_track(ambience, seed)
    if not music and not amb:
        return False
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video_in)]
    parts = ["[0:a]aresample=48000,aformat=channel_layouts=stereo,asplit=2[dlg][key]"]
    mix_in = ["[dlg]"]
    idx = 1
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={music_db}dB[mus]")
        parts.append("[mus][key]sidechaincompress=threshold=0.02:ratio=6:attack=30:release=600:makeup=1[duck]")
        mix_in.append("[duck]")
        idx += 1
    else:
        parts[0] = "[0:a]aresample=48000,aformat=channel_layouts=stereo[dlg]"
    if amb:
        cmd += ["-stream_loop", "-1", "-i", str(amb)]
        parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={ambience_db}dB[amb]")
        mix_in.append("[amb]")
    parts.append(f"{''.join(mix_in)}amix=inputs={len(mix_in)}:normalize=0:duration=first,"
                 "loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[aout]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[aout]", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out_mp4)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=900)
        if p.returncode != 0:
            log.warning("soundtrack mix failed: %s", p.stderr[-400:])
        return p.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        log.warning("soundtrack mix error: %s", e)
        return False
