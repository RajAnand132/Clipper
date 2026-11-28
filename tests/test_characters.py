"""Any kind of character (studio/anim3d/characters.py, web/studio3d/parts.js, the AI designer in studio/concepts.py).

    python tests/test_characters.py

Offline: the word rules, the design cleaner, the AI designer (with a stand-in AI) and a render of every part on
every body (needs Chrome or Edge; skipped without one)."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, ".")
data = Path(tempfile.mkdtemp(prefix="peakcut-chars-"))
os.environ["PEAKCUT_DATA"] = str(data)

from studio import ai, concepts, formats  # noqa: E402
from studio.anim3d import characters as ch, worker  # noqa: E402


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


fmt = formats.get("kids_3d")


def design(name, species, look=""):
    return ch.design_for({"name": name, "species": species, "visual_anchor": look}, fmt)


def parts(d):
    return {p["part"] for p in d.get("parts", [])}


# ---------------------------------------------------------------- the word rules: many kinds, no niche list
v = design("Virat", "Batsman", "young man in white cricket uniform, blue helmet, holding a bat")
check("a batsman: adult, helmet, pads, gloves, bat ('holding' is not 'old')",
      v["type"] == "human" and v["age"] == "adult" and {"cricket_helmet", "leg_pads", "gloves"} <= parts(v) and v["hold"] == "bat")
bw = design("Shami", "Fast Bowler", "tall man, blue India cricket kit")
kp = design("Pant", "Wicketkeeper Batsman", "young man, blue India cricket kit")
check("a team is not copies: the bowler holds the ball (no pads), the keeper has gloves, blue kit as described",
      bw["hold"] == "ball" and "leg_pads" not in parts(bw) and "gloves" in parts(kp) and bw["top"] == ch.COLORS["blue"])
check("a doctor gets a lab coat and stethoscope, not a police cap ('stethoscope' has 'cop' in it)",
      parts(design("Maya", "Doctor", "woman in white coat, stethoscope")) == {"lab_coat", "stethoscope"})
k = design("Raja", "King", "king with golden crown, red robe")
check("a king is a person with a crown and cape ('crown' is not 'crow')", k["type"] == "human" and k.get("hat") == "crown" and "cape" in parts(k))
z = design("Raju", "Zombie", "green skin zombie, torn clothes")
check("a zombie: green skin, rags, zombie walk, no kids' cap", z["pose"] == "zombie" and "rags" in parts(z) and "hat" not in z
      and z["skin"] == "#8fb07a")
check("a ghost floats and is see-through", design("Bhoot", "Ghost")["effect"] == "ghostly")
w = design("Churail", "Witch")
check("a witch: pointed hat, robe, broom", {"witch_hat", "robe"} <= parts(w) and w["hold"] == "broom")
m = design("Jalpari", "Mermaid", "mermaid with teal fish tail")
check("a mermaid is a woman with a fish tail (not a fish, not a fairy)", m["type"] == "human" and m["gender"] == "f"
      and "fish_tail" in parts(m) and "wings_fairy" not in parts(m))
f = design("Pari", "Fairy")
check("a fairy: wings, wand, a girl", f["hold"] == "wand" and f["gender"] == "f" and "wings_fairy" in parts(f))
dr = design("Draco", "Dragon")
check("a dragon has wings, horns and a dragon tail", dr["tail"] == "dragon" and "wings_bat" in parts(dr))
check("a crocodile is an animal with a long toothy snout", design("Tinku", "Crocodile")["snout"] == "croc")
check("a snake has no legs or arms", design("Nag", "Snake", "green cobra")["legs"] is False)
check("a zebra has stripes", design("Zebu", "Zebra")["pattern"] == "stripes")
check("one helmet and one set of wings at most", len(parts(v) & ch.EXCLUSIVE[0]) == 1
      and len(parts(design("Tara", "Angel", "angel with white wings")) & ch.EXCLUSIVE[1]) == 1)
cape = next(p for p in design("Cap", "Superhero", "superhero with red cape")["parts"] if p["part"] == "cape")
check("a colour named for a piece goes on it ('red cape')", cape.get("color") == ch.COLORS["red"])

# ---------------------------------------------------------------- designs from the AI are cleaned
t = ch.clean_toon({"body": "animal", "fur": "orange", "tail": "rocket-powered",
                   "parts": [{"part": "space_helmet", "color": "navy"}, {"part": "laser_cannon"}], "hold": "rocket",
                   "pose": "moonwalk", "height": 9})
check("the cleaner keeps what can be built and drops the rest",
      t == {"type": "animal", "fur": "#ff8a1f", "parts": [{"part": "space_helmet", "color": "#1f2a44"}], "hold": "rocket"})
ball = ch.design_for({"name": "Gendu", "species": "Cricket Ball", "visual_anchor": "a living red cricket ball",
                      "toon": {"body": "blob", "top": "#d32f2f", "parts": []}}, fmt)
check("when the designer picks another body, the word rules' costume goes (a ball, not a batsman)",
      ball["type"] == "critter" and not ball.get("parts") and "hold" not in ball and ball["body"] == "#d32f2f")
cat = ch.catalog()
check("the designer may use 70+ parts and 50+ things to hold", len(cat["parts"]) >= 70 and len(cat["hold"]) >= 50)


def fake_ai(model, prompt, schema, **k):
    return ([{"name": "Gendu", "body": "blob", "top": "red", "parts": [{"part": "headband", "color": "white"}], "hold": "",
              "pose": "normal", "effect": "none", "eyes": "big"}], 1, 1)


with patch.object(ai, "ready", return_value=True), patch.object(ai, "models", return_value=["m"]), \
        patch.object(ai, "call", side_effect=fake_ai):
    cs = [{"name": "Gendu", "species": "Cricket Ball", "visual_anchor": "living red ball"}]
    concepts.attach_designs(cs, fmt)
check("the AI designer's design is stored on the character", cs[0].get("toon", {}).get("type") == "critter"
      and cs[0]["toon"]["parts"] == [{"part": "headband", "color": "#f4f4f4"}])
with patch.object(ai, "ready", return_value=False):
    cs2 = [{"name": "X", "species": "Owl"}]
    concepts.attach_designs(cs2, fmt)
check("without an AI nothing breaks: the word rules design it at render time", "toon" not in cs2[0])

# ---------------------------------------------------------------- the AI design adds to the look, it does not replace it
st = ch.design_for({"name": "Sutrakaar", "species": "Sacred Narrator", "visual_anchor": "elderly storyteller, holding a glowing clay lamp",
                    "toon": {"type": "human", "effect": "glowing", "eyes": "glowing", "pose": "float", "parts": [{"part": "beard"}], "hold": "lantern"}}, fmt)
check("a storyteller with a glowing lamp does not glow all over, float or get glowing eyes",
      "effect" not in st and st.get("eyes") != "glowing" and st.get("pose") != "float" and st["hold"] == "lantern")
vb = ch.design_for({"name": "Veer", "species": "Young Hero", "visual_anchor": "spirited 3d indian cartoon boy, crimson cape",
                    "toon": {"type": "critter"}}, fmt)
check("a 'spirited boy' stays a boy (not a ghost), even if the designer says otherwise", vb["type"] == "human" and vb.get("effect") != "ghostly")
check("a Hindi bird (पक्षी) is a bird", design("पंखी", "जादुई पक्षी", "एक छोटा पक्षी जैसा प्राणी")["type"] == "animal")
g = design("Golu", "Baby Cloud Critter", "chubby baby cloud with tiny golden crown")
check("a cloud critter is a critter with a crown", g["type"] == "critter" and "crown" in parts(g))
gh = ch.design_for({"name": "Bhoot", "species": "Ghost", "toon": {"effect": "ghostly", "eyes": "glowing"}}, fmt)
check("a real ghost keeps its ghostly look", gh.get("effect") == "ghostly")

# ---------------------------------------------------------------- new look, named colours, the episode cast
base = {"name": "Chintu", "species": "little boy", "visual_anchor": "little boy"}
looks = {ch.design_for(dict(base, look_seed=n), fmt).get("top") for n in range(6)}
check("each look number gives other colours (New look without an AI)", len(looks) >= 3)
nc = ch.design_for({"name": "Chintu", "species": "little boy", "visual_anchor": "orange cap, blue shirt",
                    "toon": {"top": "#3f9a3a", "parts": [{"part": "beanie"}, {"part": "scarf"}], "hold": "kite"}}, fmt)
check("what the description names wins over a new look (orange cap, blue shirt)",
      nc["top"] == ch.COLORS["blue"] and nc.get("hat") == "cap" and nc.get("hatColor") == ch.COLORS["orange"]
      and "beanie" not in parts(nc) and nc.get("hold") == "kite")
from studio import production, storyteller  # noqa: E402
script = {"scenes": [{"lines": [{"speaker": "Bhalu", "text": "hi"}]}, {"dialogue": "Dadi: namaste"}]}
check("the script check finds a chosen character with no lines", storyteller.missing_cast(script, ["Bhalu", "Dadi", "Chintu"]) == ["Chintu"])
ser = {"characters": [{"name": "Chintu"}, {"name": "Bhalu"}, {"name": "Dadi"}]}
scs = [{"lines": [{"speaker": "Narrator", "text": "x"}]}, {"lines": [{"speaker": "Dadi", "text": "y"}]}]
production._episode_cast_on_screen(scs, {"cast": ["Dadi", "Bhalu"]}, ser)
check("a narrator-only scene shows the episode's chosen cast, not the first two of the Vault",
      scs[0].get("characters") == ["Dadi", "Bhalu"] and "characters" not in scs[1])
scs2 = [{"lines": [{"speaker": "Narrator", "text": "x"}]}, {"lines": [{"speaker": "Dadi", "text": "y"}, {"speaker": "Dadi", "text": "z"}]}]
production._episode_cast_on_screen(scs2, {}, ser)
check("without a chosen cast it shows whoever talks most in the episode", scs2[0].get("characters") == ["Dadi"])

# ---------------------------------------------------------------- episode titles come from the episode's story
ep = {"title": "Old Title", "summary": "Bhalu builds a bridge over the river", "featured_characters": ["Bhalu"],
      "script": [{"setting": "river bank, day", "lines": [{"speaker": "Bhalu", "text": "Let us build a bridge!"}]}]}
seen_prompt = {}


def fake_titles(model, prompt, schema, **k):
    seen_prompt["p"] = prompt
    return ({"titles": ["Old Title", "The River Bridge", "\u201cBhalu's Big Build\u201d", "The River Bridge"]}, 1, 1)


with patch.object(ai, "ready", return_value=True), patch.object(ai, "models", return_value=["m"]), \
        patch.object(ai, "call", side_effect=fake_titles):
    r = concepts.suggest_episode_titles({"title": "Bhalu", "format": "kids_3d", "characters": []}, ep)
check("episode titles come from the AI, from the episode's own story, without the current title or repeats",
      r["source"] == "ai" and r["titles"] == ["The River Bridge", "Bhalu's Big Build"] and "bridge over the river" in seen_prompt["p"])
with patch.object(ai, "ready", return_value=False):
    r2 = concepts.suggest_episode_titles({"title": "Bhalu", "characters": []}, ep)
check("without an AI the titles still use the episode's characters and places", r2["source"] == "builtin"
      and any("Bhalu" in t for t in r2["titles"]) and any("River Bank" in t for t in r2["titles"]))

# ---------------------------------------------------------------- the Director's Narrative is about this episode
from studio import memory, storyteller  # noqa: E402
horror = {"title": "Chalta Rasta", "format": "horror", "default_language": "en", "episodes": []}
with patch.object(memory, "get_series", return_value=horror), patch.object(ai, "ready", return_value=False):
    w1 = storyteller.build_narrative_walkthrough("x", {"title": "The Loop", "synopsis": "Karan is stuck on one road.",
        "walkthrough": {"why_this_episode": "Everyone has felt lost on a road at night.", "bridge_from_last": "It starts the story.",
                        "journey": "Karan keeps passing the same milestone.", "next_teaser": "Who is the woman at the crossing?"}}, 1)
    w2 = storyteller.build_narrative_walkthrough("x", {"title": "The Loop", "synopsis": "Karan is stuck."}, 1)
with patch.object(memory, "get_series", return_value=dict(horror, format="kids_3d")), patch.object(ai, "ready", return_value=False):
    w3 = storyteller.build_narrative_walkthrough("x", {"title": "Picnic", "synopsis": "A picnic."}, 1)
check("the script writer's notes for this episode are used as they are", w1["context_motivation"] == "Everyone has felt lost on a road at night."
      and w1["next_teaser"] == "Who is the woman at the crossing?" and w1["written_by"] == "script")
check("without an AI, the 'why' fits the kind of show (horror is not about kids' teamwork)",
      w2["context_motivation"] != w3["context_motivation"] and "fear" in w2["context_motivation"].lower())

# ---------------------------------------------------------------- scenes long enough for the length chosen
check("a 1-minute Hindi scene needs about 126 spoken words", storyteller.words_for(60, "hi") == 126)
short = {"scenes": [{"scene_num": 1, "lines": [{"speaker": "Bhalu", "text": "छोटा सा वाक्य"}]},
                    {"scene_num": 2, "lines": [{"speaker": "Dadi", "text": " ".join(["शब्द"] * 130)}]}]}


def fake_longer(model, prompt, schema, **k):
    return ({"scenes": [{"scene_num": 1, "lines": [{"speaker": "Bhalu", "text": " ".join(["नया"] * 120)}]}]}, 1, 1)


with patch.object(ai, "ready", return_value=True), patch.object(ai, "models", return_value=["m"]), \
        patch.object(ai, "call", side_effect=fake_longer):
    storyteller._lengthen_short_scenes(short, 60, "hi", "Bhalu", "")
check("a scene too short for its length gets its lines extended; a long enough one is left alone",
      storyteller.spoken_words(short["scenes"][0]) == 120 and storyteller.spoken_words(short["scenes"][1]) == 130
      and short["scenes"][0]["dialogue"].startswith("Bhalu:"))

# ---------------------------------------------------------------- every part and held thing builds on every body
if worker.available():
    bodies = [{"type": "human", "gender": "m", "age": "adult"}, {"type": "animal", **ch.ANIMALS["bear"]},
              {"type": "robot"}, {"type": "critter", "body": "#eef2ff"}]
    allparts = [{"part": p} for p in cat["parts"]]

    def spec(d, size):
        return {"w": size, "h": size, "fps": 30, "duration": 1, "seed": 1, "fov": 30, "world": {"preset": "room", "mood": "day"},
                "cast": [{"id": "c", "name": "t", "design": d, "x": 0, "z": 0, "yaw": 0}], "lines": [], "words": [],
                "actions": [], "emotions": [], "shots": [{"kind": "wide", "t0": 0, "t1": 5}]}
    ok = True
    with worker.Browser() as b:
        for i, body in enumerate(bodies):
            for j in range(0, len(allparts), 18):
                d = dict(body, parts=allparts[j:j + 18], hold=cat["hold"][(i * 7 + j) % len(cat["hold"])], pose="zombie",
                         effect="glowing")
                ok = ok and b.snapshot(spec(d, 240), 0.5, data / f"b{i}_{j}.jpg")
        for h in cat["hold"]:
            ok = ok and b.snapshot(spec({"type": "human", "hold": h}, 160), 0.5, data / f"h_{h}.jpg")
    check(f"all {len(allparts)} parts on all 4 bodies, and all {len(cat['hold'])} held things, render", ok)
else:
    print("SKIP render checks: no Chrome or Edge")
print("ALL PASS")
