"""Production progress for an episode: what is happening now, how far along it is, how long it has taken and how
long is left.

The episode is split into pieces of work: every scene (voice, then 3D animation or pictures, then finishing:
grade, captions and voice in one pass) and the steps at the end (joining the scenes, music, the vertical short).
Each scene counts for as much as it is long, so a 60-second scene moves the bar more than a 20-second one. Scenes
reused from an earlier render count as done straight away.

The time left comes from how fast this machine has actually been going in this episode. Before there is anything
to measure, it uses the speed remembered from the last episode made here (render_speed.json in the data folder).

The full status is also written to progress.json in the episode folder, so the page can show it again after a
reload, and a production stopped by a restart can be noticed and resumed.
"""
from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path

from studio import config

NO_WINDOW = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0

# share of a scene's work per stage, and of the whole episode for the steps at the end
SCENE_STAGES = {"voice": 0.06, "animate": 0.62, "finish": 0.32}
FINISH_SHARE = 0.10
FINISH_STEPS = {"stitch": 0.25, "music": 0.15, "short": 0.60}
STAGE_WORDS = {"waiting": "Waiting", "voice": "Recording voices", "animate": "Animating 3D", "pictures": "Making pictures",
               "finish": "Adding grade, captions and voice", "done": "Finished", "cached": "Reused from before",
               "failed": "Failed"}
FINISH_WORDS = {"stitch": "Joining the scenes", "music": "Adding music and ambience", "short": "Cutting the 9:16 short"}
SPEED_FILE = "render_speed.json"


def fmt_secs(s: float) -> str:
    s = max(0, int(round(s)))
    return f"{s // 60}m {s % 60:02d}s" if s >= 60 else f"{s}s"


def _guess_scene_len(sc: dict) -> float:
    """How long a scene will be before its voice exists: about 13 characters of speech per second."""
    chars = sum(len(str(ln.get("text") or "")) for ln in sc.get("lines") or [])
    return max(5.0, chars / 13.0 + 1.4) if chars else float(sc.get("duration_sec") or 8)


def remembered_speed(kind: str) -> float | None:
    """Seconds of work per second of finished video, from the last episodes made on this machine."""
    try:
        d = json.loads((config.DATA_DIR / SPEED_FILE).read_text(encoding="utf-8"))
        v = float(d.get(kind) or 0)
        return v if v > 0 else None
    except Exception:  # noqa: BLE001
        return None


def remember_speed(kind: str, secs_per_video_sec: float) -> None:
    if secs_per_video_sec <= 0:
        return
    f = config.DATA_DIR / SPEED_FILE
    try:
        d = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except Exception:  # noqa: BLE001
        d = {}
    old = float(d.get(kind) or 0)
    d[kind] = round(secs_per_video_sec if not old else old * 0.4 + secs_per_video_sec * 0.6, 3)
    try:
        f.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


class Tracker:
    """Collects progress from every step and reports one full status through on_change(status)."""

    def __init__(self, scenes: list[dict], ep_dir: Path, on_change=None, started_at: float | None = None,
                 kind: str = "anim3d", ep_num: int = 0, title: str = ""):
        self.ep_dir, self.on_change, self.kind = ep_dir, on_change, kind
        self.started_at = started_at or time.time()
        self.ep_num, self.title = ep_num, title
        self.scenes = [{"idx": i + 1, "setting": str(sc.get("setting") or "")[:60], "length": round(_guess_scene_len(sc), 1),
                        "stage": "waiting", "frac": 0.0, "done": 0, "total": 0, "started": None, "took": None,
                        "error": ""} for i, sc in enumerate(scenes)]
        self.finish = {k: {"stage": "waiting", "frac": 0.0, "took": None, "started": None} for k in FINISH_STEPS}
        self.now_label, self.now_frac, self.now_since = "Getting ready", 0.0, time.time()
        self.free = 0.0            # share of the work that was reused (not counted in the speed)
        self.state = "rendering"
        self._lock = threading.Lock()
        self._last_write = 0.0

    # ---------------------------------------------------------------- the pieces of work
    def _weights(self):
        lens = [max(1.0, s["length"]) for s in self.scenes] or [1.0]
        tot = sum(lens)
        return [(1 - FINISH_SHARE) * x / tot for x in lens]

    def percent(self) -> float:
        w = self._weights()
        p = 0.0
        for s, wi in zip(self.scenes, w):
            if s["stage"] in ("done", "cached", "failed"):
                p += wi
                continue
            got = 0.0
            for st, share in SCENE_STAGES.items():
                key = "animate" if s["stage"] == "pictures" else s["stage"]
                if st == key:
                    got += share * s["frac"]
                    break
                got += share
            if s["stage"] != "waiting":
                p += wi * got
        for k, share in FINISH_STEPS.items():
            f = self.finish[k]
            p += FINISH_SHARE * share * (1.0 if f["stage"] in ("done", "skipped") else f["frac"])
        return min(1.0, p)

    def eta(self) -> float | None:
        """Seconds left: from this episode's own speed once there is enough to measure, else the remembered one."""
        p = self.percent()
        spent = time.time() - self.started_at
        work = max(0.0, p - self.free)
        rest = max(0.0, 1.0 - p)
        if rest <= 0:
            return 0.0
        if work >= 0.04 and spent > 20:
            return spent / work * rest
        speed = remembered_speed(self.kind)
        if speed:
            left_video = sum(s["length"] for s in self.scenes if s["stage"] not in ("done", "cached", "failed"))
            return speed * left_video * (1 + FINISH_SHARE)
        return None

    # ---------------------------------------------------------------- updates from the steps
    def scene(self, idx: int, stage: str, frac: float = 0.0, done: int = 0, total: int = 0, length: float | None = None,
              error: str = ""):
        with self._lock:
            s = self.scenes[idx - 1]
            if stage != s["stage"]:
                if s["started"] is None and stage not in ("waiting", "cached"):
                    s["started"] = time.time()
                self.now_since = time.time()
            s["stage"], s["frac"], s["done"], s["total"] = stage, max(0.0, min(1.0, frac)), done, total
            if length:
                s["length"] = round(float(length), 1)
            if error:
                s["error"] = error[:200]
            if stage in ("done", "failed") and s["started"] is not None:
                s["took"] = round(time.time() - s["started"], 1)
            if stage == "cached":
                s["took"] = 0
                self.free += self._weights()[idx - 1]
            n = len(self.scenes)
            if stage in ("done", "cached", "failed"):
                self.now_label, self.now_frac = f"Scene {idx} of {n}: {STAGE_WORDS[stage].lower()}", 1.0
            else:
                extra = f" · frame {done} / {total}" if stage == "animate" and total else \
                        f" · {done} / {total}" if total else ""
                self.now_label, self.now_frac = f"Scene {idx} of {n}: {STAGE_WORDS.get(stage, stage)}{extra}", s["frac"]
        self.push()

    def step(self, key: str, stage: str, frac: float = 0.0):
        with self._lock:
            f = self.finish[key]
            if stage == "running" and f["started"] is None:
                f["started"] = time.time()
                self.now_since = time.time()
            f["stage"], f["frac"] = stage, max(0.0, min(1.0, frac))
            if stage in ("done", "skipped", "failed") and f["started"] is not None:
                f["took"] = round(time.time() - f["started"], 1)
            self.now_label = FINISH_WORDS[key] + ("" if stage == "running" else f": {stage}")
            self.now_frac = f["frac"] if stage == "running" else 1.0
        self.push()

    def end(self, ok: bool):
        with self._lock:
            self.state = "completed" if ok else "failed"
            self.now_label = "Production complete" if ok else "Production failed"
            self.now_frac = 1.0
        if ok:   # remember how fast this machine is, for the next episode's first estimate
            made = sum(s["length"] for s in self.scenes if s["stage"] == "done")
            reused = sum(s["length"] for s in self.scenes if s["stage"] == "cached")
            if made > 0 and made >= reused:
                remember_speed(self.kind, (time.time() - self.started_at) / made)
        self.push(force=True)

    # ---------------------------------------------------------------- reporting
    def status(self) -> dict:
        now = time.time()
        with self._lock:
            pct = self.percent()
            left = self.eta() if self.state == "rendering" else 0.0
            n = len(self.scenes)
            current = next((s for s in self.scenes if s["stage"] not in ("waiting", "done", "cached", "failed")), None)
            return {
                "status": self.state,
                "progress": 100 if self.state == "completed" else int(pct * 100),
                "percent": round(pct * 100, 1),
                "message": self.now_label,
                "now": now,
                "started_at": self.started_at,
                "elapsed": round(now - self.started_at, 1),
                "eta_sec": None if left is None else round(left),
                "step": {"label": self.now_label, "frac": round(self.now_frac, 3), "since": self.now_since},
                "scene_count": n,
                "scenes_done": sum(1 for s in self.scenes if s["stage"] in ("done", "cached")),
                "current_scene": current["idx"] if current else None,
                "scenes": [{k: s[k] for k in ("idx", "setting", "length", "stage", "frac", "done", "total", "took",
                                              "error")} | {"label": STAGE_WORDS.get(s["stage"], s["stage"]),
                                                           "elapsed": round(now - s["started"], 1) if s["started"] and s["took"] is None else None}
                           for s in self.scenes],
                "finish": [{"key": k, "label": FINISH_WORDS[k], "stage": f["stage"], "frac": round(f["frac"], 3),
                            "took": f["took"]} for k, f in self.finish.items()],
                "ep_num": self.ep_num,
                "title": self.title,
            }

    def push(self, force: bool = False):
        st = self.status()
        if self.on_change:
            try:
                self.on_change(st)
            except Exception:  # noqa: BLE001
                pass
        t = time.time()
        if force or t - self._last_write > 1.0:   # the file is for reloads and restarts: once a second is plenty
            self._last_write = t
            write_file(self.ep_dir, st)


def write_file(ep_dir: Path, st: dict) -> None:
    try:
        ep_dir.mkdir(parents=True, exist_ok=True)
        tmp = ep_dir / "progress.json.tmp"
        tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ep_dir / "progress.json")
    except OSError:
        pass


def read_file(ep_dir: Path) -> dict | None:
    try:
        return json.loads((ep_dir / "progress.json").read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- ffmpeg with progress
_TIME_RE = re.compile(r"^out_time_(?:us|ms)=(\d+)")


def ffmpeg(cmd: list, duration: float, on_frac=None, cwd=None, timeout: float = 900) -> subprocess.CompletedProcess:
    """Run ffmpeg like subprocess.run(capture_output=True, text=True), calling on_frac(0..1) as it goes.
    `duration` is how long the output will be, in seconds."""
    full = [cmd[0], "-progress", "pipe:1", "-nostats"] + list(cmd[1:])
    p = subprocess.Popen(full, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                         encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    err: list[str] = []
    reader = threading.Thread(target=lambda: err.append(p.stderr.read() or ""), daemon=True)
    reader.start()   # errors are read on the side, so a chatty ffmpeg never blocks
    killer = threading.Timer(timeout, p.kill)
    killer.start()
    last = 0.0
    try:
        for line in p.stdout:
            m = _TIME_RE.match(line.strip())
            if m and on_frac and duration > 0:
                frac = min(1.0, int(m.group(1)) / 1_000_000 / duration)
                if frac - last >= 0.01:
                    last = frac
                    try:
                        on_frac(frac)
                    except Exception:  # noqa: BLE001
                        pass
        p.wait()
    finally:
        killer.cancel()
        reader.join(timeout=5)
    return subprocess.CompletedProcess(full, p.returncode, "", "".join(err))
