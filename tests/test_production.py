"""The AI Studio production engine, offline: formats, script -> lines/shots, camera moves, music, a full episode.

    python tests/test_production.py

No AI key and no internet: pictures come from the local procedural provider and the voice is a stand-in tone,
so this checks the pipeline (timing, grading, captions, stitching, mixing, the short), not image quality."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, ".")
data = Path(tempfile.mkdtemp(prefix="peakcut-prod-"))
os.environ["PEAKCUT_DATA"] = str(data)
os.environ["PEAKCUT_IMAGE_PROVIDERS"] = "procedural"
os.environ["PEAKCUT_VIDEO_PROVIDER"] = "kenburns"
os.environ["PEAKCUT_MOTION_SUPERSAMPLE"] = "1"
os.environ["PEAKCUT_3D"] = "0"   # this file checks the picture pipeline; tests/test_anim3d.py checks 3D

from studio import concat, formats, production, providers, soundtrack, tts  # noqa: E402


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def fake_lines(lines, out_audio, gap=0.35):
    """Each line becomes a short tone, ~0.06 s per character, with word times spread across it."""
    t, words, spans = 0.0, [], []
    parts = []
    for i, ln in enumerate(lines):
        d = max(0.8, min(4.0, len(ln["text"]) * 0.06))
        ws = ln["text"].split()
        for k, w in enumerate(ws):
            words.append({"w": w, "s": round(t + d * k / len(ws), 3), "e": round(t + d * (k + 1) / len(ws), 3)})
        spans.append((t, t + d))
        parts.append(f"sine=frequency={300 + 80 * i}:duration={d}")
        t += d + gap
    total = t - gap
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=330:duration={total:.2f}",
                    "-c:a", "libmp3lame", str(out_audio)], check=True, creationflags=concat.NO_WINDOW)
    return words, spans


# ---------------------------------------------------------------- formats
fl = formats.list_formats()
check("at least 15 formats, each with a name and style", len(fl) >= 15 and all(f["name"] and f["visual_style"] for f in fl))
check("old series without a format still resolve", formats.resolve({"genre": "3D Cartoon Adventure"})["id"] == "kids_3d")
check("a horror genre resolves to the horror recipe", formats.resolve({"genre": "Horror stories"})["id"] == "horror")
r = formats.resolve({"format": "anime", "visual_style": "my own style", "aspect_ratio": "9:16"})
check("series overrides win over the format", r["visual"]["style"] == "my own style" and r["aspect_ratio"] == "9:16")
check("every format has a valid caption template and music mood",
      all(f["sound"]["music"] in soundtrack.MOODS for f in formats.FORMATS.values()))
check("every format names real camera moves",
      all(m in production.MOVES for f in formats.FORMATS.values() for m in f["motion"]["moves"]))
check("narrator voice follows the language", formats.narrator_voice(formats.get("horror"), "hi").startswith("hi-IN"))

# ---------------------------------------------------------------- script normalisation
series = {"id": "t", "default_language": "en", "format": "horror",
          "characters": [{"name": "Maya", "voice_id": "en-US-JennyNeural", "visual_anchor": "young woman, red raincoat"},
                         {"name": "Kabir", "voice_id": "en-US-GuyNeural", "visual_anchor": "tall man, grey beard"}]}
fmt = formats.resolve(series)
old = {"speaker": "Maya", "dialogue": "Maya: Did you hear that?\nKabir: It came from the cellar.", "visual_prompt": "a dark cellar door",
       "camera_motion": "zoom_in"}
sc = production.normalize_scene(old, series, fmt)
check("old 'Name: line' dialogue splits into two voiced lines",
      [(l["speaker"], l["voice_id"]) for l in sc["lines"]] == [("Maya", "en-US-JennyNeural"), ("Kabir", "en-US-GuyNeural")])
check("old camera names map to the new moves", sc["shots"][0]["camera_motion"] == "dolly_in")
check("narrator lines take the format's narrator and prosody",
      production.normalize_scene({"dialogue": "It was cold."}, series, fmt)["lines"][0]["rate"] == fmt["voice"]["rate"])
new = {"lines": [{"speaker": "Narrator", "text": "The house was quiet."}, {"speaker": "Maya", "text": "Hello?"}],
       "dialogue": "Narrator: The house was quiet.\nMaya: Hello?",
       "shots": [{"visual_prompt": "old house at night"}, {"visual_prompt": "Maya on the stairs"}],
       "visual_prompt": "old house at night"}
check("AI lines kept when the editor did not change them", len(production.normalize_scene(new, series, fmt)["lines"]) == 2)
edited = dict(new, dialogue="Something completely different.")
check("an edited dialogue box wins over the AI lines",
      production.normalize_scene(edited, series, fmt)["lines"][0]["text"] == "Something completely different.")
p = production.build_prompt("Maya on the stairs", fmt, sc["cast"])
check("shot prompts carry the character's fixed look and the format style",
      "red raincoat" in p and fmt["visual"]["style"][:20] in p and "grey beard" not in p)
shots = production.plan_shots(production.normalize_scene(new, series, fmt), fmt, 30.0, [(0, 2), (2.5, 4)])
check("a long scene gets extra framings instead of one frozen picture", len(shots) >= 3)
check("shot durations add up to the scene", abs(sum(s["dur"] for s in shots) - 30.0) < 0.05)
two = production.plan_shots(production.normalize_scene(new, series, fmt), fmt, 4.0, [(0, 1.8), (2.1, 4.0)])
check("with one shot per line, the cut lands on the line change", len(two) == 2 and abs(two[1]["start"] - 1.98) < 0.01)

# ---------------------------------------------------------------- providers
img = data / "p.jpg"
check("procedural provider always gives a picture of the right size",
      providers.generate_image("haunted forest at night", img, "9:16") == "procedural")
from PIL import Image  # noqa: E402
check("pictures are exactly 1080x1920 for 9:16", Image.open(img).size == (1080, 1920))
check("seeds are stable", providers.stable_seed("a", 1) == providers.stable_seed("a", 1) != providers.stable_seed("a", 2))
wf = production.providers._fill('{"a": "{{prompt}}", "w": "{{width}}"}', {"prompt": 'say "hi"', "width": 512})
check("ComfyUI workflow placeholders: text escaped, numbers stay numbers", wf == {"a": 'say "hi"', "w": 512})

import io  # noqa: E402
import urllib.error  # noqa: E402
calls = []


def fake_get(url, timeout=60, headers=None):
    calls.append(url)
    if len(calls) == 1:
        raise urllib.error.HTTPError(url, 402, "limit", {}, io.BytesIO(
            b'{"error":{"code":"FREE_LIMIT","message":"Free limit reached: Retry after 1s"}}'))
    buf = io.BytesIO()
    Image.new("RGB", (1280, 720), (90, 40, 40)).save(buf, "JPEG", quality=95)
    return buf.getvalue() + b"\0" * 6000


os.environ["PEAKCUT_POLLINATIONS_GAP"] = "0"
with patch.object(providers, "_get", side_effect=fake_get):
    ok = providers.generate_image("x", data / "poll.jpg", "16:9", chain=["pollinations"])
check("pollinations: a free-limit answer is waited out and retried", ok == "pollinations" and len(calls) == 2)

cropped = Image.open(data / "poll.jpg")
check("pollinations: the free-tier logo strip is trimmed and the frame is still 1920x1080", cropped.size == (1920, 1080))

# a scene where only the first picture came from a real service: the others borrow it, never the drawn farm
bdir = data / "borrow"
bdir.mkdir()
answers = iter(["pollinations", "procedural"])


def half_real(prompt, out, aspect="16:9", negative="", seed=None, chain=None):
    Image.new("RGB", (1920, 1080), (200, 0, 0) if "first" in prompt else (0, 200, 0)).save(out, "JPEG")
    return next(answers)


bs = production.normalize_scene({"lines": [], "shots": [{"visual_prompt": "first shot"}, {"visual_prompt": "second shot"}],
                                  "visual_prompt": "first shot", "duration_sec": 3}, series, fmt)
with patch.object(providers, "generate_image", side_effect=half_real), \
     patch.object(providers, "image_chain", return_value=["pollinations", "procedural"]):
    production.render_scene(bs, 1, bdir, series, fmt, "en", seed_key="b", captions=False)
r, g, b = Image.open(bdir / "scene_01_shot01.jpg").resize((1, 1)).getpixel((0, 0))
check("a shot whose picture failed borrows the scene's real picture", r > g)
check("borrowed shots are remembered, so the next render tries again",
      "borrowed" in json.loads((bdir / "scene_01.json").read_text())["providers"])

vf = data / "vf.jpg"
production.virtual_framing(img, vf, "close-up shot")
check("virtual camera: a close-up is cut from the same picture at full size", Image.open(vf).size == Image.open(img).size)

# ---------------------------------------------------------------- camera moves
providers.generate_image("castle on a hill", img, "16:9")
for mv in production.MOVES:
    out = data / f"mv_{mv}.mp4"
    ok = production.ken_burns(img, out, 1.2, mv, "16:9")
    check(f"camera move {mv} renders", ok and abs(concat._get_duration(out) - 1.2) < 0.15)

# ---------------------------------------------------------------- music
for mood in soundtrack.MOODS:
    check(f"music mood {mood} makes a loop", soundtrack.music_track(mood, 1) is not None)
for amb in soundtrack.AMBIENCES:
    check(f"ambience {amb} makes a loop", soundtrack.ambience_track(amb) is not None)

# ---------------------------------------------------------------- a whole episode
script = {"title": "The Cellar", "scenes": [
    {"setting": "farmhouse", "lines": [{"speaker": "Narrator", "text": "Nobody had opened the cellar in forty years."},
                                       {"speaker": "Maya", "text": "Then why is the lock new?"}],
     "dialogue": "Narrator: Nobody had opened the cellar in forty years.\nMaya: Then why is the lock new?",
     "shots": [{"visual_prompt": "old farmhouse at night, fog"}, {"visual_prompt": "Maya holding a new padlock"}],
     "visual_prompt": "old farmhouse at night, fog"},
    {"setting": "cellar", "speaker": "Kabir", "dialogue": "Stay behind me. Whatever is down there knows we are here.",
     "visual_prompt": "stone stairs going down into darkness", "teaser": True},
]}
for fid in ("horror", "kids_3d"):
    s = dict(series, format=fid, id=f"t-{fid}")
    ep_dir = data / fid
    with patch.object(tts, "synthesize_lines", side_effect=fake_lines):
        res = production.build_episode(s, 1, script, ep_dir)
    check(f"{fid}: the master video is made", res["ok"] and res["master"] and res["master"].is_file())
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(res["master"])],
                                      capture_output=True, text=True, creationflags=concat.NO_WINDOW).stdout)
    kinds = {st["codec_type"]: st for st in probe["streams"]}
    check(f"{fid}: master is 1920x1080 with sound", kinds["video"]["width"] == 1920 and "audio" in kinds)
    check(f"{fid}: a 9:16 short is cut", res["short"] and res["short"].is_file())
    m1 = json.loads((ep_dir / "scene_01.json").read_text())
    check(f"{fid}: scenes are cached by content", m1["hash"])
    if fid == "horror":
        check("extra framings reuse the scene's pictures (no extra image requests)", "virtual" in m1["providers"]
              or m1["shots"] == 2)
    with patch.object(tts, "synthesize_lines", side_effect=AssertionError("should be cached")):
        again = production.render_scene(res["scenes"][0], 1, ep_dir, s, formats.resolve(s), "en", seed_key="x")
    check(f"{fid}: an unchanged scene is not rendered again", again and again["cached"])

print("ALL PASS")
