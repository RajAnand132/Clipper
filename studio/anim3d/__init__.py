"""Real 3D animation for generated videos (planning/09_REAL_3D_ANIMATION_ENGINE.md).

    characters.py   Character Vault entry -> toon 3D design (bear, cat, boy, grandma, robot, spirit...)
    director.py     script scene + voice timings -> 3D scene spec (cast, blocking, actions, faces, shots, world)
    worker.py       headless Chrome/Edge plays web/studio3d/runtime.js and records the frames with ffmpeg

production.render_scene uses render_scene_clip() for every format whose `render` is "anim3d" (the default) and
falls back to the picture + camera-motion pipeline when no browser is available or a render fails.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from studio.anim3d import characters, director, worker

log = logging.getLogger("peakcut.anim3d")


def available() -> bool:
    return worker.available()


def enabled_for(fmt: dict) -> bool:
    """3D animation is the default for every format; PEAKCUT_3D=0 or a format's render='stills' turns it off."""
    if os.environ.get("PEAKCUT_3D", "1").strip() == "0":
        return False
    return fmt.get("render", "anim3d") == "anim3d" and available()


def render_size(aspect: str) -> tuple[int, int]:
    """PEAKCUT_3D_HEIGHT renders smaller (e.g. 720) for speed on slow machines; the video is scaled up after."""
    full = (1920, 1080) if aspect == "16:9" else (1080, 1920)
    try:
        hgt = int(os.environ.get("PEAKCUT_3D_HEIGHT", "0") or 0)
    except ValueError:
        hgt = 0
    if not hgt:
        return full
    short = min(hgt, min(full))
    k = short / min(full)
    return int(full[0] * k) // 2 * 2, int(full[1] * k) // 2 * 2


def render_scene_clip(sc: dict, series: dict, fmt: dict, lang: str, spans: list, words: list, total: float,
                      idx: int, aspect: str, out_mp4: Path, seed_key: str = "", progress=None,
                      on_frame=None) -> dict | None:
    """Render one scene as 3D animation (silent). Returns the spec used, or None when it could not be made."""
    fps = int(os.environ.get("PEAKCUT_3D_FPS", "24") or 24)
    spec = director.build_spec(sc, series, fmt, lang, spans, words, total, idx, aspect, seed_key,
                               size=render_size(aspect), fps=fps)

    def tick(i, n, left):
        if on_frame:
            on_frame(i, n)
        if progress:
            progress(f"Scene {idx}: animating frame {i}/{n} (about {int(left // 60)}m {int(left % 60)}s left)")
    try:
        with worker.Browser() as b:
            ok = b.render(spec, out_mp4, progress=tick)
        return spec if ok else None
    except Exception as e:  # noqa: BLE001
        log.warning("3D render of scene %s failed: %s", idx, e)
        return None


def portrait(character: dict, fmt: dict, out_jpg: Path) -> bool:
    """A close-up picture of a character's 3D design, for the Character Vault card."""
    d = characters.design_for(character, fmt)
    spec = {"w": 1024, "h": 1024, "fps": 30, "duration": 1, "seed": 5, "fov": 30,
            "world": {"preset": "forest_green", "mood": "day"},
            "cast": [{"id": "c", "name": character.get("name", ""), "design": d, "x": 0, "z": 0, "yaw": 0}],
            "lines": [], "words": [], "actions": [], "emotions": [{"who": "c", "t0": 0, "t1": 5, "emo": "happy"}],
            "shots": [{"kind": "close", "t0": 0, "t1": 5, "target": "c"}]}
    try:
        with worker.Browser() as b:
            return b.snapshot(spec, 0.5, out_jpg)
    except Exception as e:  # noqa: BLE001
        log.warning("3D portrait failed: %s", e)
        return False
