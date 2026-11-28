"""Render worker: plays a 3D scene spec in a headless Chrome/Edge (WebGL) and records it frame by frame.

The runtime (web/studio3d/) is served from a small local web server on 127.0.0.1, the browser is driven through
its DevTools protocol, and every frame is piped straight into ffmpeg. Nothing leaves the machine.
Set PEAKCUT_CHROME to a browser executable if Chrome/Edge are not in their usual places."""
from __future__ import annotations

import asyncio
import base64
import functools
import http.server
import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

log = logging.getLogger("peakcut.anim3d")
NO_WINDOW = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
RUNTIME_DIR = Path(__file__).resolve().parent.parent.parent / "web" / "studio3d"


def find_browser() -> str | None:
    env = os.environ.get("PEAKCUT_CHROME", "").strip()
    if env and Path(env).is_file():
        return env
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.join(local, r"Google\Chrome\Application\chrome.exe") if local else "",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
        p = shutil.which(name)
        if p:
            return p
    return None


def available() -> bool:
    try:
        import websockets  # noqa: F401
    except ImportError:
        return False
    return bool(find_browser()) and (RUNTIME_DIR / "vendor" / "three.module.js").is_file()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # noqa: D401
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


_server_lock = threading.Lock()
_server: dict = {}


def _runtime_url() -> str:
    """One small local web server for the runtime files, started once per process."""
    with _server_lock:
        if not _server:
            port = _free_port()
            handler = functools.partial(_Quiet, directory=str(RUNTIME_DIR))
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            _server["url"] = f"http://127.0.0.1:{port}/render.html"
        return _server["url"]


class Browser:
    """A headless browser session. Use as a context manager; render as many scenes as you like."""

    def __init__(self):
        self.exe = find_browser()
        if not self.exe:
            raise RuntimeError("No Chrome or Edge found for 3D rendering (set PEAKCUT_CHROME)")
        self.port = _free_port()
        self.profile = tempfile.mkdtemp(prefix="peakcut3d-")
        self.proc = None

    def __enter__(self):
        self.proc = subprocess.Popen(
            [self.exe, "--headless=new", f"--remote-debugging-port={self.port}", f"--user-data-dir={self.profile}",
             "--enable-gpu", "--ignore-gpu-blocklist", "--enable-webgl", "--use-angle=default", "--mute-audio",
             "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--hide-scrollbars",
             "--window-size=1920,1080", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        for _ in range(100):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json", timeout=2).read())
                self.ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page")
                return self
            except Exception:  # noqa: BLE001
                time.sleep(0.15)
        self.__exit__(None, None, None)
        raise RuntimeError("The headless browser did not start")

    def __exit__(self, *a):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        shutil.rmtree(self.profile, ignore_errors=True)

    def render(self, spec: dict, out_mp4: Path, progress=None, timeout_per_frame: float = 30.0) -> bool:
        return asyncio.run(self._render(spec, out_mp4, progress, timeout_per_frame))

    def snapshot(self, spec: dict, t: float, out_jpg: Path) -> bool:
        return asyncio.run(self._snapshot(spec, t, out_jpg))

    async def _session(self):
        import websockets
        ws = await websockets.connect(self.ws_url, max_size=400_000_000)
        n = [0]

        async def ev(js, timeout=60.0):
            n[0] += 1
            my = n[0]
            await ws.send(json.dumps({"id": my, "method": "Runtime.evaluate",
                                      "params": {"expression": js, "awaitPromise": True, "returnByValue": True}}))
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                if m.get("id") == my:
                    r = m.get("result", {})
                    if r.get("exceptionDetails"):
                        raise RuntimeError("3D runtime error: " + json.dumps(r["exceptionDetails"])[:500])
                    return r.get("result", {}).get("value")

        n[0] += 1
        await ws.send(json.dumps({"id": n[0], "method": "Page.navigate", "params": {"url": _runtime_url()}}))
        for _ in range(400):   # up to 40 s: a busy laptop can take a while to start the runtime
            await asyncio.sleep(0.1)
            try:
                if await ev("window.peakcut3dReady === true", timeout=5):
                    break
            except Exception:  # noqa: BLE001
                pass
        else:
            raise RuntimeError("The 3D runtime did not load")
        return ws, ev

    async def _render(self, spec, out_mp4: Path, progress, timeout_per_frame) -> bool:
        ws, ev = await self._session()
        try:
            info = await ev("window.setup(" + json.dumps(spec, ensure_ascii=False) + ")", timeout=120)
            log.info("3D scene ready on %s", (info or {}).get("gpu", "?"))
            fps = int(spec.get("fps", 30))
            frames = max(1, int(round(float(spec["duration"]) * fps)))
            out_mp4.parent.mkdir(parents=True, exist_ok=True)
            ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
                                   "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-color_range", "tv",
                                   "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
                                   "-r", str(fps), str(out_mp4)],
                                  stdin=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
            t0 = time.time()
            try:
                for i in range(frames):
                    url = await ev(f"window.renderAt({i / fps:.5f})", timeout=timeout_per_frame)
                    ff.stdin.write(base64.b64decode(url.split(",", 1)[1]))
                    if progress and (i % fps == 0 or i == frames - 1):
                        el = time.time() - t0
                        left = el / (i + 1) * (frames - i - 1)
                        progress(i + 1, frames, left)
            finally:
                ff.stdin.close()
                ff.wait(timeout=300)
            return out_mp4.is_file() and out_mp4.stat().st_size > 1000
        finally:
            await ws.close()

    async def _snapshot(self, spec, t, out_jpg: Path) -> bool:
        ws, ev = await self._session()
        try:
            await ev("window.setup(" + json.dumps(spec, ensure_ascii=False) + ")", timeout=120)
            url = await ev(f"window.renderAt({t})", timeout=60)
            out_jpg.parent.mkdir(parents=True, exist_ok=True)
            out_jpg.write_bytes(base64.b64decode(url.split(",", 1)[1]))
            return out_jpg.is_file()
        finally:
            await ws.close()
