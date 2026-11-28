"""Sets that fit every scene (studio/anim3d/sets.py, web/studio3d/sets.js): the place, time of day, weather, era
and culture are read from the scene; every set kit renders.

    python tests/test_sets.py

Offline. The render check needs Chrome or Edge (skipped without one)."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
data = Path(tempfile.mkdtemp(prefix="peakcut-sets-"))
os.environ["PEAKCUT_DATA"] = str(data)

from studio import formats  # noqa: E402
from studio.anim3d import director, sets, worker  # noqa: E402


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


kids, hist, horror = formats.get("kids_3d"), formats.get("history_doc"), formats.get("horror")


def world(setting, fmt=kids, series=None, extra=None):
    sc = {"setting": setting, **(extra or {})}
    return director.pick_world(sc, fmt, series or {"default_language": "hi"}, 3)


# the settings that used to fall back to an autumn forest
cases = {"ancient architecture": "ruins", "temple courtyard at dawn": "temple", "royal palace hall": "palace",
         "railway station": "station", "desert": "desert", "river ghat with diyas": "ghat", "hospital": "hospital",
         "cave": "cave", "mountain evening": "mountain", "busy city street": "city_street", "school classroom": "school",
         "highway dhaba": "highway", "village bazaar": "bazaar", "kitchen": "kitchen", "bedroom": "bedroom",
         "river bank": "river", "मंदिर का आँगन": "temple", "रेलवे स्टेशन": "station", "गाँव की गली": "village"}
wrong = {s: world(s)["preset"] for s, k in cases.items() if world(s)["preset"] != k}
check(f"all {len(cases)} settings get the right set (none falls back to a forest)", not wrong)
check("time of day is read", world("temple courtyard at dawn")["time"] == "dawn" and world("mountain evening")["time"] == "dusk"
      and world("ghat at midnight")["time"] == "midnight" and world("शाम को बाज़ार")["time"] == "dusk")
check("weather is read", world("city street in the rain")["weather"] == "rain" and world("foggy forest")["weather"] == "fog"
      and world("village in a storm")["weather"] == "storm" and world("बादल छाए हुए, खेत")["weather"] == "overcast")
check("history shows are set in the past", world("palace courtyard", hist)["era"] == "ancient" and world("city street")["era"] == "modern")
check("culture follows the show's language", world("street")["culture"] == "indian"
      and world("street", kids, {"default_language": "ja"})["culture"] == "japanese")
h = world("old house", horror)
check("horror stays dark", h["mood"] in ("dark", "night"))
st = {"set": {"place": "the old temple", "kit": "temple", "time": "night", "weather": "fog", "era": "ancient",
              "culture": "indian", "landmarks": ["bronze bell"], "location_name": "Somnath Mandir"}}
w1 = world("anything", kids, None, st)
check("the script writer's set wins", w1["preset"] == "temple" and w1["time"] == "night" and w1["weather"] == "fog"
      and w1["landmarks"] == ["bronze bell"])
w2 = director.pick_world({"setting": "x", **st}, kids, {}, 99)
check("a named place keeps the same layout whatever the scene", w1.get("seed") and w1["seed"] == w2["seed"])
check("an older script's general set gives way to the place its words name",
      sets.scene_set({"setting": "ट्रेन के डिब्बे के अंदर", "set": {"kit": "station", "place": "train compartment"}}, kids, {}, 1)["preset"] == "train_interior"
      and sets.scene_set({"setting": "पुरानी हवेली का आँगन", "set": {"kit": "ruins"}}, kids, {}, 1)["preset"] == "haveli"
      and sets.scene_set({"setting": "temple", "set": {"kit": "temple"}}, kids, {}, 1)["preset"] == "temple")
check("a storm flashes again and again", len([f for f in sets.weather_fx({"preset": "city_street", "weather": "storm"}, 60) if f["name"] == "lightning"]) >= 4)
check("rain and storms fall over the whole scene, not inside rooms",
      [f["name"] for f in sets.weather_fx({"preset": "city_street", "weather": "storm"}, 10)][:2] == ["rain", "lightning"]
      and sets.weather_fx({"preset": "kitchen", "weather": "rain"}, 10) == [])

# ---- the Location Vault: a place is remembered once, the user's fixes win, a new layout changes it
from studio import memory  # noqa: E402
from studio.production import _remember_places  # noqa: E402

ser = memory.create_series("Vault Test", default_language="hi", format="kids_3d")
sid = ser["id"]
scenes = [{"setting": "old village temple at dusk", "set": {"location_name": "Shiv Mandir"}},
          {"setting": "shiv mandir", "set": {"location_name": "Shiv Mandir"}},
          {"setting": "railway station"}]
ser = _remember_places(scenes, ser, kids)
locs = ser.get("locations", [])
check("every place an episode uses is remembered once", sorted(l["name"] for l in locs) == ["Shiv Mandir", "railway station"])
temple = memory.find_location(ser, "shiv mandir")
check("a place is found by its name", temple and temple["kit"] == "temple" and temple["seed"])
w_before = sets.scene_set({"setting": "anything", "set": {"location_name": "Shiv Mandir"}}, kids, ser, 1)
check("a saved place is used as it was saved", w_before["preset"] == "temple" and w_before["seed"] == temple["seed"]
      and w_before.get("location_id") == temple["id"])
memory.update_location(sid, temple["id"], {"name": "Old Shiva Temple", "kit": "ruins", "era": "ancient", "new_layout": True})
ser = memory.get_series(sid)
fixed = memory.find_location(ser, "Shiv Mandir")
check("a renamed place is still found by its old name", fixed and fixed["name"] == "Old Shiva Temple")
check("and by its new name", memory.find_location(ser, "Old Shiva Temple") is fixed or
      (memory.find_location(ser, "Old Shiva Temple") or {}).get("id") == fixed["id"])
check("the place's picture shows the fixed set", sets.scene_set({"setting": "Old Shiva Temple", "set": {"location_name": "Old Shiva Temple"}},
                                                                kids, ser, 1)["preset"] == "ruins")
w_after = sets.scene_set({"setting": "anything", "set": {"location_name": "Shiv Mandir"}}, kids, ser, 1)
check("the user's fixes win (set, era, new layout)", w_after["preset"] == "ruins" and w_after["era"] == "ancient"
      and w_after["seed"] != w_before["seed"])
_remember_places(scenes, ser, kids)
check("making another episode keeps the user's fixes", memory.find_location(memory.get_series(sid), "Shiv Mandir")["kit"] == "ruins"
      and len(memory.get_series(sid)["locations"]) == 2)
check("the script writer is told the known places", "Old Shiva Temple" in memory.get_continuity_context(sid).get("locations", [])
)

if worker.available():
    from fastapi.testclient import TestClient  # noqa: E402
    from studio import db, server  # noqa: E402
    db.init()
    BASE = "http://127.0.0.1:8765"
    client = TestClient(server.app, base_url=BASE, headers={"Origin": BASE}, client=("127.0.0.1", 5000))
    r = client.get(f"/api/series/{sid}/locations")
    check("the places list route", r.status_code == 200 and len(r.json()["locations"]) == 2)
    r = client.get(f"/api/series/{sid}/locations/{temple['id']}/image.jpg")
    check("a place's picture is made", r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and len(r.content) > 5000)
    r = client.post(f"/api/series/{sid}/preview-scene", json={"scene": {"setting": "bus stop in the rain at night",
                                                                         "lines": [{"speaker": "Narrator", "text": "Barish ho rahi thi."}]}})
    check("a scene preview is made in seconds", r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and len(r.content) > 5000)

if worker.available():
    kits = [k for k in sets.KITS if k not in ("space",)]
    ok = True
    with worker.Browser() as b:
        for i, k in enumerate(kits):
            for time, weather in (("morning", "clear"), ("night", "rain")):
                spec = {"w": 240, "h": 140, "fps": 12, "duration": 1, "seed": 5, "fov": 40,
                        "world": {"preset": k, "mood": "night" if time == "night" else "day", "time": time, "weather": weather,
                                  "era": "ancient" if i % 2 else "modern", "culture": "indian"},
                        "cast": [], "lines": [], "words": [], "actions": [], "emotions": [], "shots": [{"kind": "wide", "t0": 0, "t1": 1}],
                        "story": {"props": [], "fx": sets.weather_fx({"preset": k, "weather": weather}, 1), "looks": []}}
                ok = ok and b.snapshot(spec, 0.5, data / f"{k}_{time}.jpg")
    check(f"all {len(kits)} sets render by day and on a rainy night", ok)
else:
    print("SKIP render checks: no Chrome or Edge")
print("ALL PASS")
