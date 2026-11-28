"""Production engine: turns an approved script into finished video, for any format.

    script scene ──normalize_scene──> {lines: [who says what, in which voice], shots: [what the camera sees]}
                                   │
        lines ──tts.synthesize_lines──> scene voice track + word times + where each line starts/ends
        shots ──providers.generate_image──> still  ──providers.animate_image | ken_burns──> moving shot
                                   │
        render_scene: shots joined + format colour grade + captions + voice  ->  scene_XX_final.mp4
        (cached by content hash: re-rolling one scene re-renders only that scene)
                                   │
        build_episode: scenes stitched (format transition) -> soundtrack.mix_video (music, ambience, ducking,
        -14 LUFS) -> master.mp4  -> make_short (9:16 teaser)

Old scripts (one `speaker` + `dialogue` + `visual_prompt` per scene) are converted on the fly, and an edit of
those old fields in the script editor wins over the AI's `lines` / `shots`.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import subprocess
from pathlib import Path

from studio import anim3d, concat, formats, providers, render, sfx, soundtrack, templates, tts
from studio import progress as prog

log = logging.getLogger("peakcut.production")
NO_WINDOW = concat.NO_WINDOW
FPS = 30
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
ENGINE_VERSION = 4  # bump to invalidate every cached scene
# the most a finished 1080p video may use: keeps file sizes normal even with film grain in the grade
MAX_RATE = ["-maxrate", "8M", "-bufsize", "16M"]

MOVE_ALIASES = {"zoom_in": "dolly_in", "zoom_out": "dolly_out", "depth_zoom": "dolly_in", "orbit": "pan_right",
                "pan": "pan_right", "tilt": "tilt_up", "push_in": "dolly_in", "pull_out": "dolly_out",
                "zoom": "dolly_in", "none": "static", "hold": "static"}
MOVES = ["dolly_in", "dolly_out", "pan_left", "pan_right", "tilt_up", "tilt_down", "zoom_punch", "creep_in",
         "creep_out", "drift_left", "drift_right", "shake", "static"]
FRAMINGS = ["wide establishing shot", "medium shot", "close-up shot", "over-the-shoulder shot",
            "low angle dramatic shot", "detail insert shot"]


# ====================================================================== script -> lines + shots

def _char_index(series: dict) -> dict:
    return {c.get("name", "").strip().lower(): c for c in series.get("characters", []) if c.get("name")}


def _voice_for(speaker: str, chars: dict, fmt: dict, lang: str, fallback: str = "") -> dict:
    c = chars.get((speaker or "").strip().lower())
    if c and c.get("voice_id"):
        return {"voice_id": c["voice_id"], "rate": c.get("voice_rate", "+0%"), "pitch": c.get("voice_pitch", "+0Hz")}
    v = fmt["voice"]
    return {"voice_id": fallback or formats.narrator_voice(fmt, lang), "rate": v.get("rate", "+0%"),
            "pitch": v.get("pitch", "+0Hz")}


_LINE_RE = re.compile(r"^\s*([^\s:][^:\n]{0,40}?)\s*:\s*(.+)$")


def _split_dialogue(dialogue: str, speaker: str, chars: dict) -> list[tuple[str, str]]:
    """'Roo: Look!\\nBarnaby: Where?' -> [('Roo','Look!'), ('Barnaby','Where?')]. Plain text -> one line."""
    out = []
    for raw in (dialogue or "").splitlines():
        m = _LINE_RE.match(raw)
        if m and (m.group(1).strip().lower() in chars or m.group(1).strip().lower() == "narrator"):
            out.append((m.group(1).strip(), m.group(2).strip()))
        elif raw.strip():
            if out and not m:
                out[-1] = (out[-1][0], f"{out[-1][1]} {raw.strip()}")
            else:
                out.append((speaker or "Narrator", raw.strip()))
    return out or ([(speaker or "Narrator", dialogue.strip())] if (dialogue or "").strip() else [])


def normalize_scene(sc: dict, series: dict, fmt: dict, lang: str = "en") -> dict:
    chars = _char_index(series)
    sc = dict(sc)
    dialogue = (sc.get("dialogue") or "").strip()
    lines = [dict(x) for x in (sc.get("lines") or []) if (x.get("text") or "").strip()]
    joined = " ".join(x["text"].strip() for x in lines)
    # the old editor edits `dialogue`; when it no longer matches the AI's lines, the editor's text wins
    if not lines or (dialogue and re.sub(r"\W+", "", dialogue) != re.sub(r"\W+", "", joined)
                     and re.sub(r"\W+", "", dialogue) != re.sub(r"\W+", "", " ".join(f"{x.get('speaker','')}: {x['text']}" for x in lines))):
        lines = [{"speaker": spk, "text": txt} for spk, txt in _split_dialogue(dialogue, sc.get("speaker", ""), chars)]
        if lines and sc.get("voice_id") and len(lines) == 1:
            lines[0]["voice_id"] = sc["voice_id"]
    from studio import animals
    for ln in lines:
        ln["speaker"] = (ln.get("speaker") or "Narrator").strip()
        kind = animals.animal_kind(chars.get(ln["speaker"].lower()))
        if kind:
            ln["animal"] = kind          # its "भौं-भौं!" becomes a real bark (tts.synthesize_lines)
        v = _voice_for(ln["speaker"], chars, fmt, lang)
        if not ln.get("voice_id"):
            ln["voice_id"] = v["voice_id"]
        ln.setdefault("rate", v["rate"])
        ln.setdefault("pitch", v["pitch"])

    vp = (sc.get("visual_prompt") or "").strip()
    shots = [dict(x) for x in (sc.get("shots") or []) if (x.get("visual_prompt") or "").strip()]
    if not shots or (vp and vp != shots[0]["visual_prompt"].strip()):
        shots = [{"visual_prompt": vp or f"{sc.get('setting', '')}", "camera_motion": sc.get("camera_motion", "")}]
    for i, sh in enumerate(shots):
        mv = MOVE_ALIASES.get(str(sh.get("camera_motion", "")).lower(), str(sh.get("camera_motion", "")).lower())
        sh["camera_motion"] = mv if mv in MOVES else fmt["motion"]["moves"][i % len(fmt["motion"]["moves"])]
    sc["lines"], sc["shots"] = lines, shots
    in_scene = {x.lower() for x in (sc.get("characters") or [])} | {ln["speaker"].lower() for ln in lines}
    sc["cast"] = [chars[n] for n in in_scene if n in chars]
    return sc


def build_prompt(shot_prompt: str, fmt: dict, cast: list[dict], framing: str = "") -> str:
    """Shot description + who is in it (their fixed look) + the format's style DNA."""
    parts = [f"{framing}, {shot_prompt}" if framing else shot_prompt]
    low = shot_prompt.lower()
    looks = [f"{c['name']}: {c.get('visual_anchor', '')}" for c in cast
             if c.get("visual_anchor") and c["name"].lower() in low and c.get("visual_anchor", "")[:30].lower() not in low]
    if looks:
        parts.append("Characters (keep exactly this look): " + "; ".join(looks))
    style = fmt["visual"]["style"]
    if style[:40].lower() not in low:
        parts.append(style)
    return ". ".join(p.strip(" .") for p in parts if p)[:1400]


def plan_shots(sc: dict, fmt: dict, total: float, spans: list[tuple[float, float]]) -> list[dict]:
    """Decide how long each shot lasts. More shots are added (new framings of the same moment) when a long
    scene would otherwise sit on one picture; shot cuts follow line changes when there is one shot per line."""
    shots = [dict(s) for s in sc["shots"]]
    target = float(fmt["motion"].get("shot_sec", 5.0))
    want = max(len(shots), min(10, math.ceil(total / (target * 1.6))))
    base = list(shots)
    k = 0
    while len(shots) < want:
        src = base[k % len(base)]
        framing = FRAMINGS[(len(shots)) % len(FRAMINGS)]
        moves = fmt["motion"]["moves"]
        shots.append({"visual_prompt": src["visual_prompt"], "framing": framing,
                      "camera_motion": moves[len(shots) % len(moves)], "variant": len(shots),
                      "source": k % len(base)})
        k += 1
    n = len(shots)
    if len(spans) == n and n > 1:
        cuts = [0.0] + [spans[i][0] - 0.12 for i in range(1, n)] + [total]
    else:
        cuts = [total * i / n for i in range(n + 1)]
    for i, sh in enumerate(shots):
        sh["start"], sh["dur"] = round(cuts[i], 3), round(max(0.8, cuts[i + 1] - cuts[i]), 3)
    return shots


# ====================================================================== camera motion (local "kenburns")

def _motion_exprs(move: str, n: int) -> tuple[str, str, str]:
    P = f"(on/{max(1, n - 1)})"
    E = f"({P}*{P}*(3-2*{P}))"  # smoothstep easing
    cx, cy = "(iw-iw/zoom)/2", "(ih-ih/zoom)/2"
    rx, ry = "(iw-iw/zoom)", "(ih-ih/zoom)"
    table = {
        "dolly_in": (f"1+0.15*{E}", cx, cy),
        "dolly_out": (f"1.15-0.15*{E}", cx, cy),
        "pan_right": ("1.14", f"{rx}*{E}", cy),
        "pan_left": ("1.14", f"{rx}*(1-{E})", cy),
        "tilt_up": ("1.14", cx, f"{ry}*(1-{E})"),
        "tilt_down": ("1.14", cx, f"{ry}*{E}"),
        "zoom_punch": (f"1.04+0.14*(1-exp(-9*{P}))", cx, cy),
        "creep_in": (f"1.02+0.08*{P}", f"{cx}+{rx}*0.04*sin(on/40)", cy),
        "creep_out": (f"1.10-0.08*{P}", cx, cy),
        "drift_left": ("1.09", f"{rx}*(0.75-0.5*{P})", cy),
        "drift_right": ("1.09", f"{rx}*(0.25+0.5*{P})", cy),
        "shake": ("1.10", f"{cx}+9*sin(on*0.9)+5*sin(on*2.3)", f"{cy}+7*sin(on*1.3)+4*sin(on*3.1)"),
        "static": ("1.03", cx, cy),
    }
    return table.get(move, table["dolly_in"])


# where each extra framing looks inside the original picture: (left, top, width, height) as fractions
VIRTUAL_CROPS = {
    "wide establishing shot": (0.0, 0.0, 1.0, 1.0),
    "medium shot": (0.14, 0.08, 0.72, 0.72),
    "close-up shot": (0.26, 0.12, 0.5, 0.5),
    "over-the-shoulder shot": (0.0, 0.1, 0.7, 0.7),
    "low angle dramatic shot": (0.15, 0.3, 0.7, 0.7),
    "detail insert shot": (0.38, 0.38, 0.4, 0.4),
}


FALLBACK_IMAGES = ("procedural", "none")


def _previous_real_image(ep_dir: Path, idx: int) -> Path | None:
    """The last picture a real image service made in an earlier scene of this episode."""
    for j in range(idx - 1, 0, -1):
        for prov in sorted(ep_dir.glob(f"scene_{j:02d}_shot*.provider"), reverse=True):
            if prov.read_text(encoding="utf-8") not in FALLBACK_IMAGES and prov.with_suffix(".jpg").is_file():
                return prov.with_suffix(".jpg")
    return None


def virtual_framing(src: Path, out: Path, framing: str) -> bool:
    """A new camera angle cut out of a picture we already have: costs no image generation."""
    from PIL import Image
    x, y, fw, fh = VIRTUAL_CROPS.get(framing, VIRTUAL_CROPS["medium shot"])
    with Image.open(src) as im:
        W, H = im.size
        box = (int(x * W), int(y * H), int((x + fw) * W), int((y + fh) * H))
        im.crop(box).resize((W, H), Image.Resampling.LANCZOS).convert("RGB").save(out, "JPEG", quality=92)
    return out.is_file()


def ken_burns(image: Path, out_mp4: Path, duration: float, move: str, aspect_ratio: str) -> bool:
    w, h = providers.size_for(aspect_ratio)
    ss = float(providers._env("PEAKCUT_MOTION_SUPERSAMPLE", "2") or 2)
    sw, sh = int(w * ss) // 2 * 2, int(h * ss) // 2 * 2
    n = max(2, int(round(duration * FPS)))
    z, x, y = _motion_exprs(move, n)
    vf = (f"scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={w}x{h}:fps={FPS},format=yuv420p")
    cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}",
           "-i", str(image), "-vf", vf, "-frames:v", str(n), "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "18", str(out_mp4)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=600)
        if p.returncode != 0:
            log.warning("ken burns failed: %s", p.stderr[-300:])
        return p.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        log.warning("ken burns error: %s", e)
        return False


def _fit_clip(src: Path, out_mp4: Path, duration: float, aspect_ratio: str) -> bool:
    """An AI video clip of any length/size -> exactly `duration` seconds at the output size (last frame held)."""
    w, h = providers.size_for(aspect_ratio)
    vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},"
          f"tpad=stop_mode=clone:stop_duration={duration:.2f},format=yuv420p")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-t", f"{duration:.3f}", "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out_mp4)]
    p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=300)
    return p.returncode == 0 and out_mp4.is_file()


# ====================================================================== one scene

def _runtime_stamp() -> str:
    """Changes whenever the 3D runtime or the Director changes, so old 3D scenes are made again."""
    parts = [Path(anim3d.__file__).parent / "director.py", Path(anim3d.__file__).parent / "characters.py",
             Path(anim3d.__file__).parent / "story.py", anim3d.worker.RUNTIME_DIR / "runtime.js",
             anim3d.worker.RUNTIME_DIR / "story.js", anim3d.worker.RUNTIME_DIR / "parts.js",
             anim3d.worker.RUNTIME_DIR / "sets.js", Path(anim3d.__file__).parent / "sets.py"]
    h = hashlib.sha1()
    for p in parts:
        try:
            h.update(p.read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:12]


def _scene_hash(sc: dict, fmt: dict, aspect: str) -> str:
    keep = {"lines": sc["lines"], "shots": sc["shots"], "grade": fmt["grade"], "style": fmt["visual"]["style"],
            "cap": fmt["captions"], "aspect": aspect, "v": ENGINE_VERSION,
            "providers": [providers.image_chain(), providers.video_provider()]}
    if anim3d.enabled_for(fmt):   # a 3D scene changes when the cast's looks or the setting change
        keep["anim3d"] = {"setting": sc.get("setting", ""), "chars": sc.get("characters", []),
                          "cast": [anim3d.characters.design_for(c, fmt) for c in sc.get("cast", [])],
                          "runtime": _runtime_stamp()}
    return hashlib.sha1(json.dumps(keep, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _grade_for(fmt: dict, is3d: bool) -> str:
    """The format's colour grade. On 3D animation the film grain is a third as strong: clean 3D shapes with heavy
    moving grain look dirty, and the grain made every scene take minutes to save and hundreds of MB."""
    g = fmt.get("grade", "") or ""
    if not is3d:
        return g
    g = re.sub(r"noise=alls=(\d+)", lambda m: f"noise=alls={max(2, int(m.group(1)) // 3)}", g)
    return re.sub(r"colorbalance=([^,]+)", _tint_from_colorbalance, g)


def _tint_from_colorbalance(m) -> str:
    """colorbalance turns every pixel to RGB and back, which made it most of the finishing time. The same overall
    tint as a shift of the two colour channels (lutyuv) looks nearly the same and costs almost nothing."""
    vals = dict(kv.split("=", 1) for kv in m.group(1).split(":") if "=" in kv)
    f = lambda k: float(vals.get(k, 0) or 0)  # noqa: E731
    d = {c: 0.45 * f(c + "s") + 0.45 * f(c + "m") + 0.2 * f(c + "h") for c in "rgb"}
    du = round((-0.1687 * d["r"] - 0.3313 * d["g"] + 0.5 * d["b"]) * 224)
    dv = round((0.5 * d["r"] - 0.4187 * d["g"] - 0.0813 * d["b"]) * 224)
    if not du and not dv:
        return "null"
    return f"lutyuv=u='clip(val{du:+d},16,240)':v='clip(val{dv:+d},16,240)'"


def _caption_look(fmt: dict, aspect: str) -> tuple[dict, dict | None]:
    tid = fmt["captions"].get("template", "b-hormozi")
    look = next((t["look"] for t in templates.BUILTIN if t["id"] == tid), None) or templates.legacy()
    cap = dict(look.get("cap", look))
    size = int(cap.get("size", 110))
    cap["size"] = int(size * 0.66) if aspect == "16:9" else int(size * 0.9)
    return cap, look.get("hook")


def render_scene(sc: dict, idx: int, ep_dir: Path, series: dict, fmt: dict, lang: str, *, seed_key: str,
                 progress=None, captions: bool = True, stage=None) -> dict | None:
    """Render one normalised scene to ep_dir/scene_XX_final.mp4. Returns {"file", "duration", "words"}.
    progress(message) gets plain messages; stage(name, frac=, done=, total=, length=) gets the stage the scene is in
    (voice, animate, pictures, finish) for the progress panel (studio/progress.py)."""
    def at(name, frac=0.0, done=0, total=0, length=None):
        if stage:
            stage(name, frac=frac, done=done, total=total, length=length)

    aspect = fmt["aspect_ratio"]
    w, h = providers.size_for(aspect)
    tag = f"scene_{idx:02d}"
    final = ep_dir / f"{tag}_final.mp4"
    manifest = ep_dir / f"{tag}.json"
    digest = _scene_hash(sc, fmt, aspect)
    if final.is_file() and manifest.is_file():
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
            stand_ins = any(p in FALLBACK_IMAGES or p == "borrowed" for p in m.get("providers", []))
            can_do_better = any(n != "procedural" for n in providers.image_chain())
            if m.get("hash") == digest and not (stand_ins and can_do_better):
                return {"file": final, "duration": m["duration"], "words": m.get("words", []),
                        "spans": m.get("spans", []), "cached": True}
        except Exception:  # noqa: BLE001
            pass

    # 1. voices
    at("voice")
    audio = ep_dir / f"{tag}.mp3"
    words, spans = tts.synthesize_lines(sc["lines"], audio) if sc["lines"] else ([], [])
    voice_dur = concat._get_duration(audio) if audio.is_file() and sc["lines"] else 0.0
    if voice_dur <= 0:
        audio = None
        voice_dur = float(sc.get("duration_sec") or fmt["motion"]["shot_sec"])
    total = round(max(2.5, voice_dur + (1.4 if anim3d.enabled_for(fmt) else 0.7)), 3)

    # 2. real 3D animation (studio/anim3d): characters act the scene, the camera cuts between them
    clips, used, spec3d = [], [], {}
    if anim3d.enabled_for(fmt):
        if progress:
            progress(f"Scene {idx}: setting up the 3D scene")
        clip3d = ep_dir / f"{tag}_3d.mp4"
        at("animate", length=total)
        spec3d = anim3d.render_scene_clip(sc, series, fmt, lang, spans, words, total, idx, aspect, clip3d,
                                          seed_key=seed_key, progress=progress,
                                          on_frame=lambda i, n: at("animate", i / max(1, n), i, n, total)) or {}
        if spec3d:
            clips, used = [clip3d], ["anim3d"]
            (ep_dir / f"{tag}.scene.json").write_text(json.dumps(spec3d, ensure_ascii=False), encoding="utf-8")

    if not clips:   # no browser, or the 3D render failed: pictures + camera motion
        # 2. shots: picture -> movement
        shots = plan_shots(sc, fmt, total, spans)
        neg = fmt["visual"].get("negative", "")
        clips, used, prompts, seeds = [], [], [], []
        per_framing = providers._env("PEAKCUT_NEW_IMAGE_PER_FRAMING", "0") == "1"
        # 2a. pictures for the shots the script wrote (extra framings come from these)
        for si, sh in enumerate(shots):
            at("pictures", si / max(1, 2 * len(shots)), si + 1, len(shots), total)
            if progress:
                progress(f"Scene {idx}: picture {si + 1}/{len(shots)}")
            img = ep_dir / f"{tag}_shot{si:02d}.jpg"
            prompt = build_prompt(sh["visual_prompt"], fmt, sc["cast"], sh.get("framing", ""))
            seed = providers.stable_seed(seed_key, idx, si, sh["visual_prompt"][:80])
            prompts.append(prompt)
            seeds.append(seed)
            if "source" in sh and not per_framing:
                used.append("virtual")
                continue
            prompt_file, made_by = img.with_suffix(".prompt"), img.with_suffix(".provider")
            cached = (img.is_file() and prompt_file.is_file() and prompt_file.read_text(encoding="utf-8") == prompt
                      and made_by.is_file() and made_by.read_text(encoding="utf-8") not in FALLBACK_IMAGES)
            if cached:
                used.append(made_by.read_text(encoding="utf-8"))
                continue
            got = providers.generate_image(prompt, img, aspect, negative=neg, seed=seed) or "none"
            used.append(got)
            prompt_file.write_text(prompt, encoding="utf-8")
            made_by.write_text(got, encoding="utf-8")
        # 2b. a shot whose picture only came from the local painter borrows a real picture of this scene (or the
        #     scene before) through the virtual camera: a sunny drawn farm in the middle of a horror film is worse
        real = [si for si, u in enumerate(used) if u not in FALLBACK_IMAGES and u != "virtual"]
        for si, sh in enumerate(shots):
            img = ep_dir / f"{tag}_shot{si:02d}.jpg"
            if used[si] == "virtual":
                base = sh.get("source", 0)
                donor = base if base in real else (real[0] if real else None)
                src = ep_dir / f"{tag}_shot{donor:02d}.jpg" if donor is not None else ep_dir / f"{tag}_shot{base:02d}.jpg"
                if not src.is_file() or (donor is None and used[base] in FALLBACK_IMAGES):
                    src = _previous_real_image(ep_dir, idx) or src
                if src.is_file():
                    virtual_framing(src, img, sh.get("framing", ""))
            elif used[si] in FALLBACK_IMAGES:
                donor = ep_dir / f"{tag}_shot{real[si % len(real)]:02d}.jpg" if real else _previous_real_image(ep_dir, idx)
                if donor and donor.is_file():
                    virtual_framing(donor, img, FRAMINGS[(si + 1) % len(FRAMINGS)])
                    used[si] = "borrowed"
        # 2c. movement
        for si, sh in enumerate(shots):
            at("pictures", 0.5 + si / max(1, 2 * len(shots)), si + 1, len(shots), total)
            if progress:
                progress(f"Scene {idx}: shot {si + 1}/{len(shots)}")
            img = ep_dir / f"{tag}_shot{si:02d}.jpg"
            prompt, seed = prompts[si], seeds[si]
            clip = ep_dir / f"{tag}_shot{si:02d}.mp4"
            raw = ep_dir / f"{tag}_shot{si:02d}_ai.mp4"
            ok = img.is_file() and providers.animate_image(img, prompt, raw, sh["dur"], aspect, negative=neg, seed=seed) \
                and _fit_clip(raw, clip, sh["dur"], aspect)
            if not ok:
                fmt_id = fmt.get("id", "")
                is_cartoon = fmt_id in ("chhota_bheem", "cartoon_2d", "kids_3d") or any(k in fmt.get("visual", {}).get("style", "").lower() for k in ["bheem", "cartoon", "cocomelon", "2d", "dholakpur"])
                if is_cartoon:
                    try:
                        from studio import visuals
                        cast_list = sc.get("cast") or series.get("characters") or []
                        spk = sc["lines"][0].get("speaker", "Bheem") if sc.get("lines") else "Bheem"
                        ok = visuals.render_3d_animated_scene(
                            characters=cast_list,
                            speaker_name=spk,
                            setting=sh.get("visual_prompt", "Dholakpur Indian Village"),
                            visual_style=fmt["visual"]["style"],
                            audio_path=audio,
                            out_mp4=clip,
                            duration=sh["dur"],
                            motion=sh["camera_motion"],
                            aspect_ratio=aspect
                        )
                    except Exception as ce:
                        log.warning("Animated cartoon scene render: %s", ce)
                        ok = False
                if not ok and img.is_file():
                    ok = ken_burns(img, clip, sh["dur"], sh["camera_motion"], aspect)
            if ok:
                clips.append(clip)
    if not clips:
        log.error("scene %s: no shot could be rendered", idx)
        return None

    # 3. captions
    ass_name = ""
    if captions and words:
        cap, hook_look = _caption_look(fmt, aspect)
        script = "hi" if lang == "hi" and any("ऀ" <= ch <= "ॿ" for ch in "".join(x["w"] for x in words)) else ""
        cap_y = int(h * float(fmt["captions"].get("position", 0.89)))
        try:
            ass = render.build_ass(words, 0.0, total, "", cap, [], 0, cap_y, show_hook=False, hook_look=hook_look,
                                   script=script, play_res=(w, h))
            ass_name = f"{tag}.ass"
            (ep_dir / ass_name).write_text(ass, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            log.warning("captions for scene %s failed: %s", idx, e)

    # 4. one pass: join shots + grade + captions + voice
    at("finish", length=total)
    if progress:
        progress(f"Scene {idx}: adding grade, captions and voice")
    is3d = used == ["anim3d"]
    out_fps = int(spec3d.get("fps") or FPS) if is3d else FPS   # 3D keeps its own frame rate (no copied frames)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for c in clips:
        cmd += ["-i", c.name]
    if audio:
        cmd += ["-i", audio.name]
    else:
        cmd += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=mono"]
    chain = "".join(f"[{i}:v]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[vc];[vc]scale={w}:{h}:flags=lanczos:out_range=tv,"
    post = [f for f in [_grade_for(fmt, is3d), "format=yuv420p"] if f]
    if ass_name:
        fdir = str(FONTS_DIR).replace("\\", "/").replace(":", "\\:")
        post.insert(len(post) - 1, f"ass={ass_name}:fontsdir='{fdir}'")
    chain += ",".join(post) + "[v]"
    chain += f";[{len(clips)}:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={total:.3f}[a]"
    cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", "-r", str(out_fps),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", *MAX_RATE, "-pix_fmt", "yuv420p",
            "-color_range", "tv", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(final.name)]
    fin = lambda f: at("finish", f, length=total)  # noqa: E731
    p = prog.ffmpeg(cmd, total, fin, cwd=ep_dir, timeout=900)
    if p.returncode != 0 and ass_name:  # a font or caption problem never loses the scene
        log.warning("scene %s with captions failed (%s); trying without", idx, p.stderr[-300:])
        cmd = [c.replace(f",ass={ass_name}:fontsdir='{fdir}'", "") if isinstance(c, str) else c for c in cmd]
        p = prog.ffmpeg(cmd, total, fin, cwd=ep_dir, timeout=900)
    if p.returncode != 0 or not final.is_file():
        log.error("scene %s render failed: %s", idx, p.stderr[-500:])
        return None
    dur = concat._get_duration(final) or total
    manifest.write_text(json.dumps({"hash": digest, "duration": dur, "words": words, "spans": [list(x) for x in spans],
                                    "shots": len(clips),
                                    "providers": used}, ensure_ascii=False), encoding="utf-8")
    for c in clips:
        c.unlink(missing_ok=True)
    return {"file": final, "duration": dur, "words": words, "spans": [list(x) for x in spans], "cached": False}


# ====================================================================== the whole episode

def make_short(master: Path, out_mp4: Path, start: float = 0.0, max_dur: float = 58.0, source_aspect: str = "16:9",
               title: str = "", on_frac=None, captions: dict | None = None) -> bool:
    """A 9:16 teaser. From a 16:9 master: the picture in the middle over a blurred fill, the title on top.

    captions = {"words": episode word times, "look": caption settings, "hook": heading look, "script": "hi" or "",
    "pos": where the master's captions sit (0..1 of the height)}. With them, the master's own small captions are
    cut off the picture and the captions are drawn again, big, in the space under the picture: inside the picture
    they were tiny and half lost in the blurred fill."""
    total = concat._get_duration(master)
    if total <= 1:
        return False
    start = max(0.0, min(start, max(0.0, total - 5)))
    dur = min(max_dur, total - start)
    ass_name, fdir = "", ""
    if source_aspect == "9:16":
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        cut = 1.0
        if captions and captions.get("words"):
            # keep the picture above the master's captions (they sit around `pos`, up to two lines high)
            cut = max(0.6, min(1.0, float(captions.get("pos", 0.89)) - 0.13))
            fg_h = round(1080 * 9 / 16 * cut)
            fg_bottom = (1920 + fg_h) // 2
            cap_y = min(1700, fg_bottom + 150)
            try:
                ass = render.build_ass(captions["words"], start, start + dur, "", dict(captions["look"]), [], 0, cap_y,
                                       show_hook=False, hook_look=captions.get("hook"),
                                       script=captions.get("script", ""), play_res=(1080, 1920))
                ass_name = out_mp4.stem + "_captions.ass"
                (out_mp4.parent / ass_name).write_text(ass, encoding="utf-8")
                fdir = str(FONTS_DIR).replace("\\", "/").replace(":", "\\:")
            except Exception as e:  # noqa: BLE001
                log.warning("short captions failed: %s", e)
                ass_name, cut = "", 1.0
        top = f"crop=iw:ih*{cut:.3f}:0:0," if cut < 1.0 else ""
        vf = (f"{top}split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "gblur=sigma=28,eq=brightness=-0.12[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
        if ass_name:
            vf += f",ass={ass_name}:fontsdir='{fdir}'"
        hindi = any("ऀ" <= ch <= "ॿ" for ch in title)
        font = FONTS_DIR / ("NotoSansDevanagari-Bold.ttf" if hindi else "Anton-Regular.ttf")
        if title and font.is_file():
            tf = out_mp4.with_suffix(".title.txt")
            tf.write_text(title.strip()[:60], encoding="utf-8")
            fpath = str(font).replace("\\", "/").replace(":", "\\:")
            tpath = str(tf).replace("\\", "/").replace(":", "\\:")
            vf += (f",drawtext=fontfile='{fpath}':textfile='{tpath}':fontsize=74:fontcolor=white:"
                   f"borderw=5:bordercolor=black:x=(w-text_w)/2:y=h*0.17")

    def run(filters):
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(master),
               "-filter_complex", f"[0:v]{filters}[v]", "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset",
               "fast", "-crf", "21", *MAX_RATE, "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags",
               "+faststart", out_mp4.name]
        return prog.ffmpeg(cmd, dur, on_frac, cwd=out_mp4.parent, timeout=600)
    p = run(vf)
    if p.returncode != 0 and ass_name:   # a caption problem never loses the short: the plain version instead
        log.warning("short with captions failed (%s); making it without", p.stderr[-300:])
        plain = vf.replace(f",ass={ass_name}:fontsdir='{fdir}'", "")
        plain = plain.split("split[a][b]", 1)
        p = run("split[a][b]" + plain[1])
    if p.returncode != 0:
        log.warning("short failed: %s", p.stderr[-300:])
    out_mp4.with_suffix(".title.txt").unlink(missing_ok=True)
    if ass_name:
        (out_mp4.parent / ass_name).unlink(missing_ok=True)
    return p.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000


def _episode_sound(made: list, offsets: list, fmt: dict, script: dict, seed: int, ep_dir: Path, total: float,
                   score_f: Path, fx_f: Path, amb_f: Path | None = None) -> dict:
    """The theme music (a mood per scene, cross-faded, series tune, dips before scares) and the sound effects
    (footsteps, jumps, things named in the dialogue, stingers) for the whole episode, as two WAV files."""
    import soundfile
    theme = soundtrack.theme_for(fmt, str(script.get("music_mood") or ""))
    segments, events, dips, moods, beds = [], [], [], [], []
    fallback = str((fmt.get("sound") or {}).get("ambience") or "")
    for k, ((idx, sc, res), off) in enumerate(zip(made, offsets)):
        mood, level = soundtrack.scene_mood(sc.get("lines") or [], theme, str(sc.get("music") or ""))
        end = offsets[k + 1] if k + 1 < len(offsets) else total
        segments.append((off, end, mood, level))
        moods.append(mood)
        spec_f = ep_dir / f"scene_{idx:02d}.scene.json"
        try:
            spec = json.loads(spec_f.read_text(encoding="utf-8")) if spec_f.is_file() else None
        except Exception:  # noqa: BLE001
            spec = None
        beds.append((off, end, sfx.scene_beds((spec or {}).get("world"), fallback)))
        for t, name, g in sfx.plan_scene(spec, res.get("words") or [], sc.get("lines") or [], res.get("spans") or [],
                                         theme, res["duration"], last_scene=k == len(made) - 1):
            events.append((off + t, name, g))
            if name == theme.get("stings", {}).get("surprise") and theme.get("dip"):
                dips.append(off + t)
    score = soundtrack.build_score(segments, total, seed, theme, dips=dips)
    if score is not None:
        soundfile.write(str(score_f), score, soundtrack.SR, subtype="PCM_16")
    if events:
        soundfile.write(str(fx_f), sfx.render_track(events, total), sfx.SR, subtype="PCM_16")
    if amb_f is not None:
        bed = soundtrack.build_ambience(beds, total, seed)
        if bed is not None:
            soundfile.write(str(amb_f), bed, soundtrack.SR, subtype="PCM_16")
    names = sorted({n for _t, n, _g in events if not n.startswith("step_")})
    return {"theme": theme["name"], "moods": moods, "effects": len(events), "effect_names": names,
            "ambience": [[k for k, _l, _m in b] for _s, _e, b in beds]}


def _remember_places(scenes: list, series: dict, fmt: dict) -> dict:
    """Every place the episode uses goes into the series' Location Vault (once), so it looks the same every time
    the story comes back to it, and the user can see and fix it. Returns the series as saved."""
    from studio import memory
    from studio.anim3d import sets as _sets
    sid = series.get("id")
    if not sid or not memory.get_series(sid):
        return series
    import hashlib as _h
    for sc in scenes:
        st = sc.get("set") if isinstance(sc.get("set"), dict) else {}
        name = str(st.get("location_name") or sc.get("setting") or "").strip()
        if not name:
            continue
        w = _sets.scene_set(sc, fmt, series, 1)
        memory.register_location(sid, {"name": name, "kit": w["preset"], "era": w.get("era", ""), "culture": w.get("culture", ""),
                                       "seed": w.get("seed") or int(_h.md5(name.lower().encode("utf-8")).hexdigest()[:8], 16),
                                       "landmarks": w.get("landmarks", [])})
    return memory.get_series(sid) or series


def _episode_cast_on_screen(scenes: list, script: dict, series: dict) -> None:
    """A scene only the narrator speaks shows this episode's characters (the cast chosen for it, else the ones who
    talk most in it), not always the first two of the Vault."""
    vault = {c.get("name", "").strip().lower(): c for c in series.get("characters", []) if c.get("name")}
    cast = [n for n in (script.get("cast") or []) if str(n).strip().lower() in vault]
    if not cast:
        count: dict = {}
        for sc in scenes:
            for ln in sc.get("lines", []):
                n = ln.get("speaker", "").strip()
                if n.lower() in vault:
                    count[n] = count.get(n, 0) + 1
        cast = [n for n, _ in sorted(count.items(), key=lambda kv: -kv[1])]
    if not cast:
        return
    for sc in scenes:
        talkers = [ln for ln in sc.get("lines", []) if ln.get("speaker", "").strip().lower() in vault]
        if not talkers and not sc.get("characters"):
            sc["characters"] = cast[:3]


def build_episode(series: dict, ep_num: int, script: dict, ep_dir: Path, progress=None, on_status=None,
                  started_at: float | None = None) -> dict:
    """Render every scene, stitch, score and cut the short.
    progress(pct, message) gets a percentage and a line of text; on_status(status) gets the full status from
    studio/progress.py (every scene's stage, time taken, time left) for the progress panel."""
    fmt = formats.resolve(series)
    lang = (series.get("default_language") or "en").lower()
    aspect = fmt["aspect_ratio"]
    ep_dir.mkdir(parents=True, exist_ok=True)
    scenes = [normalize_scene(s, series, fmt, lang) for s in script.get("scenes", [])]
    _episode_cast_on_screen(scenes, script, series)
    series = _remember_places(scenes, series, fmt)

    def changed(st):
        if on_status:
            on_status(st)
        if progress:
            progress(st["progress"], st["message"])
    tr = prog.Tracker(scenes, ep_dir, changed, started_at=started_at,
                      kind="anim3d" if anim3d.enabled_for(fmt) else "pictures",
                      ep_num=ep_num, title=str(script.get("title") or ""))
    tr.push(force=True)

    rendered, starts, t = [], [], 0.0
    scene_words = []   # (words, duration) per made scene, for the short's captions
    made = []          # (scene index, scene, result) per made scene, for the music and the sound effects
    for i, sc in enumerate(scenes):
        idx = i + 1
        try:
            res = render_scene(sc, idx, ep_dir, series, fmt, lang, seed_key=f"{series.get('id')}:{ep_num}",
                               stage=lambda name, i=idx, **k: tr.scene(i, name, **k))
        except tts.VoiceServiceError as e:
            # no internet for the voices: every next scene would fail too. Stop; Resume carries on later and
            # keeps the scenes already made.
            log.warning("voice service unreachable at scene %s: %s", idx, e)
            msg = ("Could not reach Microsoft's voice service (check the internet connection). "
                   "Press Resume to carry on: the finished scenes are kept.")
            tr.scene(idx, "failed", error=msg)
            tr.end(False)
            return {"ok": False, "error": msg, "progress": tr.status(), "can_resume": True}
        except Exception as e:  # noqa: BLE001
            log.exception("scene %s failed", idx)
            res = None
            tr.scene(idx, "failed", error=str(e))
        if res:
            tr.scene(idx, "cached" if res.get("cached") else "done", 1.0, length=res["duration"])
            starts.append(t)
            t += res["duration"]
            rendered.append(res["file"])
            scene_words.append((res.get("words") or [], res["duration"]))
            made.append((idx, sc, res))
        elif tr.scenes[i]["stage"] != "failed":
            tr.scene(idx, "failed", error="This scene could not be made")

    if not rendered:
        tr.end(False)
        return {"ok": False, "error": "No scene could be rendered", "progress": tr.status()}

    tr.step("stitch", "running")
    trans = fmt["motion"].get("transition", "fade")
    stitched = ep_dir / f"episode_{ep_num:03d}_voice.mp4"
    ok = concat.stitch_scenes(rendered, stitched, transition="none" if trans == "cut" else trans, transition_dur=0.5,
                              on_frac=lambda f: tr.step("stitch", "running", f))
    tr.step("stitch", "done" if ok else "failed")
    master = ep_dir / f"episode_{ep_num:03d}_master.mp4"
    # where each scene sits in the joined video (scenes overlap by the fade when they are joined with one)
    overlap = 0.0 if (len(rendered) >= 5 or trans == "cut" or len(rendered) == 1) else 0.5
    offsets, off = [], 0.0
    for _i, _sc, r in made:
        offsets.append(off)
        off += r["duration"] - overlap
    sound = {}
    if ok:
        tr.step("music", "running")
        snd = fmt["sound"]
        mood = script.get("music_mood") or snd.get("music", "calm")
        seed = providers.stable_seed(series.get("id", ""))
        score_f, fx_f = ep_dir / f"episode_{ep_num:03d}_score.wav", ep_dir / f"episode_{ep_num:03d}_sfx.wav"
        amb_f = ep_dir / f"episode_{ep_num:03d}_ambience.wav"
        try:
            sound = _episode_sound(made, offsets, fmt, script, seed, ep_dir, concat._get_duration(stitched),
                                   score_f, fx_f, amb_f)
        except Exception as e:  # noqa: BLE001  (the episode still gets the plain music loop)
            log.warning("theme music / sound effects failed: %s", e)
        tr.step("music", "running", 0.05)
        if not soundtrack.mix_video(stitched, master, mood=mood, ambience=snd.get("ambience", ""),
                                    music_db=float(snd.get("music_db", -12)), seed=seed,
                                    on_frac=lambda f: tr.step("music", "running", f),
                                    music_file=score_f if score_f.is_file() else None,
                                    sfx_file=fx_f if fx_f.is_file() else None,
                                    ambience_file=amb_f if amb_f.is_file() else None,
                                    ambience_db=-15 if amb_f.is_file() else -30):
            stitched.replace(master)
            tr.step("music", "skipped")
        else:
            stitched.unlink(missing_ok=True)
            tr.step("music", "done")
        score_f.unlink(missing_ok=True)
        fx_f.unlink(missing_ok=True)
        amb_f.unlink(missing_ok=True)
    else:
        tr.step("music", "skipped")

    short = ep_dir / f"episode_{ep_num:03d}_short.mp4"
    if ok and master.is_file():
        tr.step("short", "running")
        pick = next((i for i, s in enumerate(scenes) if s.get("teaser")), 0)
        start = starts[pick] if pick < len(starts) else 0.0
        # the words at their time in the master
        all_words, off = [], 0.0
        for ws, d in scene_words:
            all_words += [dict(w, s=w["s"] + off, e=w["e"] + off) for w in ws]
            off += d - overlap
        cap_look, hook_look = _caption_look(fmt, "9:16")
        hi = lang == "hi" and any("ऀ" <= ch <= "ॿ" for ch in "".join(w["w"] for w in all_words))
        made = make_short(master, short, start=start, source_aspect=aspect, title=script.get("title", ""),
                          on_frac=lambda f: tr.step("short", "running", f),
                          captions={"words": all_words, "look": cap_look, "hook": hook_look, "script": "hi" if hi else "",
                                    "pos": float(fmt["captions"].get("position", 0.89))} if all_words else None)
        tr.step("short", "done" if made else "failed")
    else:
        tr.step("short", "skipped")

    done_ok = ok and master.is_file()
    tr.end(done_ok)
    return {"ok": done_ok, "master": master if master.is_file() else None,
            "short": short if short.is_file() else None,
            "duration": concat._get_duration(master) if master.is_file() else 0,
            "scenes": scenes, "format": fmt["id"], "progress": tr.status(), "sound": sound}
