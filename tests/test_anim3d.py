"""Real 3D animation (studio/anim3d): character designs, the Director, and a real headless render.

    python tests/test_anim3d.py

No AI key and no internet: the voice is a stand-in tone. The render part runs only when Chrome or Edge is
installed (it says so and skips otherwise)."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, ".")
data = Path(tempfile.mkdtemp(prefix="peakcut-3d-"))
os.environ["PEAKCUT_DATA"] = str(data)
os.environ["PEAKCUT_IMAGE_PROVIDERS"] = "procedural"
os.environ["PEAKCUT_3D_HEIGHT"] = "360"      # small and quick for the test
os.environ["PEAKCUT_3D_FPS"] = "12"

from studio import anim3d, concat, formats, production, tts  # noqa: E402
from studio.anim3d import characters as toon, director  # noqa: E402


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


# ---------------------------------------------------------------- designs
d = toon.design_for({"name": "Bhalu Bhai", "species": "Brown Bear", "visual_anchor": "big brown bear with a red scarf"})
check("a bear becomes an animal toon with a scarf", d["type"] == "animal" and d["snout"] == "bear" and d.get("accessory") == "scarf")
check("hindi species words work", toon.design_for({"name": "Moti", "species": "बिल्ली"})["ears"] == "pointy")
g = toon.design_for({"name": "Dadi", "species": "grandma", "visual_anchor": "kind old woman"})
check("a grandma is an old woman with glasses", g["type"] == "human" and g["age"] == "old" and g["gender"] == "f" and g["glasses"])
k = toon.design_for({"name": "Kabir", "species": "Human Detective"})
check("a detective wears a fedora", k["type"] == "human" and k.get("hat") == "fedora")
check("robots are robots", toon.design_for({"name": "Zip", "species": "little robot"})["type"] == "robot")
check("a rice ball spirit is a critter with a seaweed band",
      toon.design_for({"name": "Onigiri", "species": "Rice Ball Spirit"}) == {**toon.design_for({"name": "Onigiri", "species": "Rice Ball Spirit"}), "type": "critter", "band": True})
check("'bearded man' is not a bear", toon.design_for({"name": "Raju", "species": "bearded man"})["type"] == "human")
check("designs are stable", toon.design_for({"name": "X", "species": "cat"}) == toon.design_for({"name": "X", "species": "cat"}))
check("a hand-set toon value wins", toon.design_for({"name": "X", "species": "cat", "toon": {"fur": "#000000"}})["fur"] == "#000000")

# ---------------------------------------------------------------- director
series = {"id": "s", "characters": [
    {"name": "Bhalu", "species": "bear", "visual_anchor": "brown bear, red scarf", "voice_id": "hi-IN-MadhurNeural"},
    {"name": "Chintu", "species": "little boy", "visual_anchor": "orange cap, blue shirt", "voice_id": "hi-IN-SwaraNeural"}]}
fmt = formats.get("kids_3d")
sc = production.normalize_scene({"setting": "autumn forest", "lines": [
    {"speaker": "Chintu", "text": "Namaste Bhalu! Look what I found!", "emotion": "excited"},
    {"speaker": "Bhalu", "text": "Wow, a magic stone?", "emotion": "surprised"},
    {"speaker": "Narrator", "text": "And so their adventure began."},
    {"speaker": "Chintu", "text": "Let's go find out!", "emotion": "happy"}]}, series, fmt)
spans = [(0.0, 2.0), (2.4, 4.0), (4.4, 6.2), (6.6, 8.0)]
words = [{"w": "Namaste", "s": 0.1, "e": 0.6}, {"w": "Wow", "s": 2.5, "e": 2.9}]
spec = director.build_spec(sc, series, fmt, "en", spans, words, 9.5, 1, "16:9", "k")
ids = [c["id"] for c in spec["cast"]]
check("the cast is the speakers (the narrator is not on screen)", ids == ["chintu", "bhalu"])
check("the world follows the setting", spec["world"]["preset"] == "forest_autumn")
check("the first scene starts with someone walking in", any(c.get("enter") for c in spec["cast"]))
check("a greeting makes the speaker wave", any(a["type"] == "wave" and a["who"] == "chintu" for a in spec["actions"]))
check("listeners share a surprise", any(e["who"] == "chintu" and e["emo"] == "surprised" for e in spec["emotions"]))
check("a happy ending makes everyone jump", sum(a["type"] == "jump" for a in spec["actions"]) == 2)
sh = spec["shots"]
check("shots cover the whole scene without gaps", sh[0]["t0"] == 0 and sh[-1]["t1"] == 9.5 and
      all(abs(a["t1"] - b["t0"]) < 1e-6 for a, b in zip(sh, sh[1:])))
check("no shot is shorter than 1.5 s (except a closing one)", all(s["t1"] - s["t0"] >= 1.5 for s in sh[:-1]))
check("lip-sync words know who says them", spec["words"][0]["who"] == "chintu" and spec["words"][1]["who"] == "bhalu")
horror = director.pick_world({"setting": "old house"}, formats.get("horror"), {}, 1)
check("horror is dark", horror["mood"] in ("dark", "night"))
check("hindi settings pick worlds", director.pick_world({"setting": "गाँव का बाज़ार"}, fmt, {}, 2)["preset"] == "bazaar"
      and director.pick_world({"setting": "गाँव की गली"}, fmt, {}, 2)["preset"] == "village"
      and director.pick_world({"setting": "शहर की सड़क"}, fmt, {}, 2)["preset"] == "city_street")
check("narrated scenes still show the stars", [c["id"] for c in director.build_spec(
    production.normalize_scene({"dialogue": "Once upon a time."}, series, fmt), series, fmt, "en", [(0, 2)], [], 3, 2, "16:9")["cast"]]
    == ["bhalu", "chintu"])


# ---------------------------------------------------------------- a real render
def fake_lines(lines, out_audio, gap=0.35):
    t, words, spans = 0.0, [], []
    for ln in lines:
        d = max(0.8, min(2.5, len(ln["text"]) * 0.05))
        ws = ln["text"].split()
        for i, w in enumerate(ws):
            words.append({"w": w, "s": round(t + d * i / len(ws), 3), "e": round(t + d * (i + 1) / len(ws), 3)})
        spans.append((t, t + d))
        t += d + gap
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=300:duration={t:.2f}",
                    "-c:a", "libmp3lame", str(out_audio)], check=True, creationflags=concat.NO_WINDOW)
    return words, spans


if not anim3d.available():
    print("SKIP the render: no Chrome or Edge on this machine")
else:
    for fid in ("kids_3d", "horror"):
        s2 = dict(series, format=fid, id=f"t-{fid}")
        script = {"title": "Test", "scenes": [
            {"setting": "village market" if fid == "kids_3d" else "old house at night", "lines": [
                {"speaker": "Chintu", "text": "Hello Bhalu!", "emotion": "happy"},
                {"speaker": "Bhalu", "text": "What is that sound?", "emotion": "scared"}]}]}
        ep_dir = data / fid
        with patch.object(tts, "synthesize_lines", side_effect=fake_lines):
            res = production.build_episode(s2, 1, script, ep_dir)
        m = json.loads((ep_dir / "scene_01.json").read_text())
        check(f"{fid}: the scene was rendered in 3D", m["providers"] == ["anim3d"])
        check(f"{fid}: the master video is made", res["ok"] and res["master"].is_file())
        spec = json.loads((ep_dir / "scene_01.scene.json").read_text())
        check(f"{fid}: the 3D scene spec is saved next to it", spec["cast"] and spec["shots"])
        probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(res["master"])],
                                          capture_output=True, text=True, creationflags=concat.NO_WINDOW).stdout)
        v = next(x for x in probe["streams"] if x["codec_type"] == "video")
        check(f"{fid}: the small test render is scaled to 1920x1080", (v["width"], v["height"]) == (1920, 1080))
    pj = data / "portrait.jpg"
    check("a character portrait renders for the vault", anim3d.portrait(series["characters"][0], fmt, pj) and pj.stat().st_size > 5000)
    with patch.dict(os.environ, {"PEAKCUT_3D": "0"}):
        check("PEAKCUT_3D=0 turns 3D off", not anim3d.enabled_for(fmt))

print("ALL PASS")
