"""Which set a scene is played in: the place (one of the set kits in web/studio3d/sets.js or the older worlds), the
time of day, the weather, the era and the culture.

Where it comes from:
  1. the script writer's description of the scene's set (scene["set"]: place, kit, era, culture, time, weather…);
  2. otherwise words in the scene's setting and shots, in English, Hinglish and Hindi ("temple courtyard at dawn",
     "रात को घाट पर", "busy city street in the rain").
A named place ("Dadi's house", "Lord's") always gets the same layout: its name is the layout's seed.
"""
from __future__ import annotations

import hashlib
import re

# the places a scene can be in (web/studio3d/sets.js KITS + the older worlds in runtime.js)
KITS = ["temple", "palace", "ruins", "ghat", "bazaar", "city_street", "highway", "station", "school", "hospital",
        "kitchen", "bedroom", "mountain", "desert", "river", "cave", "stadium", "room", "village", "farm", "beach",
        "snow", "space", "forest_green", "forest_autumn",
        "train_interior", "office", "cafe", "library", "lab", "rooftop", "playground", "garden", "lake", "waterfall",
        "jungle", "field", "haveli", "mela", "stage", "space_station", "planet", "underwater", "castle",
        "haunted_house", "graveyard", "bus_stop"]
# the heart of each set (its temple, haveli, river, view): [x, y, z, size] for the camera to turn to when a line names it
FOCUS = {"temple": [0, 4.5, -12, 6], "palace": [0, 5, -16, 8], "ruins": [0, 3.5, -12, 7], "ghat": [0, 1.5, -20, 9],
         "haveli": [0, 3.5, -10, 6], "castle": [0, 7, -16, 10], "haunted_house": [0, 6, -16, 8], "mountain": [0, 10, -60, 30],
         "river": [0, 0.5, -10, 7], "lake": [0, 0.5, -14, 8], "waterfall": [0, 4, -14, 8], "station": [0, 1.5, -5, 6],
         "village": [0, 2.5, -10, 6], "bazaar": [0, 3, -12, 7], "mela": [0, 5, -14, 8], "stadium": [0, 4, -20, 10],
         "graveyard": [0, 1.5, -9, 5], "beach": [0, 0.5, -15, 8], "desert": [0, 3, -25, 10], "snow": [0, 5, -30, 12],
         "garden": [0, 2, -8, 5], "jungle": [0, 4, -12, 7], "field": [0, 1.5, -14, 8], "farm": [0, 2.5, -12, 6],
         "forest_green": [0, 4, -12, 7], "forest_autumn": [0, 4, -12, 7], "planet": [0, 4, -25, 10],
         "playground": [0, 2, -8, 5], "rooftop": [0, 5, -25, 12], "bus_stop": [0, 2, -6, 5], "city_street": [0, 4, -20, 10],
         "highway": [0, 2, -15, 8]}
# open sets, where a place named in a line can stand in the distance (elsewhere it is a thought bubble)
OPEN = {"village", "farm", "field", "beach", "desert", "mountain", "forest_green", "forest_autumn", "jungle", "garden",
        "playground", "snow", "ruins", "temple", "highway", "graveyard", "waterfall", "rooftop", "planet", "mela", "ghat"}
# a specific set and the general sets it was once filed under (before the specific one existed)
BROADER = {"train_interior": {"station"}, "haveli": {"ruins", "palace", "room", "village"}, "mela": {"bazaar"},
           "haunted_house": {"ruins", "haveli", "room"}, "bus_stop": {"city_street"}, "space_station": {"space"},
           "planet": {"space", "desert"}, "jungle": {"forest_green"}, "garden": {"forest_green"}, "lake": {"river"},
           "waterfall": {"river", "mountain"}, "field": {"farm"}, "graveyard": {"forest_autumn", "ruins"},
           "castle": {"palace"}, "library": {"school", "room"}, "office": {"room"}, "cafe": {"room", "kitchen"},
           "lab": {"school", "hospital"}, "stage": {"school", "room"}, "playground": {"school"}, "rooftop": {"city_street"}}
INDOOR = {"school", "hospital", "kitchen", "bedroom", "cave", "room", "train_interior", "office", "cafe", "library",
          "lab", "stage", "space_station"}

# (word pattern, kit): first match wins, specific places before general ones
PLACE_RULES = [
    (r"underwater|under the sea|ocean floor|coral reef|पानी के नीचे|समुद्र के नीचे", "underwater"),
    (r"space station|spaceship|space ship|starship|cockpit of|अंतरिक्ष स्टेशन|अंतरिक्ष यान", "space_station"),
    (r"alien planet|planet surface|on mars|\bmars\b|moon surface|another planet|दूसरे ग्रह", "planet"),
    (r"space|rocket|galaxy|moon base|अंतरिक्ष|ग्रह", "space"),
    (r"train compartment|inside the train|in the train|coach of|sleeper coach|ट्रेन (?:के|का|की) (?:अंदर|डिब्बे|डिब्बा)|डिब्बे में", "train_interior"),
    (r"haunted house|haunted mansion|abandoned house|भूतिया (?:घर|हवेली|बंगला)", "haunted_house"),
    (r"graveyard|cemetery|crematorium|kabristan|shamshan|कब्रिस्तान|श्मशान", "graveyard"),
    (r"\bstage\b|auditorium|theatre|theater|concert|मंच|सभागार", "stage"),
    (r"\blab\b|laboratory|प्रयोगशाला", "lab"),
    (r"library|पुस्तकालय", "library"),
    (r"\boffice\b|workplace|दफ़्तर|दफ्तर|ऑफिस", "office"),
    (r"\bcafe\b|café|coffee shop|restaurant|tea shop|canteen|कैफ़े|रेस्टोरेंट|कैंटीन", "cafe"),
    (r"rooftop|terrace|\broof\b|छत", "rooftop"),
    (r"playground|school yard|schoolyard|swing|park with|खेल का मैदान|झूला", "playground"),
    (r"bus stop|bus stand|बस स्टॉप|बस अड्डा", "bus_stop"),
    (r"haveli|courtyard of (?:the |an )?(?:old )?house|old mansion|mansion courtyard|हवेली", "haveli"),
    (r"\bmela\b|fair ground|funfair|carnival|ferris wheel|मेला|झूले वाला", "mela"),
    (r"waterfall|झरना|जलप्रपात", "waterfall"),
    (r"jungle|rainforest|dense forest|घना जंगल|जंगल", "jungle"),
    (r"\blake\b|pond|jheel|झील|तालाब|सरोवर", "lake"),
    (r"garden|park|बगीचा|उद्यान|बाग़|बाग", "garden"),
    (r"wheat field|crop field|paddy|fields of|farmland|खेत|फसल", "field"),
    (r"castle|knight|kingdom of|qila of europe", "castle"),
    (r"stadium|cricket|lord'?s|\bpitch\b|crease|wicket|pavilion|football field|स्टेडियम|क्रिकेट|पिच|विकेट", "stadium"),
    (r"classroom|class ?room|school|blackboard|कक्षा|स्कूल|विद्यालय|पाठशाला", "school"),
    (r"hospital|clinic|\bward\b|operation theat|अस्पताल|दवाखाना", "hospital"),
    (r"kitchen|रसोई|रसोईघर", "kitchen"),
    (r"bedroom|bed room|शयनकक्ष|सोने का कमरा", "bedroom"),
    (r"\bcave|cavern|गुफा|कंदरा", "cave"),
    (r"temple|mandir|shrine|shivalaya|मंदिर|देवालय|शिवालय", "temple"),
    (r"palace|\bfort\b|fortress|mahal|durbar|throne|royal court|महल|किला|दरबार|राजमहल", "palace"),
    (r"ruins|ancient architecture|ancient city|ancient site|monument|archaeolog|खंडहर|प्राचीन (?:नगर|इमारत|स्थल)|अवशेष", "ruins"),
    (r"\bghat|घाट|varanasi|banaras|benaras|kashi|riverfront steps", "ghat"),
    (r"bazaar|market|haat|बाज़ार|बाजार|हाट|मंडी", "bazaar"),
    (r"railway|station|platform|\btrain\b|रेलवे|स्टेशन|प्लेटफ़ॉर्म|प्लेटफार्म|रेलगाड़ी", "station"),
    (r"highway|dhaba|roadside|truck stop|milestone|lonely road|night road|हाईवे|ढाबा|राजमार्ग|मील का पत्थर", "highway"),
    (r"village|town|chowk|गाँव|गांव|कस्बा|चौक|dholakpur", "village"),
    (r"city|street|downtown|traffic|road in|crossing|metro|शहर|सड़क|गली|चौराहा|मोहल्ला", "city_street"),
    (r"desert|sand dunes|\bthar\b|रेगिस्तान|मरुस्थल|रेत के टीले", "desert"),
    (r"mountain|himalaya|\bpeak\b|\bhill\b|hills|valley|पहाड़|पर्वत|हिमालय|घाटी|चोटी", "mountain"),
    (r"river|stream|riverbank|\bbank of|नदी|किनारा|किनारे|धारा", "river"),
    (r"snow|winter|\bice\b|frozen|igloo|बर्फ|सर्दी", "snow"),
    (r"beach|\bsea\b|ocean|shore|island|समुद्र|बीच|सागर|तट", "beach"),
    (r"room|house inside|home|living room|indoor|library|office|घर के अंदर|कमरा|कमरे|घर में", "room"),
    (r"farm|barn|field|orchard|खेत|बाड़ा|बगीचा", "farm"),
    (r"autumn|fall leaves|पतझड़", "forest_autumn"),
    (r"forest|jungle|\bwood|tree|park|garden|lake|meadow|जंगल|पेड़|झील|उद्यान|पार्क|वन\b", "forest_green"),
]
TIME_RULES = [
    (r"midnight|आधी रात|मध्यरात्रि", "midnight"),
    (r"dawn|sunrise|daybreak|first light|भोर|सूर्योदय|सुबह[- ]सुबह|तड़के", "dawn"),
    (r"golden hour|late afternoon|evening sun", "golden"),
    (r"sunset|dusk|evening|twilight|शाम|सूर्यास्त|गोधूलि|संध्या", "dusk"),
    (r"night|\bmoon|stars|dark sky|रात|चाँद|चांद|तारों|अंधेरी", "night"),
    (r"noon|midday|afternoon|दोपहर", "noon"),
    (r"morning|सुबह|प्रातः", "morning"),
]
WEATHER_RULES = [
    (r"storm|thunder|lightning|cyclone|तूफ़ान|तूफान|आंधी|बिजली कड़क", "storm"),
    (r"rain|monsoon|drizzle|downpour|बारिश|बरसात|वर्षा|मानसून", "rain"),
    (r"snowfall|snowing|blizzard|बर्फबारी|हिमपात", "snow"),
    (r"\bfog|foggy|mist|misty|\bhaze|कोहरा|धुंध|कुहासा", "fog"),
    (r"cloud|overcast|grey sky|gray sky|gloomy|बादल|घटा", "overcast"),
]
ERA_RULES = [
    (r"ancient|vedic|medieval|mughal|mauryan|historical|old kingdom|era of|सदी|प्राचीन|पौराणिक|मुगल|ऐतिहासिक|राजा-महाराजा", "ancient"),
    (r"futur|cyber|sci-?fi|year 2[1-9]\d\d|भविष्य", "future"),
]
CULTURE_RULES = [
    (r"india|indian|bharat|desi|भारत|हिंदुस्तान", "indian"),
    (r"japan|tokyo|kyoto|जापान", "japanese"),
    (r"england|london|britain|british|america|usa|new york|western", "western"),
]
TIMES = ["dawn", "morning", "noon", "golden", "dusk", "night", "midnight"]
WEATHERS = ["clear", "overcast", "rain", "storm", "fog", "snow"]


def _first(rules, text, default=None):
    return next((v for pat, v in rules if re.search(pat, text, re.I)), default)


def scene_text(sc: dict) -> str:
    st = sc.get("set") if isinstance(sc.get("set"), dict) else {}
    return " ".join(str(x) for x in [st.get("place", ""), " ".join(st.get("landmarks") or []), sc.get("setting", ""),
                                     sc.get("visual_prompt", ""),
                                     " ".join(s.get("visual_prompt", "") for s in sc.get("shots", []) or [])]).lower()


def scene_set(sc: dict, fmt: dict, series: dict, seed: int) -> dict:
    """The world spec for the runtime: {preset, mood, time, weather, era, culture, landmarks, place, seed}."""
    st = dict(sc.get("set")) if isinstance(sc.get("set"), dict) else {}
    # a place saved in the series' Location Vault: its set, era, culture and layout win (the user may have fixed them)
    from studio import memory
    saved = memory.find_location(series, st.get("location_name") or sc.get("setting") or "") if series else None
    if saved:
        for k in ("kit", "era", "culture"):
            if saved.get(k):
                st[k] = saved[k]
    text = scene_text(sc)
    kit = str(st.get("kit") or "").strip().lower()
    # the script writer (or an older list of sets) may name a general set where the words name a better one:
    # "train compartment" set at a station, an old haveli as ruins. A set the owner fixed is never changed.
    if not (saved and saved.get("edited")):
        named = _first(PLACE_RULES, " ".join(str(x) for x in (st.get("place", ""), st.get("location_name", ""),
                                                                sc.get("setting", ""))).lower())
        if named and kit in BROADER.get(named, ()):
            kit = named
    if kit not in KITS:
        kit = _first(PLACE_RULES, text) or series.get("world_preset") or ("forest_autumn" if seed % 2 else "forest_green")
    time = str(st.get("time") or "").lower()
    time = time if time in TIMES else _first(TIME_RULES, text, "morning" if kit not in INDOOR else "noon")
    weather = str(st.get("weather") or "").lower()
    weather = weather if weather in WEATHERS else _first(WEATHER_RULES, text, "clear")
    era = str(st.get("era") or "").lower() or _first(ERA_RULES, text + " " + str(series.get("genre", "")).lower(),
                                                       "ancient" if fmt.get("id") in ("history_doc", "mythology") else "modern")
    lang = (series.get("default_language") or "").lower()
    culture = str(st.get("culture") or "").lower() or _first(CULTURE_RULES, text) or \
        ("indian" if lang == "hi" else "japanese" if lang == "ja" else "western" if lang in ("en", "es", "fr", "de") else "indian")
    # the older worlds' look for night in the woods
    if kit in ("forest_green", "forest_autumn", "farm") and time in ("night", "midnight"):
        kit = "night"
    mood = {"dawn": "sunset", "dusk": "sunset", "golden": "sunset", "night": "night", "midnight": "night"}.get(time, "day")
    if fmt.get("category") == "Horror & Thriller" or fmt.get("id") in ("horror", "scary_narration", "noir", "thriller"):
        # horror stays dark: indoor and town scenes in deep shadow, outdoors at night, often in mist
        if kit in INDOOR or kit in ("village", "city_street", "bazaar", "station", "ghat"):
            mood = "dark"
        else:
            mood = "night"
            time = time if time in ("night", "midnight") else "night"
        if weather == "clear" and seed % 2 == 0:
            weather = "fog"
    if kit in ("space", "space_station", "planet"):
        mood, time, weather = "space", "", "clear"
    if kit in ("underwater",):
        weather = "clear"
    place = str(st.get("location_name") or st.get("place") or sc.get("setting") or kit)[:80]
    out = {"preset": kit, "mood": mood, "time": time, "weather": weather, "era": era, "culture": culture,
           "landmarks": [str(x)[:60] for x in (st.get("landmarks") or [])][:6], "place": place}
    if saved and saved.get("seed"):
        out["seed"] = int(saved["seed"])
    elif st.get("location_name"):   # a named place is laid out the same way every time it comes back
        out["seed"] = int(hashlib.md5(str(st["location_name"]).strip().lower().encode("utf-8")).hexdigest()[:8], 16)
    if saved:
        out["location_id"] = saved.get("id")
    return out


def weather_fx(world: dict, total: float) -> list[dict]:
    """Rain, snow and storms as whole-scene happenings (web/studio3d/story.js)."""
    w = world.get("weather")
    if world.get("preset") in INDOOR:
        return []
    if w == "rain":
        return [{"name": "rain", "t0": 0.0, "t1": total}]
    if w == "storm":   # a flash every 9-14 s, not one in the whole scene
        out, t, k = [{"name": "rain", "t0": 0.0, "t1": total}], min(2.0, total / 3), 0
        while t < total - 1.5:
            out.append({"name": "lightning", "t0": round(t, 2), "t1": round(min(total, t + 2.0), 2)})
            k += 1
            t += 9.0 + (k * 3.7) % 5
        return out
    if w == "snow":
        return [{"name": "snowfall", "t0": 0.0, "t1": total}]
    return []
