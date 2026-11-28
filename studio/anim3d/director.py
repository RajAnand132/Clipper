"""Director: turns one script scene (lines, emotions, voice timings) into the 3D scene spec the runtime plays.

The AI only says WHAT happens (who speaks, with which feeling, where). The Director decides HOW it looks:
who stands where, who walks in, gestures and reactions, faces, lip-sync words, the world, and the shot list
(establishing shot, close-ups, over-the-shoulder, two-shots, cuts on speaker changes, never faster than 1.5 s).
"""
from __future__ import annotations

import hashlib
import re

from studio.anim3d import characters as toon
from studio.anim3d import story as storyfx

MIN_SHOT = 1.5

WORLD_RULES = [  # (pattern on setting/prompt text, preset)
    (r"space|planet|rocket|galaxy|moon base|alien|अंतरिक्ष|ग्रह|रॉकेट", "space"),
    (r"snow|winter|ice|frozen|igloo|बर्फ|सर्दी", "snow"),
    (r"beach|sea|ocean|shore|island|समुद्र|बीच|सागर|किनारे", "beach"),
    (r"room|house inside|home|kitchen|bedroom|class|school|indoor|library|shop inside|कमरा|कमरे|घर के अंदर|रसोई|स्कूल|कक्षा", "room"),
    (r"stadium|cricket|lord'?s|\bpitch\b|crease|wicket|boundary|pavilion|football field|match ground|"
     r"स्टेडियम|क्रिकेट|मैदान|पिच|विकेट", "stadium"),
    (r"village|town|market|street|bazaar|city|गाँव|गांव|बाज़ार|बाजार|शहर|गली|मोहल्ला|dholakpur", "village"),
    (r"farm|barn|field|orchard|खेत|बाड़ा|बगीचा", "farm"),
    (r"autumn|fall leaves|पतझड़", "forest_autumn"),
    (r"forest|jungle|wood|tree|park|garden|river|lake|mountain|hill|meadow|जंगल|पेड़|नदी|पहाड़|झील|उद्यान|पार्क", "forest_green"),
]


def _h(*parts) -> int:
    return int(hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:8], 16)


def pick_world(sc: dict, fmt: dict, series: dict, seed: int) -> dict:
    """The set of the scene: place, time of day, weather, era and culture (studio/anim3d/sets.py)."""
    from studio.anim3d import sets
    return sets.scene_set(sc, fmt, series, seed)


def _cast_for(sc: dict, series: dict, fmt: dict) -> list[dict]:
    vault = {c.get("name", "").strip().lower(): c for c in series.get("characters", []) if c.get("name")}
    names: list[str] = []
    for ln in sc.get("lines", []):
        n = (ln.get("speaker") or "").strip()
        if n and n.lower() != "narrator" and n.lower() not in [x.lower() for x in names]:
            names.append(n)
    for n in sc.get("characters", []) or []:
        n = str(n).strip()
        if n and n.lower() != "narrator" and n.lower() not in [x.lower() for x in names]:
            names.append(n)
    if not names:   # narrated scene: show the stars of the show reacting
        names = [c.get("name") for c in series.get("characters", [])[:2] if c.get("name")]
    if not names:
        names = ["Friend"]
    cast = []
    for n in names[:4]:
        c = vault.get(n.lower()) or {"name": n, "species": "", "visual_anchor": ""}
        cast.append({"id": re.sub(r"\W+", "_", n.lower()).strip("_") or "c", "name": n, "design": toon.design_for(c, fmt)})
    return cast


def _place(cast: list[dict]) -> None:
    n = len(cast)
    widths = [1.9 * float(c["design"].get("scale", 1)) + 0.7 for c in cast]
    total = sum(widths)
    x = -total / 2
    for i, c in enumerate(cast):
        c["x"] = round(x + widths[i] / 2, 3)
        x += widths[i]
        c["z"] = round(-0.25 * abs(i - (n - 1) / 2), 3)
    cx = 0.0
    for c in cast:   # face the middle, cheated towards the camera like TV cartoons do
        c["yaw"] = 0.0 if n == 1 else (0.75 if c["x"] < cx - 0.2 else (-0.75 if c["x"] > cx + 0.2 else 0.0))


GREET = re.compile(r"hello|hi\b|hey|bye|goodbye|welcome|namaste|नमस्ते|नमस्कार|हेलो|हाय|अलविदा|टाटा|स्वागत", re.I)
QUESTION = re.compile(r"\?|क्या |कैसे|क्यों|कौन|कहाँ|कब ")
EMPHASIS = re.compile(r"!|wow|yay|hurray|amazing|वाह|अरे|हुर्रे|शाबाश|ज़बरदस्त|कमाल")


def build_spec(sc: dict, series: dict, fmt: dict, lang: str, spans: list, words: list, total: float, idx: int,
               aspect: str, seed_key: str = "", size: tuple[int, int] = (1920, 1080), fps: int = 30) -> dict:
    seed = _h(seed_key, idx)
    cast = _cast_for(sc, series, fmt)
    _place(cast)
    ids = {c["name"].lower(): c["id"] for c in cast}
    lines = []
    for ln, sp in zip(sc.get("lines", []), spans):
        who = ids.get((ln.get("speaker") or "").strip().lower())
        lines.append({"who": who, "s": float(sp[0]), "e": float(sp[1]), "emotion": str(ln.get("emotion") or "").lower(),
                      "text": ln.get("text", "")})
    spoken = [{"w": w["w"], "s": w["s"], "e": w["e"],
               "who": next((l["who"] for l in lines if l["s"] - 0.02 <= w["s"] <= l["e"] + 0.02), None)} for w in words]
    spoken = [w for w in spoken if w["who"]]

    # entrance: the first scene of an episode, and about a third of the others, start with someone walking in
    first_talker = next((l["who"] for l in lines if l["who"]), cast[0]["id"])
    if idx == 1 or seed % 3 == 0:
        c = next(x for x in cast if x["id"] == first_talker)
        side = -1 if c["x"] <= 0 else 1
        c["enter"] = {"from_x": round(c["x"] + side * 7.5, 2), "t0": 0.0, "t1": round(min(2.4, max(1.4, total * 0.25)), 2)}

    actions, emotions = [], []
    for i, l in enumerate(lines):
        who, emo = l["who"], l["emotion"]
        if who and emo:
            emotions.append({"who": who, "t0": l["s"], "t1": l["e"] + 0.25, "emo": emo})
        if who and GREET.search(l["text"]):
            actions.append({"who": who, "type": "wave", "t0": l["s"], "t1": min(l["e"], l["s"] + 1.4)})
        elif who and emo in ("happy", "excited") and EMPHASIS.search(l["text"]):
            actions.append({"who": who, "type": "bounce", "t0": l["s"], "t1": min(l["e"], l["s"] + 1.2)})
        elif who and QUESTION.search(l["text"]) and (seed + i) % 2 == 0:
            actions.append({"who": who, "type": "shrug", "t0": l["e"] - 0.8, "t1": l["e"]})
        elif who and emo in ("mysterious", "whisper"):
            actions.append({"who": who, "type": "look_around", "t0": l["s"], "t1": l["e"]})
        elif who and (seed + i) % 4 == 1:
            actions.append({"who": who, "type": "point", "t0": l["s"] + 0.3, "t1": min(l["e"], l["s"] + 1.6)})
        for other in cast:   # listeners react
            if other["id"] == who:
                continue
            if emo in ("surprised", "scared"):
                emotions.append({"who": other["id"], "t0": l["s"] + 0.3, "t1": l["e"] + 0.3, "emo": emo})
            elif emo in ("happy", "excited") and (seed + i) % 2 == 0:
                actions.append({"who": other["id"], "type": "nod", "t0": l["s"] + 0.4, "t1": l["s"] + 1.4})
            elif emo == "sad":
                emotions.append({"who": other["id"], "t0": l["s"] + 0.5, "t1": l["e"], "emo": "sad"})
        if not who and i % 2 == 0:   # narrator speaking: the cast is alive anyway
            for j, other in enumerate(cast):
                actions.append({"who": other["id"], "type": "look_around" if j % 2 == 0 else "think",
                                "t0": l["s"] + 0.2, "t1": min(l["e"], l["s"] + 2.6)})
    tail = lines[-1]["e"] if lines else 0
    last_emo = lines[-1]["emotion"] if lines else ""
    if last_emo in ("happy", "excited") and total - tail > 0.4:
        for c in cast:
            actions.append({"who": c["id"], "type": "jump", "t0": tail + 0.05, "t1": total})

    # shots
    shots: list[dict] = []
    est_end = min(max(1.8, lines[0]["e"] if lines else total), 3.2, total)
    shots.append({"kind": "establish", "t0": 0.0, "t1": est_end})
    kinds = ["close", "ots", "two", "close", "two", "ots"]
    for i, l in enumerate(lines):
        t0 = max(0.0, l["s"] - 0.12)
        if t0 < shots[-1]["t0"] + MIN_SHOT:
            continue
        if l["who"] and len(cast) > 1:
            other = next((c["id"] for c in cast if c["id"] != l["who"]), None)
            k = kinds[(seed + i) % len(kinds)]
            shots.append({"kind": k, "t0": t0, "target": l["who"], "other": other})
        elif l["who"]:
            shots.append({"kind": "close" if i % 2 else "wide", "t0": t0, "target": l["who"]})
        else:
            shots.append({"kind": "wide", "t0": t0})
    if last_emo in ("happy", "excited") and total - tail > 1.0 and tail - shots[-1]["t0"] >= MIN_SHOT:
        shots.append({"kind": "pull", "t0": tail})
    for i, s in enumerate(shots):
        s["t1"] = shots[i + 1]["t0"] if i + 1 < len(shots) else total
        s["t0"], s["t1"] = round(s["t0"], 3), round(s["t1"], 3)
    shots = [s for s in shots if s["t1"] - s["t0"] > 0.05]

    world = pick_world(sc, fmt, series, seed)
    # what the narration talks about, on screen at the word (studio/anim3d/story.py, web/studio3d/story.js)
    story, shots = _story(sc, cast, lines, spans, words, total, shots, emotions, actions, world)

    from studio.anim3d import sets as _sets   # rain, snow or a storm over the whole scene
    have = {f["name"] for f in story.get("fx", [])}
    story["fx"] = story.get("fx", []) + [f for f in _sets.weather_fx(world, total) if f["name"] not in have]
    night = world["mood"] in ("night", "dark") or world.get("time") in ("night", "midnight")
    w, h = size
    return {
        "w": w, "h": h, "fps": fps, "duration": round(total, 3), "seed": seed,
        "world": world,
        "cast": [{"id": c["id"], "name": c["name"], "design": c["design"], "x": c["x"], "z": c["z"], "yaw": c["yaw"],
                  "enter": c.get("enter"), "night_rim": night} for c in cast],
        "lines": [{"who": l["who"], "s": l["s"], "e": l["e"]} for l in lines],
        "words": spoken, "actions": actions, "emotions": emotions, "shots": shots, "story": story,
        "fov": 36 if aspect == "16:9" else 50,
    }


def _story(sc: dict, cast: list, lines: list, spans: list, words: list, total: float, shots: list,
           emotions: list, actions: list, world: dict | None = None) -> tuple[dict, list]:
    """Props, sky effects, looks and cut-in shots for the things the scene's lines talk about."""
    cues = storyfx.find_cues(sc.get("lines", []), spans, words, total)
    props, fx, looks, extra = [], [], [], []
    if not cues:
        return {"props": [], "fx": [], "looks": []}, shots
    xs = [c["x"] for c in cast] or [0.0]
    cx = sum(xs) / len(xs)
    ids = [c["id"] for c in cast]
    free = [cx - 3.0, cx + 3.0, cx]          # spots in front of the cast for things nobody in particular names
    lo, hi = min(xs), max(xs)
    for k, c in enumerate(cues):
        li = c["line"]
        who = lines[li]["who"] if 0 <= li < len(lines) else None
        t0, t1 = c["t0"], c["t1"]
        others = [i for i in ids if i != who]
        if c["kind"] == "place":
            _named_place(c, k, who, others, ids, cast, cx, lo, hi, world or {}, total, props, looks, extra, actions)
            continue
        if c["kind"] == "prop":
            pid = f"prop{k}"
            if c["how"] == "bubble" and who:
                props.append({"id": pid, "name": c["name"], "how": "bubble", "t0": t0, "t1": t1, "x": 0, "z": 0, "who": who})
                extra.append({"kind": "bubble", "t0": t0 - 0.1, "t1": min(t1, t0 + 2.6), "target": who})
                if others:
                    looks.append({"t0": t0 + 0.2, "t1": min(t1, t0 + 2.4), "prop": pid, "who": others})
                continue
            big = c["name"] in ("car", "bicycle", "boat", "rocket")
            if who:   # on the outer side of whoever names it, a little in front: never between the characters
                me = next(x for x in cast if x["id"] == who)
                out = -1 if me["x"] <= cx else 1
                x = (lo if out < 0 else hi) + out * (2.6 if big else 1.7)
            else:
                x = free.pop(0) if free else cx
            how = c["how"]
            props.append({"id": pid, "name": c["name"], "how": how, "t0": t0, "t1": t1, "x": round(x, 2),
                          "z": 2.2 if big else 1.6, "who": who})
            show_at = t0 + (0.7 if how == "drive" else 0.15)
            extra.append({"kind": "insert", "t0": show_at, "t1": min(total, show_at + (2.2 if how == "fly" else 1.8)),
                          "target": pid})
            looks.append({"t0": t0 + 0.1, "t1": min(t1, t0 + 2.6), "prop": pid, "who": ids})
            for o in others:
                emotions.append({"who": o, "t0": t0 + 0.2, "t1": min(t1, t0 + 1.8), "emo": "surprised"})
        else:
            f = {"name": c["name"], "t0": t0, "t1": t1}
            if c["name"] == "sparkles":
                f["who"] = who
            fx.append(f)
            if c["name"] in storyfx.SKY_FX:
                extra.append({"kind": "sky", "t0": max(0.0, t0 - 0.1), "t1": min(total, t0 + 2.5)})
                # up and towards the camera's side, so the faces show, lifted in wonder
                looks.append({"t0": t0, "t1": min(total, t0 + 3.0), "at": [round(cx, 2), 9.0, 12.0], "who": ids})
                for o in others:
                    emotions.append({"who": o, "t0": t0 + 0.2, "t1": min(total, t0 + 2.2), "emo": "surprised"})
                if who:
                    actions.append({"who": who, "type": "point", "t0": t0, "t1": min(total, t0 + 1.6)})
    return {"props": props, "fx": fx, "looks": looks}, _overlay(shots, extra, total)


def _named_place(c, k, who, others, ids, cast, cx, lo, hi, world, total, props, looks, extra, actions):
    """A place named in a line. In that very place: the camera turns to its building or view and everyone looks.
    Somewhere else: the place appears in the distance (in open country) or in a thought bubble (indoors, by water,
    or when it is remembered), with a shot of it."""
    from studio.anim3d import sets as _sets
    kit = str(world.get("preset") or "")
    t0, t1, pid = c["t0"], c["t1"], f"place{k}"
    here = kit in storyfx.place_kits(c["name"])
    if here:
        if kit in _sets.INDOOR or c["name"] == "tree":
            return               # inside it already (a train, a school), or trees all around: nothing to turn to
        at = _sets.FOCUS.get(kit, [0, 3, -12, 6])
        extra.append({"kind": "landmark", "t0": t0 + 0.1, "t1": min(total, t0 + 2.8), "at": at})
        looks.append({"t0": t0, "t1": min(total, t0 + 3.0), "at": at[:3], "who": ids})
        if who:
            actions.append({"who": who, "type": "point", "t0": t0, "t1": min(total, t0 + 1.6)})
        return
    if c["name"] == "tree" and kit in storyfx.NATURE:
        return
    far = c["how"] != "bubble" and kit in _sets.OPEN and c["name"] not in ("river", "lake")
    if not far:
        if not who:
            return
        props.append({"id": pid, "name": "place_" + c["name"], "how": "bubble", "t0": t0, "t1": min(t1, t0 + 3.6),
                      "x": 0, "z": 0, "who": who})
        extra.append({"kind": "bubble", "t0": t0 - 0.1, "t1": min(total, t0 + 2.8), "target": who})
        if others:
            looks.append({"t0": t0 + 0.2, "t1": min(total, t0 + 2.6), "prop": pid, "who": others})
        return
    me = next((x for x in cast if x["id"] == who), None)
    side = (-1 if me["x"] <= cx else 1) if me else (1 if k % 2 else -1)
    props.append({"id": pid, "name": "place_" + c["name"], "how": "far", "t0": t0, "t1": total,
                  "x": round(side * 11.0, 2), "z": -22.0 if c["name"] != "mountain" else -45.0, "who": who})
    extra.append({"kind": "landmark", "t0": t0 + 0.3, "t1": min(total, t0 + 3.0), "target": pid})
    looks.append({"t0": t0 + 0.1, "t1": min(total, t0 + 3.2), "prop": pid, "who": ids})
    if who:
        actions.append({"who": who, "type": "point", "t0": t0, "t1": min(total, t0 + 1.6)})


def _overlay(shots: list, extra: list, total: float) -> list:
    """Cut the story's shots into the shot list at their times; what was there carries on after them."""
    for e in sorted(extra, key=lambda x: x["t0"]):
        t0, t1 = max(0.0, e["t0"]), min(total, e["t1"])
        if t1 - t0 < 1.0:
            continue
        out = []
        for s in shots:
            if s["t1"] <= t0 or s["t0"] >= t1:
                out.append(s)
                continue
            if s["t0"] < t0:
                out.append({**s, "t1": t0})
            if s["t1"] > t1:
                out.append({**s, "t0": t1})
        out.append({**e, "t0": round(t0, 3), "t1": round(t1, 3)})
        shots = sorted(out, key=lambda s: s["t0"])
    # no flash cuts: a piece shorter than 0.6 s joins the shot before it
    clean: list = []
    for s in shots:
        if clean and s["t1"] - s["t0"] < 0.6 and s["kind"] not in ("sky", "insert", "bubble", "landmark"):
            clean[-1]["t1"] = s["t1"]
            continue
        clean.append(dict(s))
    for i in range(len(clean) - 1):
        clean[i]["t1"] = clean[i + 1]["t0"]
    if clean:
        clean[0]["t0"], clean[-1]["t1"] = 0.0, round(total, 3)
    return clean
