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

from studio import concat, formats, providers, render, soundtrack, templates, tts

log = logging.getLogger("peakcut.production")
NO_WINDOW = concat.NO_WINDOW
FPS = 30
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
ENGINE_VERSION = 1  # bump to invalidate every cached scene

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
    for ln in lines:
        ln["speaker"] = (ln.get("speaker") or "Narrator").strip()
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

def _scene_hash(sc: dict, fmt: dict, aspect: str) -> str:
    keep = {"lines": sc["lines"], "shots": sc["shots"], "grade": fmt["grade"], "style": fmt["visual"]["style"],
            "cap": fmt["captions"], "aspect": aspect, "v": ENGINE_VERSION,
            "providers": [providers.image_chain(), providers.video_provider()]}
    return hashlib.sha1(json.dumps(keep, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _caption_look(fmt: dict, aspect: str) -> tuple[dict, dict | None]:
    tid = fmt["captions"].get("template", "b-hormozi")
    look = next((t["look"] for t in templates.BUILTIN if t["id"] == tid), None) or templates.legacy()
    cap = dict(look.get("cap", look))
    size = int(cap.get("size", 110))
    cap["size"] = int(size * 0.66) if aspect == "16:9" else int(size * 0.9)
    return cap, look.get("hook")


def render_scene(sc: dict, idx: int, ep_dir: Path, series: dict, fmt: dict, lang: str, *, seed_key: str,
                 progress=None, captions: bool = True) -> dict | None:
    """Render one normalised scene to ep_dir/scene_XX_final.mp4. Returns {"file", "duration", "words"}."""
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
                return {"file": final, "duration": m["duration"], "words": m.get("words", []), "cached": True}
        except Exception:  # noqa: BLE001
            pass

    # 1. voices
    audio = ep_dir / f"{tag}.mp3"
    words, spans = tts.synthesize_lines(sc["lines"], audio) if sc["lines"] else ([], [])
    voice_dur = concat._get_duration(audio) if audio.is_file() and sc["lines"] else 0.0
    if voice_dur <= 0:
        audio = None
        voice_dur = float(sc.get("duration_sec") or fmt["motion"]["shot_sec"])
    total = round(max(2.5, voice_dur + 0.7), 3)

    # 2. shots: picture -> movement
    shots = plan_shots(sc, fmt, total, spans)
    neg = fmt["visual"].get("negative", "")
    clips, used, prompts, seeds = [], [], [], []
    per_framing = providers._env("PEAKCUT_NEW_IMAGE_PER_FRAMING", "0") == "1"
    # 2a. pictures for the shots the script wrote (extra framings come from these)
    for si, sh in enumerate(shots):
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
        if progress:
            progress(f"Scene {idx}: shot {si + 1}/{len(shots)}")
        img = ep_dir / f"{tag}_shot{si:02d}.jpg"
        prompt, seed = prompts[si], seeds[si]
        clip = ep_dir / f"{tag}_shot{si:02d}.mp4"
        raw = ep_dir / f"{tag}_shot{si:02d}_ai.mp4"
        ok = img.is_file() and providers.animate_image(img, prompt, raw, sh["dur"], aspect, negative=neg, seed=seed) \
            and _fit_clip(raw, clip, sh["dur"], aspect)
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
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for c in clips:
        cmd += ["-i", c.name]
    if audio:
        cmd += ["-i", audio.name]
    else:
        cmd += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=mono"]
    chain = "".join(f"[{i}:v]" for i in range(len(clips))) + f"concat=n={len(clips)}:v=1:a=0[vc];[vc]"
    post = [f for f in [fmt.get("grade", ""), "format=yuv420p"] if f]
    if ass_name:
        fdir = str(FONTS_DIR).replace("\\", "/").replace(":", "\\:")
        post.insert(len(post) - 1, f"ass={ass_name}:fontsdir='{fdir}'")
    chain += ",".join(post) + "[v]"
    chain += f";[{len(clips)}:a]aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={total:.3f}[a]"
    cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}", "-r", str(FPS),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(final.name)]
    p = subprocess.run(cmd, cwd=ep_dir, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=900)
    if p.returncode != 0 and ass_name:  # a font or caption problem never loses the scene
        log.warning("scene %s with captions failed (%s); trying without", idx, p.stderr[-300:])
        cmd = [c.replace(f",ass={ass_name}:fontsdir='{fdir}'", "") if isinstance(c, str) else c for c in cmd]
        p = subprocess.run(cmd, cwd=ep_dir, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=900)
    if p.returncode != 0 or not final.is_file():
        log.error("scene %s render failed: %s", idx, p.stderr[-500:])
        return None
    dur = concat._get_duration(final) or total
    manifest.write_text(json.dumps({"hash": digest, "duration": dur, "words": words, "shots": len(clips),
                                    "providers": used}, ensure_ascii=False), encoding="utf-8")
    for c in clips:
        c.unlink(missing_ok=True)
    return {"file": final, "duration": dur, "words": words, "cached": False}


# ====================================================================== the whole episode

def make_short(master: Path, out_mp4: Path, start: float = 0.0, max_dur: float = 58.0, source_aspect: str = "16:9",
               title: str = "") -> bool:
    """A 9:16 teaser. From a 16:9 master: the full frame (captions included) over a blurred fill, title on top."""
    total = concat._get_duration(master)
    if total <= 1:
        return False
    start = max(0.0, min(start, max(0.0, total - 5)))
    dur = min(max_dur, total - start)
    if source_aspect == "9:16":
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        vf = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
              "gblur=sigma=28,eq=brightness=-0.12[bg];[b]scale=1080:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
        hindi = any("ऀ" <= ch <= "ॿ" for ch in title)
        font = FONTS_DIR / ("NotoSansDevanagari-Bold.ttf" if hindi else "Anton-Regular.ttf")
        if title and font.is_file():
            tf = out_mp4.with_suffix(".title.txt")
            tf.write_text(title.strip()[:60], encoding="utf-8")
            fpath = str(font).replace("\\", "/").replace(":", "\\:")
            tpath = str(tf).replace("\\", "/").replace(":", "\\:")
            vf += (f",drawtext=fontfile='{fpath}':textfile='{tpath}':fontsize=74:fontcolor=white:"
                   f"borderw=5:bordercolor=black:x=(w-text_w)/2:y=h*0.17")
    cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{start:.2f}", "-t", f"{dur:.2f}", "-i", str(master),
           "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "fast",
           "-crf", "21", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_mp4)]
    p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=600)
    if p.returncode != 0:
        log.warning("short failed: %s", p.stderr[-300:])
    out_mp4.with_suffix(".title.txt").unlink(missing_ok=True)
    return p.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000


def build_episode(series: dict, ep_num: int, script: dict, ep_dir: Path, progress=None) -> dict:
    """Render every scene, stitch, score and cut the short. progress(pct, message) is called along the way."""
    fmt = formats.resolve(series)
    lang = (series.get("default_language") or "en").lower()
    aspect = fmt["aspect_ratio"]
    ep_dir.mkdir(parents=True, exist_ok=True)
    scenes = [normalize_scene(s, series, fmt, lang) for s in script.get("scenes", [])]
    report = lambda pct, msg: progress and progress(pct, msg)  # noqa: E731

    rendered, starts, t = [], [], 0.0
    for i, sc in enumerate(scenes):
        idx = i + 1
        base = 8 + int(78 * i / max(1, len(scenes)))
        report(base, f"Scene {idx}/{len(scenes)}: {str(sc.get('setting', ''))[:40]}")
        res = render_scene(sc, idx, ep_dir, series, fmt, lang, seed_key=f"{series.get('id')}:{ep_num}",
                           progress=lambda m, b=base: report(b, m))
        if res:
            starts.append(t)
            t += res["duration"]
            rendered.append(res["file"])

    if not rendered:
        return {"ok": False, "error": "No scene could be rendered"}

    report(88, "Stitching scenes")
    trans = fmt["motion"].get("transition", "fade")
    stitched = ep_dir / f"episode_{ep_num:03d}_voice.mp4"
    ok = concat.stitch_scenes(rendered, stitched, transition="none" if trans == "cut" else trans, transition_dur=0.5)
    master = ep_dir / f"episode_{ep_num:03d}_master.mp4"
    if ok:
        report(93, "Adding music and ambience")
        snd = fmt["sound"]
        mood = script.get("music_mood") or snd.get("music", "calm")
        if not soundtrack.mix_video(stitched, master, mood=mood, ambience=snd.get("ambience", ""),
                                    music_db=float(snd.get("music_db", -20)),
                                    seed=providers.stable_seed(series.get("id", ""))):
            stitched.replace(master)
        else:
            stitched.unlink(missing_ok=True)

    short = ep_dir / f"episode_{ep_num:03d}_short.mp4"
    if ok and master.is_file():
        report(97, "Cutting the vertical short")
        pick = next((i for i, s in enumerate(scenes) if s.get("teaser")), 0)
        start = starts[pick] if pick < len(starts) else 0.0
        make_short(master, short, start=start, source_aspect=aspect, title=script.get("title", ""))

    return {"ok": ok and master.is_file(), "master": master if master.is_file() else None,
            "short": short if short.is_file() else None, "duration": concat._get_duration(master) if master.is_file() else 0,
            "scenes": scenes, "format": fmt["id"]}
