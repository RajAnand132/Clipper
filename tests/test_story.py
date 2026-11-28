"""Story visuals (studio/anim3d/story.py, director.py, web/studio3d/story.js): what the lines talk about is shown.

    python tests/test_story.py

Offline. The render checks need Chrome or Edge (they are skipped without one)."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
data = Path(tempfile.mkdtemp(prefix="peakcut-story-"))
os.environ["PEAKCUT_DATA"] = str(data)

from studio import formats, production  # noqa: E402
from studio.anim3d import director, story, worker  # noqa: E402


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def cues(text, speaker="Narrator", show=None):
    ws = [{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.3} for i, w in enumerate(text.split())]
    ln = {"text": text, "speaker": speaker}
    if show:
        ln["show"] = show
    return [(c["name"], c["how"]) for c in story.find_cues([ln], [(0, len(ws) * 0.4)], ws, 20)]


# ---------------------------------------------------------------- finding what to show
check("'stars falling' (English) → falling stars in the sky", cues("Why are the stars falling from the sky?") == [("falling_stars", "sky")])
check("'तारे गिर रहे' (Hindi) → falling stars", cues("आसमान से तारे क्यों गिर रहे हैं?") == [("falling_stars", "sky")])
check("stars without falling → a starry sky", cues("look at the stars tonight") == [("stars", "sky")])
check("'गाड़ी' → a car drives in", cues("वो गाड़ी आ रही है!", "Chintu") == [("car", "drive")])
check("a memory → a thought bubble", cues("याद है, पापा की पतंग?", "Chintu") == [("kite", "bubble")])
check("the narrator's memories are shown in the scene, not in a bubble", cues("He remembered the kite", "Narrator") == [("kite", "fly")])
check("rain and lightning together", cues("बारिश होने लगी और बिजली कड़की") == [("rain", "around"), ("lightning", "sky")])
check("a shining thing → a glowing orb", cues("अरे, वो चमकती हुई चीज़ क्या है?", "Chintu") == [("orb", "float")])
check("look-alike words show nothing (कारण, सरकार, बस)", cues("कारण यह है कि सरकार ने बस कहा") == [])
check("the script can ask for a thing", cues("Look over there!", "Maya", show=[{"thing": "a red balloon", "how": "enter"}])
      == [("balloons", "fly")])
many = cues("a car a ball a cake a gift a book and rain and fireworks and the moon")
check("at most 3 things and 2 happenings per scene", sum(1 for n, h in many if h in ("drive", "drop", "pop", "fly", "float")) <= 3
      and sum(1 for n, h in many if h in ("sky", "around")) <= 2)

# ---------------------------------------------------------------- the Director places and times it
series = {"id": "t", "format": "kids_3d", "characters": [
    {"name": "Chintu", "species": "Little Boy", "visual_anchor": "little boy, orange cap"},
    {"name": "Bhalu", "species": "Brown Bear", "visual_anchor": "big brown bear, red scarf"}]}
fmt = formats.resolve(series)
sc = production.normalize_scene({"setting": "jungle at night", "lines": [
    {"speaker": "Chintu", "text": "आसमान से तारे क्यों गिर रहे हैं?", "emotion": "surprised"},
    {"speaker": "Bhalu", "text": "देखो, वो गाड़ी आ रही है!", "emotion": "excited"},
    {"speaker": "Chintu", "text": "याद है, पापा की पतंग?", "emotion": "happy"}]}, series, fmt, "hi")
spans, words, t = [], [], 0.3
for ln in sc["lines"]:
    s0 = t
    for w in ln["text"].split():
        words.append({"w": w, "s": round(t, 2), "e": round(t + 0.38, 2)})
        t += 0.42
    spans.append((s0, t))
    t += 1.6
total = t + 1.0
spec = director.build_spec(sc, series, fmt, "hi", spans, words, total, 2, "16:9", "x", size=(640, 360), fps=12)
st = spec["story"]
check("the spec carries the falling stars, the car and the kite bubble",
      [f["name"] for f in st["fx"]] == ["falling_stars"] and [(p["name"], p["how"]) for p in st["props"]] == [("car", "drive"), ("kite", "bubble")])
kinds = [s["kind"] for s in spec["shots"]]
check("the camera looks up at the sky, cuts to the car and to the bubble", "sky" in kinds and "insert" in kinds and "bubble" in kinds)
sky = next(s for s in spec["shots"] if s["kind"] == "sky")
check("the sky shot comes at the word 'तारे'", abs(sky["t0"] - (st["fx"][0]["t0"] - 0.1)) < 0.01)
shots = spec["shots"]
check("the shots still cover the scene with no gaps", shots[0]["t0"] == 0 and abs(shots[-1]["t1"] - total) < 0.01
      and all(abs(a["t1"] - b["t0"]) < 1e-6 for a, b in zip(shots, shots[1:])))
xs = [c["x"] for c in spec["cast"]]
car = st["props"][0]
check("the car parks outside the characters, never between them", car["x"] < min(xs) or car["x"] > max(xs))
check("everyone looks up at the stars, and at the car", any("at" in l for l in st["looks"]) and any(l.get("prop") == car["id"] for l in st["looks"]))
check("the listener reacts with surprise", any(e["emo"] == "surprised" and e["who"] != "chintu" for e in spec["emotions"]))

# ---------------------------------------------------------------- it renders
if worker.available():
    with worker.Browser() as b:
        ok = b.render(spec, data / "story.mp4")
    check("a scene with stars, a car and a bubble renders", ok and (data / "story.mp4").stat().st_size > 10000)
    every = [{"id": f"p{i}", "name": n, "how": "pop", "t0": 0, "t1": 9, "x": -8 + (i % 9) * 2, "z": 2 - (i // 9) * 2}
             for i, (n, _p, k, _h) in enumerate(story.LEXICON) if k == "prop"]
    fx = [{"name": n, "t0": 0.1, "t1": 9} for n in ("falling_stars", "fireworks", "rainbow", "moon", "sun", "birds", "butterflies",
                                                    "sparkles", "rain", "snowfall", "lightning", "wind", "stars")]
    gal = {"w": 640, "h": 360, "fps": 12, "duration": 3, "seed": 2, "fov": 50, "world": {"preset": "forest_green", "mood": "night"},
           "cast": [], "lines": [], "words": [], "actions": [], "emotions": [], "shots": [{"kind": "sky", "t0": 0, "t1": 3}],
           "story": {"props": every, "fx": fx, "looks": []}}
    with worker.Browser() as b:
        ok = b.snapshot(gal, 1.2, data / "all.jpg")
    check(f"all {len(every)} things and {len(fx)} happenings build and render together", ok)
else:
    print("SKIP render checks: no Chrome or Edge")
# ---------------------------------------------------------------- places named in a line
check("a temple, a haveli and a mountain are places", story.place_named("मंदिर")[0] == "temple"
      and story.place_named("हवेली")[0] == "haveli" and story.place_named("पहाड़")[0] == "mountain" and story.place_named("घर") is None)


kids = formats.get("kids_3d")


def place_spec(setting, text, speaker="Narrator"):
    sc = production.normalize_scene({"setting": setting, "lines": [{"speaker": speaker, "text": text}]}, {"default_language": "hi"}, kids, "hi")
    words, t = [], 0.3
    for w in text.split():
        words.append({"w": w, "s": round(t, 2), "e": round(t + 0.36, 2)})
        t += 0.42
    return director.build_spec(sc, {"default_language": "hi"}, kids, "hi", [(0.3, t)], words, t + 3, 2, "16:9", "x",
                               size=(320, 180), fps=12)


here = place_spec("मंदिर का आँगन, सुबह", "यह मंदिर बहुत पुराना और सुंदर है")
check("in the temple, naming it turns the camera to it", any(s["kind"] == "landmark" and s.get("at") for s in here["shots"])
      and not [p for p in here["story"]["props"] if p["name"].startswith("place_")])
away = place_spec("गाँव की गली, सुबह", "देखो वहाँ दूर एक मंदिर है")
far = [p for p in away["story"]["props"] if p["name"] == "place_temple"]
check("in the village, a temple named appears far off, with a shot of it", far and far[0]["how"] == "far"
      and any(s["kind"] == "landmark" and s.get("target") == far[0]["id"] for s in away["shots"]))
inside = place_spec("रसोई", "कल हम मंदिर जाएँगे", "चिंटू")
check("indoors it is a thought bubble", [p["how"] for p in inside["story"]["props"] if p["name"] == "place_temple"] == ["bubble"])
if worker.available():
    with worker.Browser() as b:
        ok = b.snapshot(away, 2.0, data / "far_temple.jpg") and b.snapshot(here, 1.5, data / "temple_landmark.jpg")
        every = {"w": 640, "h": 360, "fps": 12, "duration": 3, "seed": 2, "fov": 46, "world": {"preset": "field", "mood": "day"},
                 "cast": [], "lines": [], "words": [], "actions": [], "emotions": [], "shots": [{"kind": "wide", "t0": 0, "t1": 3}],
                 "story": {"props": [{"id": f"p{i}", "name": "place_" + n, "how": "far", "t0": 0, "t1": 3, "x": -30 + i * 4, "z": -22}
                                     for i, (n, _r, _k) in enumerate(story.PLACES)], "fx": [], "looks": []}}
        ok = ok and b.snapshot(every, 1.5, data / "all_places.jpg")
    check(f"all {len(story.PLACES)} places build and render", ok)
print("ALL PASS")
