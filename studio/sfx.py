"""Sound effects for generated episodes: footsteps, jumps, doors, cars, phones, thunder, stingers…

Every effect is synthesised here with numpy (no downloads, no licences). Your own recordings win: a file in
<data>/music/sfx/<name>.wav|mp3|… replaces the built-in one of that name.

plan_scene() decides which effects a scene gets and when, from:
  - what the characters do in the 3D scene (walking in → footsteps on that ground, a jump → whoosh and landing),
  - words in the dialogue (car / गाड़ी → engine, door / दरवाज़ा → creak, phone / फ़ोन → ring…), at the word,
  - the script ("sfx": ["door_creak"] on a line),
  - the format's theme (a horror hit on a scare, a comedy boing on a surprise, a kids ta-da at a happy end).
"""
from __future__ import annotations

import logging
import re
import subprocess
import zlib
from pathlib import Path

import numpy as np

from studio import config

log = logging.getLogger("peakcut.sfx")
SR = 32000
NO_WINDOW = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
USER_DIR = config.DATA_DIR / "music" / "sfx"
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".ogg", ".flac")


# ---------------------------------------------------------------- building blocks
def _t(sec: float) -> np.ndarray:
    return np.arange(int(sec * SR)) / SR


def _noise(n: int, rng, lo: float = 0, hi: float = 16000, tilt: float = 0.0) -> np.ndarray:
    spec = rng.normal(size=n // 2 + 1) + 1j * rng.normal(size=n // 2 + 1)
    f = np.fft.rfftfreq(n, 1 / SR)
    f[0] = 1.0
    if tilt:
        spec /= f ** (tilt / 2)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / (np.max(np.abs(x)) + 1e-9)


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / max(decay, 1e-4))


def _glide(f0: float, f1: float, sec: float) -> np.ndarray:
    t = _t(sec)
    f = f0 * (f1 / f0) ** (t / sec)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def _norm(x: np.ndarray, peak: float = 0.8) -> np.ndarray:
    return (x / (np.max(np.abs(x)) + 1e-9) * peak).astype(np.float32)


# ---------------------------------------------------------------- the effects
def _step(rng, kind="grass"):
    n = int(0.16 * SR)
    lo, hi, body = {"grass": (900, 7000, 0.5), "wood": (200, 3000, 1.0), "snow": (1500, 9000, 0.3),
                    "sand": (700, 5000, 0.35)}.get(kind, (900, 7000, 0.5))
    x = _noise(n, rng, lo, hi) * _env(n, 0.004, 0.035)
    x += body * np.sin(2 * np.pi * 85 * _t(0.16)) * _env(n, 0.002, 0.025)
    return _norm(x, 0.6)


def _whoosh(rng):
    sec = 0.45
    n = int(sec * SR)
    x = _noise(n, rng, 300, 5000, tilt=0.8) * np.sin(np.pi * _t(sec) / sec) ** 2
    return _norm(x, 0.55)


def _thud(rng):
    t = _t(0.35)
    x = np.sin(2 * np.pi * (90 - 50 * t) * t) * _env(len(t), 0.002, 0.08)
    x += 0.3 * _noise(len(t), rng, 60, 900) * _env(len(t), 0.001, 0.03)
    return _norm(x, 0.8)


def _pop(rng):
    t = _t(0.12)
    return _norm(np.sin(2 * np.pi * (900 - 4000 * t) * t) * _env(len(t), 0.001, 0.03), 0.6)


def _boing(rng):
    t = _t(0.7)
    f = 180 + 60 * np.sin(2 * np.pi * 14 * t) * np.exp(-3 * t) + 80 * t
    return _norm(np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(len(t), 0.003, 0.3), 0.7)


def _slide_whistle(rng):
    sec = 0.8
    up = _glide(500, 1400, sec / 2)
    down = _glide(1400, 600, sec / 2)
    x = np.concatenate([up, down])
    return _norm(x * np.sin(np.pi * _t(len(x) / SR) / (len(x) / SR)) ** 0.5, 0.45)


def _tada(rng):
    out = np.zeros(int(1.4 * SR))
    for k, (start, notes) in enumerate([(0.0, [72, 76, 79]), (0.18, [77, 81, 84])]):
        a0 = int(start * SR)
        t = _t(1.2)
        y = sum(np.sin(2 * np.pi * 440 * 2 ** ((m - 69) / 12) * t) for m in notes) * _env(len(t), 0.005, 0.35 + 0.2 * k)
        out[a0:a0 + len(t)] += y[: len(out) - a0]
    return _norm(out, 0.55)


def _sparkle(rng):
    out = np.zeros(int(1.0 * SR))
    for k in range(7):
        a0 = int(k * 0.07 * SR)
        t = _t(0.4)
        f = 2000 + 300 * k + rng.uniform(-80, 80)
        out[a0:a0 + len(t)] += np.sin(2 * np.pi * f * t) * _env(len(t), 0.002, 0.08)
    return _norm(out, 0.35)


def _heartbeat(rng):
    out = np.zeros(int(0.9 * SR))
    for start, g in ((0.0, 1.0), (0.22, 0.7)):
        t = _t(0.25)
        a0 = int(start * SR)
        out[a0:a0 + len(t)] += g * np.sin(2 * np.pi * (60 - 20 * t) * t) * _env(len(t), 0.004, 0.06)
    return _norm(out, 0.9)


def _horror_hit(rng):
    sec = 2.6
    t = _t(sec)
    n = len(t)
    boom = np.sin(2 * np.pi * (55 - 15 * t / sec) * t) * _env(n, 0.003, 0.9)
    cluster = sum(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) for f in (311, 330, 349, 370)) * _env(n, 0.01, 0.7) * 0.25
    hiss = _noise(n, rng, 2000, 9000) * _env(n, 0.001, 0.15) * 0.4
    return _norm(boom + cluster + hiss, 0.9)


def _whisper_swell(rng):
    sec = 1.6
    t = _t(sec)
    x = _noise(len(t), rng, 1200, 7000) * (t / sec) ** 2.5
    x[-int(0.03 * SR):] *= np.linspace(1, 0, int(0.03 * SR))
    return _norm(x, 0.5)


def _creak(rng):
    sec = 1.1
    t = _t(sec)
    f = 140 + 70 * np.sin(2 * np.pi * 0.9 * t) + rng.normal(0, 6, len(t)).cumsum() * 0.02
    saw = 2 * ((np.cumsum(f) / SR) % 1.0) - 1
    grain = (np.sin(2 * np.pi * 38 * t) > 0.2).astype(float) * 0.6 + 0.4
    x = saw * grain * np.sin(np.pi * t / sec) ** 0.7
    return _norm(np.convolve(x, np.ones(6) / 6, mode="same"), 0.5)


def _knock(rng):
    out = np.zeros(int(0.8 * SR))
    for k in range(3):
        a0 = int(k * 0.2 * SR)
        y = _thud(rng)[: int(0.15 * SR)]
        y = y + 0.4 * _noise(len(y), rng, 800, 4000) * _env(len(y), 0.001, 0.01)
        out[a0:a0 + len(y)] += y
    return _norm(out, 0.8)


def _car_engine(rng):
    sec = 2.4
    t = _t(sec)
    rpm = 28 + 30 * np.clip(t / 1.4, 0, 1) ** 1.5
    ph = 2 * np.pi * np.cumsum(rpm) / SR
    x = sum(np.sin(k * ph) / k for k in range(1, 7))
    x += 0.5 * _noise(len(t), rng, 80, 1500) * (0.5 + 0.5 * np.sin(ph))
    x *= np.clip(t / 0.15, 0, 1) * np.clip((sec - t) / 0.4, 0, 1)
    return _norm(x, 0.6)


def _car_horn(rng):
    t = _t(0.5)
    x = np.sign(np.sin(2 * np.pi * 400 * t)) + np.sign(np.sin(2 * np.pi * 500 * t))
    x = np.convolve(x, np.ones(8) / 8, mode="same") * np.clip(t / 0.01, 0, 1) * np.clip((0.5 - t) / 0.03, 0, 1)
    return _norm(x, 0.45)


def _phone_ring(rng):
    out = np.zeros(int(2.2 * SR))
    for burst in (0.0, 1.2):
        t = _t(0.8)
        y = np.sin(2 * np.pi * 1300 * t) * (np.sin(2 * np.pi * 20 * t) > 0)
        a0 = int(burst * SR)
        out[a0:a0 + len(t)] += y
    return _norm(out, 0.35)


def _bell(rng):
    t = _t(2.5)
    x = sum(a * np.sin(2 * np.pi * 523 * r * t) * np.exp(-t * d) for r, a, d in
            ((1, 1, 1.2), (2.76, 0.5, 2.0), (5.4, 0.25, 3.0), (8.93, 0.12, 4.0)))
    return _norm(x, 0.5)


def _thunder(rng):
    sec = 4.0
    t = _t(sec)
    x = _noise(len(t), rng, 25, 600, tilt=1.5) * (np.exp(-t / 1.4) * (1 + 0.6 * np.sin(2 * np.pi * 1.3 * t)))
    x += 0.6 * _noise(len(t), rng, 400, 6000) * _env(len(t), 0.002, 0.08)
    return _norm(x, 0.8)


def _wind_gust(rng):
    sec = 2.5
    t = _t(sec)
    return _norm(_noise(len(t), rng, 150, 2500, tilt=1.5) * np.sin(np.pi * t / sec) ** 2, 0.5)


def _clock_tick(rng):
    out = np.zeros(int(2.0 * SR))
    for k in range(4):
        y = _noise(int(0.02 * SR), rng, 2000, 9000) * _env(int(0.02 * SR), 0.0005, 0.004)
        a0 = int(k * 0.5 * SR)
        out[a0:a0 + len(y)] += y * (1 if k % 2 == 0 else 0.7)
    return _norm(out, 0.5)


def _bird(rng):
    out = np.zeros(int(1.2 * SR))
    for k in range(4):
        a0 = int((k * 0.22 + rng.uniform(0, 0.05)) * SR)
        y = _glide(2600 + rng.uniform(-200, 200), 4200, 0.09) * _env(int(0.09 * SR), 0.003, 0.05)
        out[a0:a0 + len(y)] += y
    return _norm(out, 0.35)


def _firework(rng):
    """A rocket going up, a bang and crackles."""
    sec = 2.6
    t = _t(sec)
    out = np.zeros(len(t))
    up = int(0.7 * SR)
    out[:up] = 0.35 * _noise(up, rng, 1500, 7000) * np.linspace(0.2, 1, up)
    b = len(t) - up
    out[up:] += _noise(b, rng, 40, 3000, tilt=1.2) * np.exp(-np.arange(b) / (0.25 * SR))
    for pos in rng.integers(up + int(0.2 * SR), len(t) - 400, size=40):
        out[pos:pos + 300] += rng.uniform(0.1, 0.4) * rng.normal(size=300) * np.exp(-np.arange(300) / 50)
    return _norm(out, 0.8)


def _splash(rng):
    sec = 1.2
    t = _t(sec)
    return _norm(_noise(len(t), rng, 300, 7000, tilt=0.8) * _env(len(t), 0.01, 0.25), 0.6)


def _rimshot(rng):
    t = _t(0.25)
    x = _noise(len(t), rng, 1500, 9000) * _env(len(t), 0.001, 0.05) + 0.6 * np.sin(2 * np.pi * 330 * t) * _env(len(t), 0.001, 0.04)
    return _norm(x, 0.6)


EFFECTS = {
    "step_grass": lambda r: _step(r, "grass"), "step_wood": lambda r: _step(r, "wood"),
    "step_snow": lambda r: _step(r, "snow"), "step_sand": lambda r: _step(r, "sand"),
    "whoosh": _whoosh, "thud": _thud, "pop": _pop, "boing": _boing, "slide_whistle": _slide_whistle,
    "tada": _tada, "sparkle": _sparkle, "heartbeat": _heartbeat, "horror_hit": _horror_hit,
    "whisper_swell": _whisper_swell, "door_creak": _creak, "knock": _knock, "car_engine": _car_engine,
    "car_horn": _car_horn, "phone_ring": _phone_ring, "bell": _bell, "thunder": _thunder,
    "wind_gust": _wind_gust, "clock_tick": _clock_tick, "bird": _bird, "rimshot": _rimshot,
    "firework": _firework, "splash": _splash,
}
_cache: dict[str, np.ndarray] = {}

# ---------------------------------------------------------------- animals
# A voice-like source (a buzz at the animal's pitch, with breath noise) shaped by the resonances of its throat
# (formants), with the pitch moving the way the call does. Cartoon-real, not recordings: a recording of your own in
# <data>/music/sfx/<name>.wav (dog_bark.wav, cat_meow.wav...) is used instead when it is there.
def _curve(points: list, sec: float) -> np.ndarray:
    """A pitch (or any value) moving through [(time, value), ...] over sec seconds."""
    t = _t(sec)
    ts, vs = zip(*points)
    return np.interp(t, ts, vs)


def _buzz(f0: np.ndarray, rng, rough: float = 0.0, pure: float = 0.0) -> np.ndarray:
    """The voice source: a sawtooth at the pitch f0 (with a little wobble), roughness, and some pure tone."""
    jitter = 1 + 0.01 * np.convolve(rng.normal(size=len(f0)), np.ones(200) / 200, "same")
    ph = np.cumsum(f0 * jitter) / SR
    saw = 2 * (ph % 1) - 1
    x = (1 - pure) * saw + pure * np.sin(2 * np.pi * ph)
    if rough:
        t = np.arange(len(f0)) / SR
        x *= 1 - rough + rough * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 31 * t + rng.uniform(0, 6))))
    return x


def _throat(x: np.ndarray, formants: list) -> np.ndarray:
    """Shape a sound by resonances [(centre Hz, width Hz, strength)], like a mouth and throat do."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    h = 0.02 + sum(g * np.exp(-0.5 * ((f - fc) / bw) ** 2) for fc, bw, g in formants)
    return np.fft.irfft(spec * h, len(x))


def _call(sec, pitch, formants, rng, noise=0.2, rough=0.0, pure=0.0, attack=0.01, release=0.08, lo=200, hi=8000):
    t = _t(sec)
    n = len(t)
    src = _buzz(_curve(pitch, sec), rng, rough, pure) + noise * _noise(n, rng, lo, hi)
    x = _throat(src, formants)
    env = np.clip(t / attack, 0, 1) * np.clip((sec - t) / release, 0, 1)
    return x * env


def _dog_bark(rng):
    one = _call(0.2, [(0, 560), (0.05, 620), (0.2, 360)], [(750, 220, 1), (1500, 350, 0.7), (2700, 500, 0.3)], rng,
                noise=0.45, rough=0.25, attack=0.004, release=0.12, lo=300, hi=6000)
    return _norm(one, 0.85)


def _dog_growl(rng):
    return _norm(_call(1.1, [(0, 90), (0.5, 105), (1.1, 85)], [(350, 150, 1), (900, 300, 0.7), (2000, 500, 0.2)], rng,
                       noise=0.5, rough=0.7, attack=0.12, release=0.3, lo=80, hi=3000), 0.7)


def _dog_whine(rng):
    return _norm(_call(0.8, [(0, 900), (0.3, 1350), (0.8, 800)], [(1200, 400, 1), (2600, 500, 0.3)], rng,
                       noise=0.05, pure=0.6, attack=0.05, release=0.25), 0.55)


def _cat_meow(rng):
    sec = 0.85
    pitch = [(0, 480), (0.3, 780), (0.85, 430)]
    ee = _call(sec, pitch, [(450, 150, 1), (2200, 400, 0.8), (3200, 500, 0.3)], rng, noise=0.08, attack=0.06, release=0.3)
    ow = _call(sec, pitch, [(800, 200, 1), (1250, 250, 0.8), (2800, 500, 0.2)], rng, noise=0.08, attack=0.06, release=0.3)
    m = np.clip(_t(sec) / sec * 1.6 - 0.3, 0, 1)            # "mee" turning into "ow"
    return _norm(ee * (1 - m) + ow * m, 0.7)


def _cat_hiss(rng):
    t = _t(0.9)
    return _norm(_noise(len(t), rng, 2500, 10000) * np.clip(t / 0.05, 0, 1) * np.clip((0.9 - t) / 0.3, 0, 1), 0.5)


def _cow_moo(rng):
    return _norm(_call(1.6, [(0, 105), (0.3, 135), (1.1, 128), (1.6, 92)], [(320, 120, 1), (700, 200, 0.5), (2400, 400, 0.08)],
                       rng, noise=0.12, rough=0.1, attack=0.25, release=0.45, lo=100, hi=3000), 0.8)


def _lion_roar(rng):
    return _norm(_call(1.6, [(0, 110), (0.35, 190), (1.6, 75)], [(480, 250, 1), (1100, 400, 0.7), (2500, 700, 0.3)],
                       rng, noise=0.9, rough=0.6, attack=0.08, release=0.6, lo=60, hi=5000), 0.9)


def _duck_quack(rng):
    one = _call(0.22, [(0, 280), (0.22, 230)], [(1000, 200, 1), (2400, 350, 0.8), (3500, 500, 0.3)], rng,
                noise=0.15, rough=0.2, attack=0.01, release=0.1)
    gap = np.zeros(int(0.08 * SR))
    return _norm(np.concatenate([one, gap, one * 0.85]), 0.7)


def _goat_baa(rng):
    sec = 0.9
    t = _t(sec)
    base = _call(sec, [(0, 300), (0.9, 280)], [(700, 200, 1), (1300, 300, 0.6), (2600, 500, 0.2)], rng,
                 noise=0.1, attack=0.05, release=0.3)
    vib = 1 + 0.35 * np.sin(2 * np.pi * 7 * t)                  # the bleat's wobble
    return _norm(base * vib, 0.7)


def _horse_neigh(rng):
    sec = 1.3
    t = _t(sec)
    f = _curve([(0, 650), (0.2, 1100), (1.3, 450)], sec) * (1 + 0.08 * np.sin(2 * np.pi * 11 * t))
    src = _buzz(f, rng, 0.15) + 0.25 * _noise(len(t), rng, 300, 6000)
    x = _throat(src, [(900, 300, 1), (2000, 500, 0.5)])
    return _norm(x * np.clip(t / 0.05, 0, 1) * np.clip((sec - t) / 0.5, 0, 1), 0.7)


def _elephant_trumpet(rng):
    return _norm(_call(1.1, [(0, 340), (0.15, 660), (0.9, 600), (1.1, 400)], [(1100, 350, 1), (2600, 600, 0.6)], rng,
                       noise=0.3, rough=0.25, attack=0.04, release=0.25), 0.85)


def _crow_caw(rng):
    one = _call(0.32, [(0, 560), (0.32, 470)], [(1300, 300, 1), (2200, 400, 0.6)], rng, noise=0.6, rough=0.3,
                attack=0.01, release=0.12)
    gap = np.zeros(int(0.15 * SR))
    return _norm(np.concatenate([one, gap, one * 0.9]), 0.7)


def _rooster(rng):
    parts = []
    for sec, f0, f1 in ((0.14, 600, 650), (0.14, 780, 820), (0.2, 900, 950), (0.65, 950, 600)):
        parts.append(_call(sec, [(0, f0), (sec, f1)], [(1000, 300, 1), (2500, 500, 0.5)], rng, noise=0.15, rough=0.15,
                           attack=0.01, release=min(0.2, sec / 2)))
        parts.append(np.zeros(int(0.03 * SR)))
    return _norm(np.concatenate(parts), 0.75)


def _frog_croak(rng):
    sec = 0.5
    t = _t(sec)
    x = _call(sec, [(0, 110), (0.5, 100)], [(500, 200, 1), (1400, 300, 0.4)], rng, noise=0.2, attack=0.01, release=0.1)
    return _norm(x * (np.sin(2 * np.pi * 22 * t) > 0), 0.7)


def _wolf_howl(rng):
    return _norm(_call(2.2, [(0, 380), (0.4, 620), (1.6, 600), (2.2, 420)], [(800, 300, 1), (1600, 400, 0.3)], rng,
                       noise=0.05, pure=0.5, attack=0.2, release=0.6), 0.7)


def _snake_hiss(rng):
    t = _t(1.2)
    return _norm(_noise(len(t), rng, 3000, 10000) * np.clip(t / 0.15, 0, 1) * np.clip((1.2 - t) / 0.4, 0, 1), 0.5)


def _monkey(rng):
    parts = []
    for k in range(6):
        f = rng.uniform(700, 1400)
        parts.append(_call(0.09, [(0, f), (0.09, f * 1.3)], [(1100, 300, 1), (2500, 500, 0.4)], rng, noise=0.2,
                           attack=0.005, release=0.04))
        parts.append(np.zeros(int(rng.uniform(0.03, 0.08) * SR)))
    return _norm(np.concatenate(parts), 0.7)


def _pig_oink(rng):
    sec = 0.28
    t = _t(sec)
    one = _call(sec, [(0, 200), (0.28, 170)], [(420, 150, 1), (1000, 300, 0.5)], rng, noise=0.5, rough=0.5,
                attack=0.01, release=0.1) * (0.6 + 0.4 * np.sin(2 * np.pi * 40 * t))
    return _norm(np.concatenate([one, np.zeros(int(0.1 * SR)), one]), 0.7)


def _owl_hoot(rng):
    a = _call(0.35, [(0, 390), (0.35, 370)], [(390, 120, 1)], rng, noise=0.03, pure=0.9, attack=0.05, release=0.15)
    b = _call(0.6, [(0, 380), (0.6, 350)], [(380, 120, 1)], rng, noise=0.03, pure=0.9, attack=0.05, release=0.3)
    return _norm(np.concatenate([a, np.zeros(int(0.25 * SR)), b]), 0.6)


def _donkey(rng):
    parts = []
    for _ in range(2):
        parts.append(_call(0.35, [(0, 850), (0.35, 950)], [(1100, 300, 1), (2600, 500, 0.5)], rng, noise=0.3, rough=0.3,
                           attack=0.02, release=0.1))
        parts.append(_call(0.4, [(0, 320), (0.4, 260)], [(600, 200, 1), (1200, 300, 0.5)], rng, noise=0.3, rough=0.4,
                           attack=0.02, release=0.15))
    return _norm(np.concatenate(parts), 0.75)


EFFECTS.update({
    "dog_bark": _dog_bark, "dog_growl": _dog_growl, "dog_whine": _dog_whine, "cat_meow": _cat_meow,
    "cat_hiss": _cat_hiss, "cow_moo": _cow_moo, "lion_roar": _lion_roar, "duck_quack": _duck_quack,
    "goat_baa": _goat_baa, "horse_neigh": _horse_neigh, "elephant_trumpet": _elephant_trumpet, "crow_caw": _crow_caw,
    "rooster": _rooster, "frog_croak": _frog_croak, "wolf_howl": _wolf_howl, "snake_hiss": _snake_hiss,
    "monkey": _monkey, "pig_oink": _pig_oink, "owl_hoot": _owl_hoot, "donkey": _donkey,
})


def _decode(path: Path) -> np.ndarray | None:
    try:
        p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                           capture_output=True, creationflags=NO_WINDOW, timeout=60)
        x = np.frombuffer(p.stdout, dtype=np.float32)
        return x if len(x) else None
    except Exception:  # noqa: BLE001
        return None


def effect(name: str) -> np.ndarray | None:
    """The samples of one effect: your own file in data/music/sfx/<name>.* if there is one, else the built-in."""
    if name in _cache:
        return _cache[name]
    x = None
    if USER_DIR.is_dir():
        own = next((p for p in sorted(USER_DIR.iterdir()) if p.stem.lower() == name and p.suffix.lower() in AUDIO_EXT), None)
        if own:
            x = _decode(own)
    if x is None and name in EFFECTS:
        x = EFFECTS[name](np.random.default_rng(zlib.crc32(name.encode()) % 1000))   # same sound on every run
    if x is not None:
        _cache[name] = x
    return x


# ---------------------------------------------------------------- what the dialogue asks for
# word (English, Hinglish, Hindi) -> effect. A Hindi stem matches its forms (गाड़ी, गाड़ियाँ); short or common
# words are matched only whole (कार, not सरकार; "bus" left out: बस also means "enough").
WORD_SFX = [
    (r"cars?|gaadi|gadi|truck|jeep|गाड़ी|गाडी|ट्रक|जीप|कार", "car_engine"),
    (r"horn|honk|हॉर्न|पों", "car_horn"),
    (r"doors?|darwaza|darwaja|दरवाज़ा|दरवाजा|दरवाज़े|दरवाजे|किवाड़", "door_creak"),
    (r"knock|knocking|khatkhat|खटखट|खट-खट", "knock"),
    (r"phone|call|ringing|फ़ोन|फोन|मोबाइल", "phone_ring"),
    (r"bells?|ghanti|घंटी|घंटा", "bell"),
    (r"thunder|storm|lightning|toofan|tufan|तूफ़ान|तूफान|बिजली", "thunder"),
    (r"fireworks?|patakhe?|pataka|पटाखे|पटाखा|आतिशबाज़ी|आतिशबाजी", "firework"),
    (r"splash|chhapak|छपाक", "splash"),
    # animals named doing their sound in a line ("कुत्ता भौंका", "the lion roared"); an animal's own noises
    # ("भौं-भौं!") are made in studio/animals.py
    (r"barks?|barked|barking|भौंक[ऀ-ॿ]*", "dog_bark"),
    (r"growls?|growled|growling|गुर्रा[ऀ-ॿ]*", "dog_growl"),
    (r"meows?|meowed|मिमिया[ऀ-ॿ]*", "cat_meow"),
    (r"roars?|roared|roaring|दहाड़[ऀ-ॿ]*", "lion_roar"),
    (r"moos?|mooed|रंभा[ऀ-ॿ]*", "cow_moo"),
    (r"neighs?|neighed|हिनहिना[ऀ-ॿ]*", "horse_neigh"),
    (r"trumpeted|चिंघाड़[ऀ-ॿ]*", "elephant_trumpet"),
    (r"howls?|howled|howling", "wolf_howl"),
    (r"hiss(?:es|ed|ing)?|फुफकार[ऀ-ॿ]*", "snake_hiss"),
    (r"quacks?|quacked", "duck_quack"),
    (r"wind|hawa|aandhi|हवा|आंधी|आँधी", "wind_gust"),
    (r"clock|ghadi|tick|घड़ी", "clock_tick"),
    (r"birds?|chidiya|chirp|चिड़िया|चिडिया|पक्षी|पंछी", "bird"),
    (r"magic|magical|jaadu|jadu|जादू|जादुई|चमत्कार", "sparkle"),
    (r"heartbeat|dhadkan|धड़कन", "heartbeat"),
]
_WORD_RE = [(re.compile(rf"^(?:{p})$", re.I), name) for p, name in WORD_SFX]
_STRIP = re.compile(r"[^\wऀ-ॿ-]+")


def words_to_sfx(words: list[dict]) -> list[tuple[float, str]]:
    """(time, effect) for the words that call an effect, at the moment the word is said."""
    out = []
    for w in words:
        if w.get("fx"):          # an animal's own noise: its sound is already there
            continue
        k = _STRIP.sub("", str(w.get("w", ""))).lower()
        if not k:
            continue
        for rx, name in _WORD_RE:
            if rx.match(k) or (len(k) > 4 and any(rx.match(k[:n]) for n in range(4, len(k)) if "ऀ" <= k[0] <= "ॿ")):
                out.append((float(w["s"]), name))
                break
    return out


# ---------------------------------------------------------------- what is seen on screen makes its sound
# on-screen happening (web/studio3d/story.js) -> [(delay after it starts, effect, gain)]
FX_SFX = {
    "lightning": [(0.0, "whoosh", 0.25), (0.7, "thunder", 0.85)],        # the flash, then the thunder a moment later
    "falling_stars": [(0.0, "sparkle", 0.6), (0.6, "whoosh", 0.4)],
    "sparkles": [(0.0, "sparkle", 0.55)],
    "fireworks": [(0.0, "firework", 0.7), (1.4, "firework", 0.55)],
    "rainbow": [(0.0, "sparkle", 0.45)],
    "birds": [(0.0, "bird", 0.6)],
    "wind": [(0.0, "wind_gust", 0.6)],
}
# a thing that appears in the scene (a prop): flying things whoosh, things that pop up pop, cars drive in
PROP_HOW_SFX = {"fly": "whoosh", "pop": "pop", "drop": "thud", "drive": "car_engine"}


def screen_sfx(spec: dict | None) -> list[tuple[float, str, float]]:
    """The sounds of what happens on screen: lightning thunders, stars falling sparkle, fireworks bang."""
    if not spec:
        return []
    story = spec.get("story") or {}
    ev = []
    for f in story.get("fx") or []:
        for d, name, g in FX_SFX.get(str(f.get("name")), []):
            ev.append((float(f.get("t0", 0)) + d, name, g))
    # a storm outside while the scene is indoors (inside the train, a room): no flash is seen, the thunder is heard
    world = spec.get("world") or {}
    if world.get("weather") == "storm" and not any(f.get("name") == "lightning" for f in story.get("fx") or []):
        total = float(spec.get("duration") or 0)
        t, k = min(2.0, total / 3), 0
        while total and t < total - 1.5:
            ev.append((t, "thunder", 0.55))
            k += 1
            t += 9.0 + (k * 3.7) % 5
    for p in story.get("props") or []:
        name = PROP_HOW_SFX.get(str(p.get("how")))
        if name:
            ev.append((float(p.get("t0", 0)), name, 0.4))
    return ev


# ---------------------------------------------------------------- the background sound of a place
WATER = {"river", "ghat", "lake", "beach", "waterfall"}
CROWD = {"bazaar", "mela", "station", "stadium", "cafe"}
ROAD = {"city_street", "highway", "bus_stop"}
NATURE = {"forest_green", "forest_autumn", "jungle", "garden", "village", "farm", "field", "playground", "mountain",
          "temple", "ruins", "palace", "haveli"}


def scene_beds(world: dict | None, fallback: str = "") -> list[tuple[str, float, bool]]:
    """[(background sound, level, heard through walls)] for a scene's place, time and weather: rain when it rains
    (muffled indoors), wind in storms, snow and fog, water by rivers and the sea, a crowd in markets and stations,
    traffic on roads, the train's rhythm inside a train, birds by day and crickets by night outdoors."""
    if not world:
        return [(fallback, 0.8, False)] if fallback else []
    from studio.anim3d.sets import INDOOR
    kit = str(world.get("preset") or "")
    weather = str(world.get("weather") or "")
    time = str(world.get("time") or "")
    indoor = kit in INDOOR
    night = time in ("night", "midnight") or world.get("mood") == "night"
    beds: list[tuple[str, float, bool]] = []
    if weather in ("rain", "storm"):
        beds.append(("rain", 1.0 if weather == "storm" else 0.85, indoor))
        if weather == "storm" and not indoor:
            beds.append(("wind", 0.55, False))
    elif weather in ("snow", "fog") and not indoor:
        beds.append(("wind", 0.45 if weather == "snow" else 0.3, False))
    if kit == "train_interior":
        beds.append(("train", 0.9, False))
    elif kit in ("underwater",):
        beds.append(("underwater", 0.9, False))
    elif kit in ("space", "space_station", "lab"):
        beds.append(("hum", 0.5, False))
    elif kit in WATER:
        beds.append(("water", 0.6 if weather in ("rain", "storm") else 0.8, False))
    elif kit in CROWD:
        beds.append(("crowd", 0.55 if night else 0.75, indoor))
    elif kit in ROAD:
        beds.append(("traffic", 0.6, False))
    elif kit in ("cave", "haunted_house", "graveyard", "castle", "desert"):
        beds.append(("wind", 0.35, False))
    elif not indoor and weather not in ("rain", "storm"):
        if night:
            beds.append(("night", 0.7, False))
        elif kit in NATURE:
            beds.append(("birds", 0.7, False))
    if not beds and fallback:
        beds.append((fallback, 0.7, False))
    return beds[:3]


# ---------------------------------------------------------------- one scene's effects
GROUND = {"snow": "step_snow", "beach": "step_sand", "room": "step_wood", "space": "step_wood"}
SCARY = {"scared", "fear", "afraid", "terrified", "mysterious", "whisper"}
SURPRISE = {"surprised", "shocked", "amazed", "curious"}
HAPPY = {"happy", "excited", "joy", "laughing", "funny"}


def plan_scene(spec: dict | None, words: list[dict], lines: list[dict], spans: list, theme: dict,
               duration: float, last_scene: bool = False) -> list[tuple[float, str, float]]:
    """[(time in the scene, effect, gain 0..1)] for one scene."""
    ev: list[tuple[float, str, float]] = []
    stings = theme.get("stings", {})
    # 1. what the characters do in the 3D scene
    if spec:
        step = GROUND.get(str(spec.get("world", {}).get("preset", "")), "step_grass")
        for c in spec.get("cast", []):
            e = c.get("enter")
            if e and theme.get("steps", True):
                t, k = float(e.get("t0", 0)), 0
                while t < float(e.get("t1", 0)) - 0.1:
                    ev.append((t, step, 0.5 if k % 2 else 0.42))
                    t += 0.42
                    k += 1
        for a in spec.get("actions", []):
            t0, t1 = float(a.get("t0", 0)), float(a.get("t1", 0))
            if a.get("type") == "jump":
                ev.append((t0, "whoosh", 0.5))
                ev.append((t0 + (t1 - t0) * 0.72, "thud", 0.45))
            elif a.get("type") == "bounce" and stings.get("bounce"):
                ev.append((t0, stings["bounce"], 0.4))
    # 1b. what happens on screen (lightning, falling stars, fireworks, things flying in)
    ev.extend(screen_sfx(spec))
    # 2. words in the dialogue
    for t, name in words_to_sfx(words):
        ev.append((t, name, 0.7))
    # 3. the script, and 4. the theme, line by line
    for i, ln in enumerate(lines):
        t0, t1 = (spans[i] if i < len(spans) else (None, None))
        if t0 is None:
            continue
        for name in ln.get("sfx") or []:
            name = str(name).strip().lower().replace(" ", "_")
            if name in EFFECTS or (USER_DIR / f"{name}.wav").is_file():
                ev.append((t0, name, 0.7))
        emo = str(ln.get("emotion") or "").lower()
        if emo in SCARY and stings.get("scared"):
            ev.append((max(0.0, t0 - 0.2), stings["scared"], 0.6))
        if emo in SURPRISE and stings.get("surprise"):
            ev.append((t0, stings["surprise"], 0.55))
        if emo in HAPPY and stings.get("funny") and i == len(lines) - 1:
            ev.append((min(duration - 0.3, t1 + 0.15), stings["funny"], 0.5))
    if last_scene and stings.get("end"):
        happy_end = lines and str(lines[-1].get("emotion") or "").lower() in HAPPY
        if happy_end or theme.get("end_always"):
            ev.append((max(0.0, duration - 1.6), stings["end"], 0.6))
    # the same effect never twice within 3 s (except footsteps), and at most 10 per scene
    ev.sort()
    kept, last = [], {}
    for t, name, g in ev:
        if not name.startswith("step_") and t - last.get(name, -99) < 3.0:
            continue
        last[name] = t
        kept.append((round(t, 3), name, g))
    steps = [e for e in kept if e[1].startswith("step_")]
    others = [e for e in kept if not e[1].startswith("step_")][:14]
    return sorted(steps + others)


def render_track(events: list[tuple[float, str, float]], total: float) -> np.ndarray:
    """All the effects of the episode laid on one track as long as the episode."""
    out = np.zeros(int(total * SR) + SR, dtype=np.float32)
    for t, name, g in events:
        x = effect(name)
        if x is None:
            continue
        a0 = int(max(0.0, t) * SR)
        if a0 >= len(out):
            continue
        seg = x[: len(out) - a0]
        out[a0:a0 + len(seg)] += g * seg
    peak = float(np.max(np.abs(out))) if len(out) else 0.0
    if peak > 0.95:
        out *= 0.95 / peak
    return out[: int(total * SR)]
