"""Series ideas for the New Series dialog: titles, a cast and whole blueprints that fit the chosen video format,
market and language.

The AI writes them when one is set up (studio/ai.py). Without it, ideas are put together from the built-in lists
below, still matched to the format, so the dialog always has something sensible to offer.
"""
from __future__ import annotations

import logging
import random

from studio import ai, formats, usage

log = logging.getLogger("peakcut.concepts")

MARKETS = {
    "IN": "India (Hindi-speaking families; Indian names, villages, cities, festivals, folk tales and mythology)",
    "US": "United States and global English audience (American names and settings)",
    "JP": "Japan (Japanese names and settings, anime-friendly ideas)",
    "GB": "United Kingdom (British names, countryside, towns and storybook settings)",
}

CONCEPT_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "title": {"type": "STRING"},
            "genre": {"type": "STRING"},
            "category": {"type": "STRING"},
            "target_audience": {"type": "STRING"},
            "logline": {"type": "STRING"},
            "hook": {"type": "STRING"},
            "visual_style": {"type": "STRING"},
            "character_seed": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING"},
                        "species": {"type": "STRING"},
                        "visual_anchor": {"type": "STRING"},
                        "personality": {"type": "STRING"},
                    },
                    "required": ["name", "species", "visual_anchor", "personality"],
                },
            },
        },
        "required": ["title", "genre", "logline", "hook", "visual_style", "character_seed"],
    },
}

WANTS = {
    "all": "complete series blueprints",
    "title": "NEW series titles for the series the user described (fit their cast and genre; every title must differ "
             "from the title they already have)",
    "cast": "starting casts for the series the user described (keep their title and genre; every cast must differ "
            "from the cast they already have, with new names)",
}


def suggest(format_id: str, market: str = "IN", lang: str = "en", want: str = "all", title: str = "",
            genre: str = "", cast: str = "", count: int = 4) -> dict:
    """Returns {"concepts": [...], "source": "ai" | "builtin"}. Every concept has the same fields as a market
    blueprint, so the dialog can apply any of them the same way."""
    fmt = formats.get(format_id)
    market = (market or "IN").strip().upper()
    want = want if want in WANTS else "all"
    count = max(1, min(int(count or 4), 6))
    if ai.ready():
        got = _from_ai(fmt, market, lang, want, title, genre, cast, count)
        if got:
            return {"concepts": got, "source": "ai"}
    return {"concepts": _builtin(fmt, market, lang, count), "source": "builtin"}


def _from_ai(fmt, market, lang, want, title, genre, cast, count) -> list:
    looks = "; ".join(l["style"] for l in formats.looks_for(fmt))
    prompt = f"""You develop new YouTube video series.

VIDEO FORMAT: {fmt['name']} ({fmt['category']}). {fmt['description']}
Audience: {fmt['audience']}. Tone: {fmt['story']['tone']}
Example topics for this format: {fmt.get('examples') or 'any that fit the format'}
MARKET: {MARKETS.get(market, market)}
SERIES LANGUAGE: {lang}
What the user already wrote (may be empty; ignore anything that does not fit the format):
- title: {title or '-'}
- genre: {genre or '-'}
- cast: {cast or '-'}

TASK: Suggest {count} {WANTS[want]}. Each one must clearly belong to the {fmt['name']} format (a horror format gets
horror series, a documentary format gets documentary series, and so on), and the {count} must be clearly different
from each other. Use original ideas, names and characters only: never existing shows, films, brands or their
characters.

Fields:
- title: catchy and short, in English (names may be in the market's language, written in Latin letters).
- genre: 2-5 words.
- category: a short label for the kind of idea (e.g. "Haunted village", "Space mystery").
- target_audience: who it is for.
- logline: one or two sentences.
- hook: what keeps viewers coming back every episode.
- visual_style: one comma-separated line describing the look, in the spirit of: {looks}
- character_seed: 2-4 characters. "species" is what they are in 2-3 plain English words (e.g. "Old Man",
  "Little Girl", "Brown Bear", "Ghost", "Robot", "Village Priest"). "visual_anchor" describes the look in plain
  English with colours tied to clothing items (e.g. "tall old man, white beard, brown shawl, round glasses"), because
  the 3D characters are built from these words. "personality" is one short line.
  For a narrated faceless format, the cast can be the narrator plus 1-2 recurring figures.
"""
    for m in ai.models() or []:
        try:
            raw = usage.studio_call(m, prompt, CONCEPT_SCHEMA, "Studio: series ideas", f"New series · {fmt['name']}",
                                    timeout=45, temperature=0.9)
            res = raw[0] if isinstance(raw, tuple) else raw
            if isinstance(res, dict):
                res = res.get("concepts") or res.get("items") or [res]
            out = [_clean(c, fmt, lang) for c in (res or []) if isinstance(c, dict) and c.get("title")]
            if out:
                return out[:count]
        except Exception as e:  # noqa: BLE001
            log.warning("series ideas from %s failed: %s", m, e)
    return []


def _clean(c: dict, fmt: dict, lang: str) -> dict:
    cast = []
    for ch in (c.get("character_seed") or [])[:4]:
        if not isinstance(ch, dict) or not str(ch.get("name") or "").strip():
            continue
        cast.append({"name": str(ch["name"]).strip()[:40], "species": str(ch.get("species") or "Character").strip()[:40],
                     "visual_anchor": str(ch.get("visual_anchor") or "").strip()[:200],
                     "personality": str(ch.get("personality") or "").strip()[:160]})
    return {
        "title": str(c.get("title") or "").strip()[:90],
        "genre": str(c.get("genre") or fmt["name"]).strip()[:60],
        "category": str(c.get("category") or fmt["name"]).strip()[:40],
        "target_audience": str(c.get("target_audience") or fmt["audience"]).strip()[:60],
        "logline": str(c.get("logline") or "").strip()[:400],
        "hook": str(c.get("hook") or "").strip()[:240],
        "visual_style": str(c.get("visual_style") or fmt["visual"]["style"]).strip()[:300],
        "default_language": lang,
        "format": fmt["id"],
        "character_seed": cast,
    }


# ---------------------------------------------------------------- without an AI
# A few ideas per family of formats; names come from the market. Picked at random, so pressing again gives others.

NAMES = {
    "IN": ["Aarav", "Meera", "Kabir", "Anaya", "Raghu", "Tara", "Vikram", "Diya", "Arjun", "Kavya", "Mohan", "Nisha"],
    "US": ["Jake", "Lily", "Marcus", "Emma", "Leo", "Ava", "Noah", "Grace", "Ethan", "Zoe", "Owen", "Maya"],
    "JP": ["Haruto", "Yui", "Ren", "Hina", "Sora", "Aoi", "Kenji", "Mei", "Takumi", "Sakura", "Kaito", "Riku"],
    "GB": ["Oliver", "Isla", "Harry", "Poppy", "Alfie", "Freya", "George", "Ivy", "Archie", "Rosie", "Maisie", "Theo"],
}

IDEAS = {
    "Kids & Family": [
        ("{a} and {b}'s Forest Club", "Animal Friendship Adventures", "Two forest friends solve a small problem in every episode with kindness and teamwork.",
         "Each episode ends with a mysterious gift left at their tree house.",
         [("Bear Cub", "chubby brown bear cub, red scarf"), ("Bunny", "small white bunny, blue bow tie")]),
        ("Little {a}'s Big Farm", "Farm Comedy", "A curious child and a cheeky goat turn ordinary farm chores into big adventures.",
         "The farm's old windmill hides a new surprise every week.",
         [("Little Boy", "little boy, yellow shirt, orange cap"), ("Goat", "small white goat, green bell collar")]),
        ("{a} the Robot Helper", "Robot Friendship", "A clumsy helper robot learns about feelings from the family that built it.",
         "Each episode it unlocks a new silly gadget.",
         [("Robot", "round blue robot, orange antenna"), ("Little Girl", "little girl, pink dress, two ponytails")]),
    ],
    "Horror & Thriller": [
        ("The Last House in {place}", "Haunted Village Horror", "A family moves into an empty house at the edge of a village that nobody will talk about.",
         "Every night the clock stops at 3:13 and something new is out of place.",
         [("Young Woman", "young woman, grey sweater, dark hair"), ("Old Man", "old man, white beard, brown shawl, round glasses"), ("Ghost", "pale ghost, white cloth")]),
        ("Night Shift at {place} Station", "Supernatural Mystery", "A night guard at a lonely railway station keeps meeting passengers who don't exist.",
         "The logbook writes one new line by itself every episode.",
         [("Night Guard", "middle-aged man, dark blue uniform, cap"), ("Ghost Child", "pale ghost child, white dress")]),
        ("Whispers of {place} Forest", "Folk Horror", "Two friends lost in an old forest discover it remembers everyone who ever entered it.",
         "Each episode a new carved name appears on the trees.",
         [("Teen Boy", "teenage boy, black hoodie"), ("Teen Girl", "teenage girl, red jacket"), ("Shadow Creature", "tall shadow creature, glowing eyes")]),
    ],
    "Anime & Stylised": [
        ("{a} of the Sky Islands", "Fantasy Adventure", "A young pilot races between floating islands to find their missing mentor.",
         "Every island holds one piece of a broken map.",
         [("Young Pilot", "teenage boy, orange jacket, goggles"), ("Fox Spirit", "small white fox spirit, blue flame tail")]),
        ("Pixel Quest: {a}'s Run", "Retro Game Adventure", "A hero trapped inside an old video game must clear one level per episode to get home.",
         "Every boss drops a clue about who built the game.",
         [("Hero", "young hero, green tunic"), ("Robot", "small boxy robot, yellow light")]),
    ],
    "Documentary & Education": [
        ("Secrets of {place}", "History Documentary", "Each episode uncovers one forgotten story from an ancient place.",
         "Every episode ends on an unanswered question for the next.",
         [("Narrator", "middle-aged man, brown jacket, glasses"), ("Historian", "woman, green saree, notebook")]),
        ("How Things Work with {a}", "Science Explainer", "A curious host and a robot sidekick explain one everyday thing per episode.",
         "Viewers' questions decide the next episode.",
         [("Host", "young woman, blue shirt"), ("Robot", "small white robot, orange screen")]),
    ],
    "Cinematic Fiction": [
        ("Station {a}", "Sci-Fi Mystery", "The crew of a quiet space station receive signals from a ship that vanished 50 years ago.",
         "Each signal reveals a little more of the missing crew's last day.",
         [("Captain", "woman, white space suit, red stripe"), ("Engineer", "man, grey overalls, tool belt"), ("Robot", "tall silver robot")]),
        ("The {place} Diaries", "Family Drama", "Three siblings return to their grandmother's house and find letters she never sent.",
         "Every episode opens one new letter.",
         [("Older Sister", "young woman, yellow kurta"), ("Brother", "young man, blue shirt"), ("Grandma", "grandma, green saree, glasses")]),
    ],
    "Faceless Channels": [
        ("Rise Again", "Motivational Stories", "Short true-to-life comeback stories with one lesson each.",
         "A new challenge for viewers at the end of every video.",
         [("Narrator", "man, black hoodie"), ("Runner", "young man, red tracksuit")]),
    ],
}

PLACES = {"IN": ["Rampur", "Shivgarh", "Neelpur", "Chandanvan"], "US": ["Maple Hollow", "Cedar Falls", "Ridgewood"],
          "JP": ["Kirigaoka", "Hoshimura", "Aonuma"], "GB": ["Ashbury", "Mistle Down", "Wrenford"]}


def _builtin(fmt: dict, market: str, lang: str, count: int) -> list:
    ideas = list(IDEAS.get(fmt["category"]) or IDEAS["Kids & Family"])
    random.shuffle(ideas)
    names = list(NAMES.get(market, NAMES["US"]))
    out = []
    for i in range(count):
        title, genre, logline, hook, cast = ideas[i % len(ideas)]
        random.shuffle(names)
        a, b = names[0], names[1]
        place = random.choice(PLACES.get(market, PLACES["US"]))
        seed = [{"name": names[j], "species": sp, "visual_anchor": look, "personality": ""}
                for j, (sp, look) in enumerate(cast)]
        out.append({
            "title": title.format(a=a, b=b, place=place), "genre": genre, "category": fmt["name"],
            "target_audience": fmt["audience"], "logline": logline, "hook": hook,
            "visual_style": fmt["visual"]["style"], "default_language": lang, "format": fmt["id"],
            "character_seed": seed,
        })
        if i + 1 >= len(ideas):   # every idea used once: stop rather than repeat with other names
            break
    return out


# ---------------------------------------------------------------- a new character for an existing series
CHARACTER_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "species": {"type": "STRING"},
            "gender": {"type": "STRING"},
            "age": {"type": "STRING"},
            "visual_anchor": {"type": "STRING"},
            "personality": {"type": "STRING"},
            "role": {"type": "STRING"},
        },
        "required": ["name", "species", "visual_anchor", "personality"],
    },
}


def suggest_characters(series: dict, hint: str = "", episode: str = "", count: int = 3) -> dict:
    """New characters that fit this series: its format, its cast (no look-alikes, no repeated names), the story so
    far and the episode being written. Each comes with a real voice for its age, size and gender.
    Returns {"characters": [...], "source": "ai" | "builtin"}."""
    from studio import tts
    fmt = formats.resolve(series)
    lang = (series.get("default_language") or "en").lower()
    cast = series.get("characters", []) or []
    count = max(1, min(int(count or 3), 5))
    out, source = [], "builtin"
    if ai.ready():
        out = _characters_from_ai(series, fmt, lang, cast, hint, episode, count)
        source = "ai" if out else source
    if not out:
        out = _builtin_characters(fmt, series, cast, count)
    # a voice in the series' language that suits each one and differs from the voices already taken
    used = [{"voice_id": c.get("voice_id"), "voice_rate": c.get("voice_rate", "+0%"),
             "voice_pitch": c.get("voice_pitch", "+0Hz")} for c in cast]
    used.append({"voice_id": formats.narrator_voice(fmt, lang), "voice_rate": "+0%", "voice_pitch": "+0Hz"})
    attach_designs(out, fmt)   # each idea comes with its 3D design (the AI designer), shown when it is saved
    for c in out:
        who = " ".join(str(c.get(k, "")) for k in ("name", "species", "gender", "age", "visual_anchor"))
        if str(c.get("gender", "")).lower().startswith("f"):
            who += " woman female"
        v = tts.cast_voice(lang, who, used)
        c.update(v)
        used.append(v)
    return {"characters": out, "source": source}


def _characters_from_ai(series, fmt, lang, cast, hint, episode, count) -> list:
    eps = series.get("episodes", []) or []
    story = "\n".join(f"- Episode {e.get('episode_num')}: {e.get('title', '')}: {str(e.get('summary', ''))[:200]}"
                      for e in eps[-3:]) or "- No episodes yet."
    hook = eps[-1].get("unresolved_hook", "") if eps else ""
    have = "\n".join(f"- {c.get('name')} ({c.get('species', '')}): {str(c.get('personality', ''))[:100]}"
                     for c in cast) or "- Nobody yet."
    prompt = f"""You create characters for an ongoing animated YouTube series.

SERIES: {series.get('title', '')}. Genre: {series.get('genre', '')}.
FORMAT: {fmt['name']} ({fmt['category']}): {fmt['description']} Audience: {fmt['audience']}. Tone: {fmt['story']['tone']}
LANGUAGE OF THE SHOW: {lang}
CHARACTERS ALREADY IN THE SHOW (do not repeat their names, species or looks):
{have}
STORY SO FAR:
{story}
{f"OPEN CLIFFHANGER: {hook}" if hook else ""}
{f"THE EPISODE BEING WRITTEN NOW: {episode[:600]}" if episode else ""}
WHAT THE USER WANTS (may be empty): {hint[:300] or '-'}

TASK: Suggest {count} different new characters who would make the next episodes better: each brings something the
cast lacks (a rival, a mentor, a funny sidekick, a mystery, a villain for a scary format...). Original names and
characters only, never from existing shows or films. Names fit the show's language and market.

Fields:
- name: short and memorable.
- species: what they are, 1-3 plain English words ("Old Man", "Little Girl", "Parrot", "Robot", "Ghost").
- gender: male or female. age: child, teen, adult or old.
- visual_anchor: their look in plain English, 8-16 words, with colours tied to clothing or fur
  ("small green parrot, red beak, yellow scarf, round glasses"); the 3D character is built from these words.
- personality: one short line. role: one line on how they fit the story now.
"""
    for m in ai.models() or []:
        try:
            raw = usage.studio_call(m, prompt, CHARACTER_SCHEMA, "Studio: character ideas", series.get("title", ""),
                                    timeout=45, temperature=0.9)
            res = raw[0] if isinstance(raw, tuple) else raw
            if isinstance(res, dict):
                res = res.get("characters") or [res]
            names = {str(c.get("name", "")).strip().lower() for c in cast}
            out = []
            for c in res or []:
                if not isinstance(c, dict) or not str(c.get("name", "")).strip():
                    continue
                if str(c["name"]).strip().lower() in names:
                    continue
                role = str(c.get("role") or "").strip()
                pers = str(c.get("personality") or "").strip()
                out.append({"name": str(c["name"]).strip()[:40], "species": str(c.get("species") or "Character").strip()[:40],
                            "gender": str(c.get("gender") or "").strip().lower()[:10],
                            "age": str(c.get("age") or "").strip().lower()[:10],
                            "visual_anchor": str(c.get("visual_anchor") or "").strip()[:220],
                            "personality": (pers + (f" Role: {role}" if role else ""))[:240]})
            if out:
                return out[:count]
        except Exception as e:  # noqa: BLE001
            log.warning("character ideas from %s failed: %s", m, e)
    return []


def _builtin_characters(fmt: dict, series: dict, cast: list, count: int) -> list:
    market = "IN" if (series.get("default_language") or "").lower() == "hi" else "US"
    taken = {str(c.get("name", "")).lower() for c in cast}
    pool = [n for n in NAMES.get(market, NAMES["US"]) if n.lower() not in taken]
    random.shuffle(pool)
    kinds = [x for idea in IDEAS.get(fmt["category"], IDEAS["Kids & Family"]) for x in idea[4]]
    random.shuffle(kinds)
    out = []
    for i, (species, look) in enumerate(kinds[:count]):
        out.append({"name": pool[i % len(pool)] if pool else f"Friend {i + 1}", "species": species, "gender": "",
                    "age": "", "visual_anchor": look, "personality": "New to the story"})
    return out


# ---------------------------------------------------------------- the AI character designer (any kind of character)
DESIGN_PROPS = {
    "body": {"type": "STRING"}, "gender": {"type": "STRING"}, "age": {"type": "STRING"}, "height": {"type": "NUMBER"},
    "skin": {"type": "STRING"}, "hair": {"type": "STRING"}, "hairStyle": {"type": "STRING"}, "top": {"type": "STRING"},
    "bottom": {"type": "STRING"}, "shoes": {"type": "STRING"}, "dress": {"type": "BOOLEAN"}, "hat": {"type": "STRING"},
    "glasses": {"type": "BOOLEAN"}, "fur": {"type": "STRING"}, "belly": {"type": "STRING"}, "ears": {"type": "STRING"},
    "snout": {"type": "STRING"}, "tail": {"type": "STRING"}, "pattern": {"type": "STRING"}, "patternColor": {"type": "STRING"},
    "mane": {"type": "STRING"}, "arms": {"type": "BOOLEAN"}, "legs": {"type": "BOOLEAN"}, "eyes": {"type": "STRING"},
    "eyeColor": {"type": "STRING"}, "pose": {"type": "STRING"}, "effect": {"type": "STRING"}, "glowColor": {"type": "STRING"},
    "hold": {"type": "STRING"},
    "parts": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "part": {"type": "STRING"}, "color": {"type": "STRING"}, "color2": {"type": "STRING"}}}},
}
DESIGN_ITEM = {"type": "OBJECT", "properties": {"name": {"type": "STRING"}, **DESIGN_PROPS},
               "required": ["name", "body", "parts", "hold", "pose", "effect", "eyes"]}


def design_rules() -> str:
    """How to write a design, for any prompt that asks the AI for one."""
    from studio.anim3d import characters as ch
    cat = ch.catalog()
    e = ch.ENUMS
    return f"""3D DESIGN RULES (the 3D character is built only from these; anything can be made by combining them):
- body: human | animal | robot | blob. Animals stand on two legs like cartoon animals. A creature with no legs
  (snake, fish) sets legs=false; with no arms, arms=false. A ghost or a slime is a blob.
- human: gender m|f, age child|adult|old, height 0.6-1.3, skin, hair (colours), hairStyle {'|'.join(e['hairStyle'])},
  top, bottom, shoes (colours), dress true for a skirt or frock, hat {'|'.join(x for x in e['hat'] if x)}, glasses.
- animal: fur, belly (colours), ears {'|'.join(e['ears'])}, snout {'|'.join(e['snout'])},
  tail {'|'.join(e['tail'])}, pattern {'|'.join(e['pattern'])} with patternColor, mane (a colour, for a lion or horse).
- robot: top = body colour, bottom = light colour. blob: top = body colour.
- eyes normal|big|glowing (+ eyeColor). pose: normal|zombie|hunched|proud|float|hands_on_hips.
  effect: none|ghostly|glowing|shadowy (+ glowColor).
- parts (up to 8 worn pieces or features, each with optional color/color2): {', '.join(cat['parts'])}.
- hold (one thing in the hand, or empty): {', '.join(cat['hold'])}.
- Fill EVERY field that applies to the body you chose (a human: gender, age, height, skin, hair, hairStyle, top,
  bottom, shoes; an animal: fur, belly, ears, snout, tail, pattern; a blob: top), list 2-6 parts, and set hold, pose
  and effect (use "" or none when nothing fits). Think about what makes this character recognisable at a glance.
- A thing that comes alive (a ball, a mango, a cloud, a teapot) is a blob in its colours, with parts for details.
- Keep EXACTLY every colour and item the description names ("orange cap, blue shirt" stays an orange cap and a blue
  shirt); vary only what it does not say.
- Colours as #rrggbb. Make every character easy to tell apart and true to the description (a cricketer gets
  cricket_helmet, leg_pads, gloves and hold=bat; a zombie gets green skin, rags, pose zombie; a king gets a crown
  hat, cape and necklace; a mermaid gets fish_tail).
"""


def design_toons(chars: list[dict], fmt: dict | None = None, avoid: list | None = None) -> list[dict]:
    """The AI designer: a 3D design for each character from its name, species and look. [] when no AI answers;
    the word rules in studio/anim3d/characters.py then design them."""
    if not chars or not ai.ready():
        return []
    from studio.anim3d import characters as ch
    import json as _json
    who = "\n".join(f"- {c.get('name', '')}: {c.get('species', '')}. Look: {c.get('visual_anchor', '')}"
                    + (f"\n  Their previous design was {_json.dumps(avoid[i])[:600]}: make a clearly DIFFERENT take "
                       f"(other colours, hair, pieces or held item) that still fits the look above."
                       if avoid and i < len(avoid) and avoid[i] else "")
                    for i, c in enumerate(chars))
    style = f"Format: {fmt['name']} ({fmt['category']}), audience {fmt['audience']}." if fmt else ""
    prompt = f"""You design cartoon 3D characters for an animated show. {style}
Design each of these characters (keep the order and the names):
{who}

{design_rules()}"""
    schema = {"type": "ARRAY", "items": DESIGN_ITEM}
    for m in ai.models() or []:
        try:
            raw = usage.studio_call(m, prompt, schema, "Studio: character design",
                                    ", ".join(str(c.get("name", "")) for c in chars)[:120],
                                    timeout=60, temperature=0.9 if avoid else 0.4)
            res = raw[0] if isinstance(raw, tuple) else raw
            if isinstance(res, dict):
                res = res.get("characters") or res.get("designs") or [res]
            if isinstance(res, list) and res:
                by_name = {str(x.get("name", "")).strip().lower(): x for x in res if isinstance(x, dict)}
                out = []
                for i, c in enumerate(chars):
                    d = by_name.get(str(c.get("name", "")).strip().lower()) or (res[i] if i < len(res) and isinstance(res[i], dict) else {})
                    out.append(ch.clean_toon(d))
                return out
        except Exception as e:  # noqa: BLE001
            log.warning("character design from %s failed: %s", m, e)
    return []


def attach_designs(chars: list[dict], fmt: dict | None = None, avoid: list | None = None) -> None:
    """Give every character without a design one from the AI designer (in one call). Leaves them as they are when
    no AI answers. avoid: their previous designs, for a different take."""
    todo = [c for c in chars if isinstance(c, dict) and not c.get("toon") and c.get("name")]
    if not todo:
        return
    for c, d in zip(todo, design_toons(todo, fmt, avoid)):
        if d:
            c["toon"] = d


# ---------------------------------------------------------------- titles for a made episode
def suggest_episode_titles(series: dict, ep: dict, summary: str = "", current: str = "", count: int = 5) -> dict:
    """Titles for an episode from what actually happens in it (its synopsis and lines), in the show's language.
    Returns {"titles": [...], "source": "ai" | "builtin"}."""
    fmt = formats.resolve(series)
    lang = (series.get("default_language") or "en").lower()
    summary = (summary or ep.get("summary") or "").strip()
    lines = []
    for sc in (ep.get("script") or [])[:8]:
        for ln in (sc.get("lines") or [])[:2]:
            if ln.get("text"):
                lines.append(f"{ln.get('speaker', '')}: {ln['text']}")
    who = ", ".join(ep.get("featured_characters") or [c.get("name", "") for c in series.get("characters", [])[:3]])
    current = (current or ep.get("title") or "").strip()
    if ai.ready():
        script_note = " (Devanagari)" if lang == "hi" else ""
        prompt = f"""Suggest {count} titles for one episode of the YouTube series "{series.get('title', '')}".
Format: {fmt['name']} ({fmt['category']}), audience {fmt['audience']}. Tone: {fmt['story']['tone']}
Language of the show: {lang} (write the titles in this language and its usual script{script_note}).
Characters: {who or '-'}
What happens in the episode: {summary[:900] or '-'}
Some lines: {' | '.join(lines)[:900] or '-'}
Current title (every suggestion must be different from it): {current or '-'}

Titles: short (2-7 words), catchy, true to this episode's story and the format's mood, each in a different style
(a question, a name + the event, a mystery, a promise of what happens...). No episode numbers, no quotes, no emojis.
"""
        schema = {"type": "OBJECT", "properties": {"titles": {"type": "ARRAY", "items": {"type": "STRING"}}},
                  "required": ["titles"]}
        for m in ai.models() or []:
            try:
                raw = usage.studio_call(m, prompt, schema, "Studio: episode titles", series.get("title", ""),
                                        timeout=30, temperature=0.9)
                res = raw[0] if isinstance(raw, tuple) else raw
                titles = res.get("titles") if isinstance(res, dict) else res
                out = []
                for t in titles or []:
                    t = str(t).strip().strip('"\u201c\u201d\'').strip()[:100]
                    if t and t.lower() != current.lower() and t not in out:
                        out.append(t)
                if out:
                    return {"titles": out[:count], "source": "ai"}
            except Exception as e:  # noqa: BLE001
                log.warning("episode titles from %s failed: %s", m, e)
    # without an AI: titles built from this episode's own characters and places
    lead = (ep.get("featured_characters") or [c.get("name") for c in series.get("characters", [])] or ["Our Friends"])[0]
    place = next((str(sc.get("setting") or "").split(",")[0].strip() for sc in ep.get("script") or [] if sc.get("setting")), "")
    ideas = [f"{lead} and the {place.title()} Secret" if place else f"{lead}'s Secret",
             f"A Day in {place.title()}" if place else f"{lead}'s Big Day",
             f"What {lead} Found", f"{lead} to the Rescue", f"The {place.title()} Mystery" if place else f"{lead}'s Surprise"]
    return {"titles": [t for t in ideas if t.lower() != current.lower()][:count], "source": "builtin"}


# ---------------------------------------------------------------- a whole series from the creator's own brief
BRIEF_SCHEMA = {"type": "OBJECT", "properties": {
    "format": {"type": "STRING"}, "title": {"type": "STRING"}, "genre": {"type": "STRING"},
    "language": {"type": "STRING"}, "visual_style": {"type": "STRING"}, "logline": {"type": "STRING"},
    "characters": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "name": {"type": "STRING"}, "species": {"type": "STRING"}, "visual_anchor": {"type": "STRING"},
        "personality": {"type": "STRING"}}, "required": ["name", "species", "visual_anchor", "personality"]}},
    "first_episode": {"type": "OBJECT", "properties": {"title": {"type": "STRING"}, "premise": {"type": "STRING"}}}},
    "required": ["format", "title", "genre", "language", "visual_style", "characters", "first_episode"]}


def series_from_brief(text: str, market: str = "IN") -> dict:
    """Read anything the creator pastes (a story, a list of characters, a concept, in any language) and set up the
    series from it: the best format, title, genre, language, look, every character and Episode 1's story."""
    text = (text or "").strip()
    if not text:
        return {"error": "Paste an idea, a story or characters first"}
    if not ai.ready():
        return {"error": "Set up an AI service in Settings to build a series from your own idea"}
    fl = formats.list_formats()
    menu = "\n".join(f"- {f['id']}: {f['name']} ({f['category']}): {f['description']}" for f in fl)
    prompt = f"""A creator pasted the idea below for a new animated YouTube series. Set the series up from it.

THEIR IDEA:
{text[:9000]}

Choose "format" from these ids (the closest fit):
{menu}

Fields:
- title: the series title (keep theirs if they gave one; in their language).
- genre: 2-5 words. language: the language code of their idea (hi, en, ...). logline: one sentence.
- visual_style: one comma-separated line describing the look of the series.
- characters: EVERY character they describe (keep their names and roles), up to 12. species = what they are in 2-3
  plain English words ("Cricket Captain", "Fast Bowler", "Old Woman", "Bear"). visual_anchor = their look in plain
  English, 8-16 words, colours tied to clothes or kit ("young man, blue India cricket kit, white helmet, holding a
  bat"); the 3D character is built from these words. personality = one line in their language.
- first_episode: title and premise: Episode 1's story, as complete as their idea gives it, in their language.
Market: {MARKETS.get(market, market)}.
"""
    last = None
    for m in ai.models() or []:
        try:
            raw = usage.studio_call(m, prompt, BRIEF_SCHEMA, "Studio: series from your idea", text[:60].replace("\n", " "),
                                    timeout=90, temperature=0.4)
            r = raw[0] if isinstance(raw, tuple) else raw
            if not isinstance(r, dict) or not r.get("title"):
                continue
            fid = str(r.get("format") or "")
            if fid not in formats.FORMATS:
                fid = formats.guess(str(r.get("genre", "")), str(r.get("visual_style", "")))
            lang = str(r.get("language") or "en").lower()[:5]
            chars = []
            for c in r.get("characters") or []:
                if isinstance(c, dict) and str(c.get("name", "")).strip():
                    chars.append({k: str(c.get(k) or "").strip()[:240] for k in ("name", "species", "visual_anchor", "personality")})
            ep = r.get("first_episode") or {}
            return {"format": fid, "title": str(r["title"]).strip()[:90], "genre": str(r.get("genre") or "").strip()[:60],
                    "language": lang, "visual_style": str(r.get("visual_style") or formats.get(fid)["visual"]["style"]).strip()[:300],
                    "logline": str(r.get("logline") or "").strip()[:300], "characters": chars[:12],
                    "first_episode": {"title": str(ep.get("title") or "").strip()[:100],
                                      "premise": str(ep.get("premise") or "").strip()[:6000]}}
        except Exception as e:  # noqa: BLE001
            last = e
            log.warning("series from brief with %s failed: %s", m, e)
    if last is not None and "free tier is not available" in str(last):
        return {"error": "Google says the Gemini free tier is not available for this key's project: set up billing at "
                         "aistudio.google.com/billing, or use another AI service on the AI page."}
    return {"error": ai.explain(last) if last is not None else "The AI could not read this idea right now; try again in a minute"}
