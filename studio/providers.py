"""Generation providers: where images and moving shots come from.

Every shot of a generated video needs a picture (and, with a video model, real motion). Providers are tried in
order until one works, so a free setup, a local GPU and a paid API all use the same pipeline:

    Image providers (PEAKCUT_IMAGE_PROVIDERS, comma separated, tried in order; default "pollinations,procedural")
        pollinations   free cloud text-to-image. Free tier: 1 picture / ~45 s per internet address (calls are
                       spaced and "retry after" is honoured); PEAKCUT_POLLINATIONS_KEY lifts the limit. Seeded.
        openai_images  any OpenAI-compatible /v1/images/generations endpoint (OpenAI gpt-image-1, Together, ...)
                       PEAKCUT_IMAGE_API_URL, PEAKCUT_IMAGE_API_KEY, PEAKCUT_IMAGE_MODEL
        comfyui        your own ComfyUI (local GPU: SDXL, Flux, ...). PEAKCUT_COMFYUI_URL and
                       PEAKCUT_COMFY_IMAGE_WORKFLOW (an API-format workflow JSON with {{prompt}} {{negative}}
                       {{width}} {{height}} {{seed}} placeholders)
        procedural     drawn locally, always works, never leaves the machine (the last resort)

    Video providers (PEAKCUT_VIDEO_PROVIDER; default "kenburns")
        kenburns       camera motion over the still, rendered by FFmpeg (production.py). Free, fast, local.
        comfyui        image-to-video through ComfyUI (Wan 2.x, CogVideoX, SVD, AnimateDiff...).
                       PEAKCUT_COMFY_VIDEO_WORKFLOW with {{image}} {{prompt}} {{negative}} {{frames}} {{fps}}
                       {{width}} {{height}} {{seed}} placeholders. A shot that fails falls back to kenburns.

Adding a service = one function with the same signature registered in IMAGE_PROVIDERS / VIDEO_PROVIDERS.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import random
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

log = logging.getLogger("peakcut.providers")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PeakCut-Studio"


def _env(name: str, default: str = "") -> str:
    from studio import config  # noqa: F401  (loads .env into os.environ)
    return (os.environ.get(name) or default).strip()


def size_for(aspect_ratio: str) -> tuple[int, int]:
    return {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1024, 1024)}.get(aspect_ratio, (1920, 1080))


def stable_seed(*parts) -> int:
    """The same inputs give the same seed: a character's portrait and shots stay consistent between runs."""
    h = hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(h[:8], 16) % 2_000_000_000


def _cover_save(data: bytes, out_path: Path, w: int, h: int) -> bool:
    """Scale-and-crop to fill w x h exactly (never stretch a square image into 16:9)."""
    im = Image.open(io.BytesIO(data)).convert("RGB")
    scale = max(w / im.width, h / im.height)
    nw, nh = max(w, int(im.width * scale + 0.5)), max(h, int(im.height * scale + 0.5))
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    im = im.crop((left, top, left + w, top + h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, "JPEG", quality=92)
    return out_path.is_file() and out_path.stat().st_size > 5000


def _get(url: str, timeout: float = 60, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _post_json(url: str, body: dict, timeout: float = 120, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"User-Agent": UA, "Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


# ====================================================================== image providers
# signature: (prompt, negative, out_path, width, height, seed) -> bool

_poll_lock = threading.Lock()
_poll_last = [0.0]


def _img_pollinations(prompt, negative, out_path, w, h, seed) -> bool:
    """Free tier: one picture every ~45 s per internet address (the service answers 402 FREE_LIMIT otherwise),
    so calls are spaced out and a 'retry after N s' is honoured. PEAKCUT_POLLINATIONS_KEY lifts the limit."""
    key = _env("PEAKCUT_POLLINATIONS_KEY")
    gap = 0.0 if key else float(_env("PEAKCUT_POLLINATIONS_GAP", "46"))
    max_wait = float(_env("PEAKCUT_POLLINATIONS_MAX_WAIT", "75"))
    scale = 1280 / max(w, h)
    qw, qh = int(w * scale) // 8 * 8, int(h * scale) // 8 * 8
    full = prompt if not negative else f"{prompt}. Avoid: {negative}"
    q = {"width": qw, "height": qh, "seed": seed, "nologo": "true", "model": "flux"}
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(full[:1500]) + "?" + urllib.parse.urlencode(q)
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    with _poll_lock:  # one request at a time, so parallel renders do not burn the free allowance
        for attempt in range(3):
            wait = _poll_last[0] + gap - time.time()
            if wait > 0:
                time.sleep(min(wait, max_wait))
            _poll_last[0] = time.time()
            try:
                data = _get(url, timeout=90, headers=headers)
                if len(data) > 5000 and not key:
                    # the free tier stamps a small logo in the bottom-right corner: trim that strip off
                    im = Image.open(io.BytesIO(data)).convert("RGB")
                    buf = io.BytesIO()
                    im.crop((0, 0, im.width, int(im.height * 0.94))).save(buf, "JPEG", quality=95)
                    data = buf.getvalue()
                if len(data) > 5000 and _cover_save(data, out_path, w, h):
                    return True
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "ignore") if hasattr(e, "read") else ""
                m = re.search(r"[Rr]etry after (\d+)", body)
                if e.code in (402, 429) and m and int(m.group(1)) <= max_wait:
                    _poll_last[0] = time.time() + int(m.group(1)) + 1 - gap
                    continue
                log.info("pollinations %s: %s", e.code, body[:160])
                return False
            except Exception as e:  # noqa: BLE001
                log.info("pollinations: %s", e)
    return False


def _img_openai(prompt, negative, out_path, w, h, seed) -> bool:
    key = _env("PEAKCUT_IMAGE_API_KEY")
    if not key:
        return False
    base = _env("PEAKCUT_IMAGE_API_URL", "https://api.openai.com/v1").rstrip("/")
    model = _env("PEAKCUT_IMAGE_MODEL", "gpt-image-1")
    size = "1536x1024" if w > h else ("1024x1536" if h > w else "1024x1024")
    body = {"model": model, "prompt": prompt if not negative else f"{prompt}\nAvoid: {negative}", "n": 1, "size": size}
    try:
        res = _post_json(f"{base}/images/generations", body, timeout=180, headers={"Authorization": f"Bearer {key}"})
        item = (res.get("data") or [{}])[0]
        if item.get("b64_json"):
            data = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            data = _get(item["url"], timeout=60)
        else:
            return False
        return _cover_save(data, out_path, w, h)
    except Exception as e:  # noqa: BLE001
        log.warning("openai_images: %s", e)
        return False


def _comfy_url() -> str:
    return _env("PEAKCUT_COMFYUI_URL").rstrip("/")


def _fill(workflow_text: str, values: dict) -> dict:
    for k, v in values.items():
        token = "{{" + k + "}}"
        if isinstance(v, (int, float)):
            workflow_text = workflow_text.replace(f'"{token}"', str(v))  # numbers stay numbers
        workflow_text = workflow_text.replace(token, json.dumps(str(v))[1:-1])
    return json.loads(workflow_text)


def _comfy_run(workflow: dict, timeout: float) -> list[dict]:
    """Queue a workflow, wait for it, return its output files [{filename, subfolder, type}]."""
    base = _comfy_url()
    pid = _post_json(f"{base}/prompt", {"prompt": workflow, "client_id": "peakcut"}, timeout=30).get("prompt_id")
    if not pid:
        return []
    end = time.time() + timeout
    while time.time() < end:
        time.sleep(2.0)
        try:
            hist = json.loads(_get(f"{base}/history/{pid}", timeout=15).decode("utf-8") or "{}")
        except Exception:  # noqa: BLE001
            continue
        if pid in hist:
            files = []
            for node in (hist[pid].get("outputs") or {}).values():
                for key in ("images", "gifs", "videos"):
                    files += node.get(key) or []
            return files
    return []


def _comfy_download(f: dict) -> bytes:
    q = urllib.parse.urlencode({"filename": f.get("filename", ""), "subfolder": f.get("subfolder", ""),
                                "type": f.get("type", "output")})
    return _get(f"{_comfy_url()}/view?{q}", timeout=120)


def _img_comfyui(prompt, negative, out_path, w, h, seed) -> bool:
    wf_path = _env("PEAKCUT_COMFY_IMAGE_WORKFLOW")
    if not _comfy_url() or not wf_path or not Path(wf_path).is_file():
        return False
    try:
        wf = _fill(Path(wf_path).read_text(encoding="utf-8"),
                   {"prompt": prompt, "negative": negative, "width": w // 8 * 8, "height": h // 8 * 8, "seed": seed})
        files = _comfy_run(wf, timeout=float(_env("PEAKCUT_COMFY_TIMEOUT", "300")))
        return bool(files) and _cover_save(_comfy_download(files[0]), out_path, w, h)
    except Exception as e:  # noqa: BLE001
        log.warning("comfyui image: %s", e)
        return False


def _img_procedural(prompt, negative, out_path, w, h, seed) -> bool:
    from studio import visuals
    random.seed(seed)
    ar = "9:16" if h > w else "16:9"
    if not visuals.draw_3d_scene_fallback(prompt, out_path, aspect_ratio=ar):
        return False
    with Image.open(out_path) as im:
        if im.size != (w, h):
            buf = io.BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=92)
            return _cover_save(buf.getvalue(), out_path, w, h)
    return True


IMAGE_PROVIDERS = {
    "pollinations": _img_pollinations,
    "openai_images": _img_openai,
    "comfyui": _img_comfyui,
    "procedural": _img_procedural,
}


def image_chain() -> list[str]:
    names = [n.strip() for n in _env("PEAKCUT_IMAGE_PROVIDERS", "pollinations,procedural").split(",") if n.strip()]
    names = [n for n in names if n in IMAGE_PROVIDERS] or ["pollinations"]
    if "procedural" not in names:
        names.append("procedural")  # a video is always finished, even offline
    return names


def generate_image(prompt: str, out_path: Path, aspect_ratio: str = "16:9", negative: str = "",
                   seed: int | None = None, chain: list[str] | None = None) -> str | None:
    """Make one picture. Returns the provider name that made it, or None."""
    w, h = size_for(aspect_ratio)
    seed = stable_seed(prompt) if seed is None else seed
    for name in chain or image_chain():
        try:
            if IMAGE_PROVIDERS[name](prompt, negative, out_path, w, h, seed):
                return name
        except Exception as e:  # noqa: BLE001
            log.warning("image provider %s failed: %s", name, e)
    return None


# ====================================================================== video providers
# signature: (image_path, prompt, negative, out_mp4, duration, width, height, seed) -> bool
# A provider returns a silent clip of about `duration` seconds; production.py fits it to the exact length.

def _vid_comfyui(image_path, prompt, negative, out_mp4, duration, w, h, seed) -> bool:
    wf_path = _env("PEAKCUT_COMFY_VIDEO_WORKFLOW")
    if not _comfy_url() or not wf_path or not Path(wf_path).is_file():
        return False
    try:
        import uuid
        # upload the still as the first frame
        boundary = uuid.uuid4().hex
        data = Path(image_path).read_bytes()
        name = f"peakcut_{uuid.uuid4().hex[:10]}.jpg"
        body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
                f"Content-Type: image/jpeg\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(f"{_comfy_url()}/upload/image", data=body, method="POST",
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            uploaded = json.loads(r.read().decode("utf-8")).get("name", name)
        fps = int(_env("PEAKCUT_COMFY_VIDEO_FPS", "16"))
        frames = max(17, min(int(_env("PEAKCUT_COMFY_MAX_FRAMES", "81")), int(duration * fps)))
        frames = (frames - 1) // 4 * 4 + 1  # Wan-style models want 4n+1 frames
        vw, vh = (832, 480) if w >= h else (480, 832)
        wf = _fill(Path(wf_path).read_text(encoding="utf-8"),
                   {"image": uploaded, "prompt": prompt, "negative": negative, "frames": frames, "fps": fps,
                    "width": vw, "height": vh, "seed": seed})
        files = _comfy_run(wf, timeout=float(_env("PEAKCUT_COMFY_VIDEO_TIMEOUT", "900")))
        vids = [f for f in files if str(f.get("filename", "")).lower().endswith((".mp4", ".webm", ".gif", ".webp"))]
        if not vids:
            return False
        raw = out_mp4.with_suffix(Path(vids[0]["filename"]).suffix)
        raw.write_bytes(_comfy_download(vids[0]))
        if raw != out_mp4:
            raw.replace(out_mp4) if raw.suffix == ".mp4" else _transcode(raw, out_mp4)
        return out_mp4.is_file() and out_mp4.stat().st_size > 1000
    except Exception as e:  # noqa: BLE001
        log.warning("comfyui video: %s", e)
        return False


def _transcode(src: Path, dst: Path):
    import subprocess
    from studio.concat import NO_WINDOW
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    str(dst)], capture_output=True, creationflags=NO_WINDOW, timeout=300)
    src.unlink(missing_ok=True)


VIDEO_PROVIDERS = {
    "comfyui": _vid_comfyui,
    # "kenburns" is the built-in local renderer in production.py and needs no entry here
}


def video_provider() -> str:
    name = _env("PEAKCUT_VIDEO_PROVIDER", "kenburns")
    return name if name in VIDEO_PROVIDERS or name == "kenburns" else "kenburns"


def animate_image(image_path: Path, prompt: str, out_mp4: Path, duration: float, aspect_ratio: str = "16:9",
                  negative: str = "", seed: int = 0) -> bool:
    """Real AI motion for one shot. False means: use the local camera-motion renderer instead."""
    name = video_provider()
    if name == "kenburns":
        return False
    w, h = size_for(aspect_ratio)
    try:
        return VIDEO_PROVIDERS[name](image_path, prompt, negative, out_mp4, duration, w, h, seed)
    except Exception as e:  # noqa: BLE001
        log.warning("video provider %s failed: %s", name, e)
        return False


def status() -> dict:
    """What is set up, for the dashboard."""
    return {
        "image_chain": image_chain(),
        "video_provider": video_provider(),
        "comfyui": bool(_comfy_url()),
        "image_api": bool(_env("PEAKCUT_IMAGE_API_KEY")),
        "available_image": list(IMAGE_PROVIDERS),
        "available_video": ["kenburns", *VIDEO_PROVIDERS],
    }
