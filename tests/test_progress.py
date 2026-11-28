"""Episode production progress (studio/progress.py): the bar only moves forward, every scene and final step is
reported, timers and time left are there, the status file survives for reloads, and a stopped production can be
found and resumed.

    python tests/test_progress.py

Offline: pictures from the local painter, a stand-in tone for the voice, 3D off (tests/test_anim3d.py covers 3D)."""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, ".")
data = Path(tempfile.mkdtemp(prefix="peakcut-progress-"))
os.environ["PEAKCUT_DATA"] = str(data)
os.environ["PEAKCUT_IMAGE_PROVIDERS"] = "procedural"
os.environ["PEAKCUT_VIDEO_PROVIDER"] = "kenburns"
os.environ["PEAKCUT_MOTION_SUPERSAMPLE"] = "1"
os.environ["PEAKCUT_3D"] = "0"

from studio import concat, memory, production, progress, series as series_engine, tts  # noqa: E402


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def fake_lines(lines, out_audio, gap=0.35):
    t, words, spans = 0.0, [], []
    for ln in lines:
        d = max(0.8, min(3.0, len(ln["text"]) * 0.05))
        ws = ln["text"].split()
        for k, w in enumerate(ws):
            words.append({"w": w, "s": round(t + d * k / len(ws), 3), "e": round(t + d * (k + 1) / len(ws), 3)})
        spans.append((t, t + d))
        t += d + gap
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=330:duration={t - gap:.2f}",
                    "-c:a", "libmp3lame", str(out_audio)], check=True, creationflags=concat.NO_WINDOW)
    return words, spans


# ---------------------------------------------------------------- the tracker on its own
scenes = [{"setting": "road", "lines": [{"text": "x" * 260}]}, {"setting": "dhaba", "lines": [{"text": "y" * 130}]}]
seen = []
tr = progress.Tracker(scenes, data / "unit", seen.append, ep_num=3, title="Test", started_at=time.time() - 30)
check("a longer scene counts for more of the bar", tr._weights()[0] > tr._weights()[1])
tr.scene(1, "voice")
tr.scene(1, "animate", 0.5, 120, 240)
st = tr.status()
check("the status says which scene, of how many, and what it is doing",
      st["current_scene"] == 1 and st["scene_count"] == 2 and "Scene 1 of 2" in st["message"] and "120 / 240" in st["message"])
tr.scene(1, "finish", 0.5)
tr.scene(1, "done", 1.0)
tr.scene(2, "cached")
for k in ("stitch", "music", "short"):
    tr.step(k, "running", 0.5)
    tr.step(k, "done")
tr.end(True)
pcts = [x["percent"] for x in seen]
check("the percentage never goes backwards", all(b >= a for a, b in zip(pcts, pcts[1:])))
fin = tr.status()
check("it ends at 100% with times for each scene and step",
      fin["progress"] == 100 and fin["scenes"][0]["took"] is not None and all(f["took"] is not None for f in fin["finish"]))
check("a reused scene is marked as reused", fin["scenes"][1]["stage"] == "cached" and fin["scenes"][1]["took"] == 0)
check("the status is written for reloads", progress.read_file(data / "unit")["status"] == "completed")
check("the machine's speed is remembered for the next estimate", progress.remembered_speed("anim3d") is not None)

# ---------------------------------------------------------------- ffmpeg reports how far it is
fr = []
out = data / "tone.mp4"
p = progress.ffmpeg(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=24:duration=4",
                     "-c:v", "libx264", "-preset", "ultrafast", str(out)], 4.0, fr.append)
check("ffmpeg runs and reports its progress", p.returncode == 0 and out.is_file() and fr and fr[-1] > 0.9)

# ---------------------------------------------------------------- a whole episode through the series engine
s = memory.create_series("Progress Test", genre="Horror", aspect_ratio="16:9", default_language="en", format="horror",
                         characters=[{"name": "Maya", "voice_id": "en-US-JennyNeural", "visual_anchor": "young woman"}])
sid = s["id"]
script = {"title": "The Cellar", "scenes": [
    {"setting": "farmhouse", "lines": [{"speaker": "Maya", "text": "Nobody had opened the cellar in forty years."}],
     "visual_prompt": "old farmhouse at night"},
    {"setting": "cellar", "lines": [{"speaker": "Maya", "text": "Then why is the lock new?"}],
     "visual_prompt": "stone stairs into darkness", "teaser": True},
]}
statuses = []
real_build = production.build_episode


def spy_build(*a, **k):
    on = k.get("on_status")

    def both(st):
        statuses.append(json.loads(json.dumps(st)))
        on(st)
    k["on_status"] = both
    return real_build(*a, **k)


with patch.object(tts, "synthesize_lines", side_effect=fake_lines), \
        patch.object(series_engine.visuals, "generate_character_avatar", return_value=None), \
        patch.object(production, "build_episode", side_effect=spy_build):
    series_engine.start_episode_production(sid, 1, script)
    for _ in range(600):
        st = series_engine.get_production_status(sid, 1)
        if st.get("status") in ("completed", "failed"):
            break
        time.sleep(0.5)
check("the episode is made", st["status"] == "completed")
check("the finished status has the render time", st.get("render_seconds", 0) > 0)
ep = memory.get_episode(sid, 1)
check("the episode keeps how long it took, per scene too",
      ep.get("render_seconds", 0) > 0 and len(ep["render_steps"]["scenes"]) == 2)
stages = {(x["current_scene"], x["scenes"][x["current_scene"] - 1]["stage"]) for x in statuses if x.get("current_scene")}
check("every scene reported its voice, pictures and finishing", all((i, k) in stages for i in (1, 2)
                                                                    for k in ("voice", "pictures", "finish")))
check("the final steps were reported while running",
      any(f["key"] == "stitch" and f["stage"] == "running" for x in statuses for f in x["finish"])
      and any(f["key"] == "short" and f["stage"] == "running" for x in statuses for f in x["finish"]))
pcts = [x["percent"] for x in statuses]
check("the bar only moves forward across the whole episode", all(b >= a for a, b in zip(pcts, pcts[1:])))
check("there is a time-left estimate while it works", any(x.get("eta_sec") is not None for x in statuses))
check("the saved script is kept for resuming", (data / "series" / sid / "episodes" / "ep_001" / "script.json").is_file())

# ---------------------------------------------------------------- a production stopped by a restart
d2 = data / "series" / sid / "episodes" / "ep_002"
d2.mkdir(parents=True, exist_ok=True)
progress.write_file(d2, {"status": "rendering", "percent": 40, "progress": 40, "ep_num": 2, "scenes": []})
(d2 / "script.json").write_text(json.dumps(script), encoding="utf-8")
st2 = series_engine.get_production_status(sid, 2)
check("a production stopped part-way is reported as stopped, with resume offered",
      st2["status"] == "interrupted" and st2["can_resume"])
check("the list of productions shows it", any(x["ep_num"] == 2 for x in series_engine.list_productions(sid)))
# ---------------------------------------------------------------- voices: an invented voice, and no internet
check("an invented voice is swapped for a real one of the same language and gender",
      tts.usable_voice("hi-IN-NeerjaNeural") == "hi-IN-SwaraNeural" and tts.usable_voice("hi-IN-KabirNeural") == "hi-IN-MadhurNeural"
      and tts.usable_voice("hi-IN-SwaraNeural") == "hi-IN-SwaraNeural")


def no_internet(*a, **k):
    raise tts.VoiceServiceError("Connection timeout")


with patch.object(tts, "synthesize_lines", side_effect=no_internet):
    r = production.build_episode(memory.get_series(sid), 3, script, data / "series" / sid / "episodes" / "ep_003")
check("without the voice service the episode stops at once, says why and offers resume",
      not r["ok"] and "internet" in r["error"] and r.get("can_resume")
      and r["progress"]["scenes"][0]["stage"] == "failed" and r["progress"]["scenes"][1]["stage"] == "waiting")
print("ALL PASS")
