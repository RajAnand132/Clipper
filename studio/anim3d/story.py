"""Story visuals: what the narration and the dialogue talk about appears on screen, at the word.

"Why are the stars falling from the sky?"   → shooting stars streak down the sky; the camera looks up; everyone
                                              looks up, surprised.
"वो गाड़ी आ रही है!"                          → a car drives into the scene; a quick cut-in shows it.
"याद है, पापा की पतंग…" (a memory or wish)    → a thought bubble with a kite over the speaker's head.

find_cues() reads the scene's words (with their times from the voice) and lines, in English, Hinglish and Hindi.
The script writer can also ask for something directly: a line's "show": [{"thing": "car", "how": "enter"}].
The Director (director.py) turns the cues into props, sky effects, camera shots and reactions; the runtime
(web/studio3d/story.js) builds and animates them.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- what can be shown
# (name, word pattern, kind, how). kind: "fx" (something happening in the world or sky) or "prop" (a thing).
# how for fx: "sky" (the camera looks up) or "around" (seen in the normal shots).
# how for props: "drop" (falls in), "drive" (drives in), "pop" (appears), "float" (hovers), "fly" (rises into the sky).
STAR = r"stars?|taare|tare|sitare|तारा|तारे|तारों|सितारा|सितारे|सितारों"
FALL = r"fall|falling|fell|falls|shooting|gir|girne|girte|गिर|गिरा|गिरी|गिरे|गिरने|गिरते|गिरती|टूट|टूटा|टूटते|टूटता"
SNOW = r"snow|snowing|barf|baraf|बर्फ|बर्फ़|हिमपात"
LEXICON = [
    ("rain", r"rain|raining|rainy|baarish|barish|barsaat|बारिश|बरसात|बूँदें|बूंदें", "fx", "around"),
    ("lightning", r"lightning|thunder|storm|bijli|toofan|tufan|बिजली|तूफ़ान|तूफान|गरज", "fx", "sky"),
    ("fireworks", r"fireworks?|patakhe|pataakhe|aatishbaazi|diwali|पटाखे|पटाखों|आतिशबाज़ी|आतिशबाजी|दिवाली", "fx", "sky"),
    ("rainbow", r"rainbow|indradhanush|इंद्रधनुष", "fx", "sky"),
    ("moon", r"moon|chand|chaand|चाँद|चांद|चंदा|चंद्रमा", "fx", "sky"),
    ("sun", r"sun|sunshine|suraj|sooraj|सूरज|सूर्य|धूप", "fx", "sky"),
    ("birds", r"birds?|chidiya|chidiyan|panchhi|चिड़िया|चिड़ियाँ|चिड़ियों|पंछी|पक्षी|पक्षियों", "fx", "sky"),
    ("butterflies", r"butterfl(?:y|ies)|titli|titliyan|तितली|तितलियाँ|तितलियों", "fx", "around"),
    ("sparkles", r"magic|magical|jaadu|jadu|chamak|glitter|sparkle|जादू|जादुई|चमक|चमत्कार", "fx", "around"),
    ("wind", r"wind|windy|aandhi|hawa|हवा|आंधी|आँधी", "fx", "around"),
    ("ghost", r"ghosts?|bhoot|bhut|aatma|spirit|भूत|भूतों|आत्मा|चुड़ैल|साया", "prop", "float"),
    ("car", r"cars?|gaadi|gadi|truck|jeep|taxi|गाड़ी|गाडी|गाड़ियाँ|ट्रक|जीप|टैक्सी|कार", "prop", "drive"),
    ("bicycle", r"bicycle|cycle|bike|साइकिल|साईकिल", "prop", "drive"),
    ("ball", r"balls?|gend|गेंद|फुटबॉल|football", "prop", "drop"),
    ("cake", r"cake|birthday|केक|जन्मदिन", "prop", "pop"),
    ("gift", r"gifts?|present|tohfa|uphaar|तोहफ़ा|तोहफा|उपहार|गिफ्ट", "prop", "drop"),
    ("box", r"box|boxes|dibba|sandook|डिब्बा|डब्बा|संदूक", "prop", "drop"),
    ("treasure", r"treasure|khazana|khajana|ख़ज़ाना|खज़ाना|खजाना", "prop", "pop"),
    ("book", r"books?|kitab|kitaab|किताब|किताबें|पुस्तक", "prop", "drop"),
    ("letter", r"letter|chitthi|khat|चिट्ठी|चिठ्ठी|पत्र", "prop", "drop"),
    ("map", r"map|naksha|नक्शा|नक़्शा", "prop", "pop"),
    ("key", r"keys?|chabi|chaabi|चाबी|चाभी", "prop", "drop"),
    ("phone", r"phone|mobile|फ़ोन|फोन|मोबाइल", "prop", "pop"),
    ("clock", r"clock|ghadi|घड़ी", "prop", "pop"),
    ("lantern", r"lantern|lamp|diya|lalten|लालटेन|दीया|दिया|दीपक|लैंप", "prop", "pop"),
    ("candle", r"candles?|mombatti|मोमबत्ती", "prop", "pop"),
    ("fire", r"fire|campfire|aag|आग|अलाव", "prop", "pop"),
    ("flower", r"flowers?|phool|फूल|फूलों", "prop", "pop"),
    ("apple", r"apples?|seb|सेब", "prop", "drop"),
    ("mango", r"mangoes|mangos?|आमों", "prop", "drop"),
    ("laddoo", r"laddoos?|ladoos?|laddu|लड्डू", "prop", "pop"),
    ("honey", r"honey|shahad|शहद", "prop", "pop"),
    ("icecream", r"ice-?cream|आइसक्रीम", "prop", "pop"),
    ("egg", r"eggs?|anda|अंडा|अंडे", "prop", "drop"),
    ("umbrella", r"umbrella|chhata|chhatri|छाता|छतरी", "prop", "pop"),
    ("drum", r"drums?|dhol|ढोल|नगाड़ा", "prop", "pop"),
    ("crown", r"crown|mukut|ताज|मुकुट", "prop", "float"),
    ("kite", r"kites?|patang|पतंग", "prop", "fly"),
    ("balloons", r"balloons?|gubbare|gubbara|गुब्बारा|गुब्बारे", "prop", "fly"),
    ("orb", r"glowing|shining|chamakti|चमकती|चमकता|रोशनी|roshni", "prop", "float"),
    ("bell", r"bells?|ghanti|घंटी", "prop", "pop"),
    ("boat", r"boat|naav|nav|नाव|कश्ती", "prop", "pop"),
    ("rocket", r"rocket|रॉकेट", "prop", "fly"),
]
_RX = [(name, re.compile(rf"^(?:{pat})$", re.I), kind, how) for name, pat, kind, how in LEXICON]

# places and buildings named in a line: (name, words, the sets that already are that place). Said in the place itself,
# the camera turns to it; said elsewhere, it is seen in the distance (or in a thought bubble indoors).
NATURE = {"village", "farm", "field", "river", "lake", "ghat", "mountain", "forest_green", "forest_autumn", "jungle",
          "garden", "playground", "ruins", "temple", "waterfall", "highway", "graveyard", "snow"}
PLACES = [
    ("temple", r"temples?|mandir|mandiron|मंदिर|मन्दिर|मंदिरों|शिवालय|देवालय", {"temple", "ghat"}),
    ("haveli", r"haveli|havelis|mansion|हवेली|हवेलियों|कोठी", {"haveli", "haunted_house"}),
    ("palace", r"palace|fort|mahal|qila|kila|महल|किला|क़िला|किले|राजमहल", {"palace"}),
    ("castle", r"castles?", {"castle"}),
    ("mountain", r"mountains?|hills?|pahad|pahaad|pahadi|parvat|पहाड़|पहाड़ी|पहाड़ों|पहाड़ियों|पर्वत|पर्वतों", {"mountain", "snow"}),
    ("river", r"rivers?|nadi|नदी|नदियों|नदिया", {"river", "ghat"}),
    ("lake", r"lakes?|pond|jheel|talab|झील|तालाब", {"lake"}),
    ("waterfall", r"waterfalls?|jharna|झरना|झरने|जलप्रपात", {"waterfall"}),
    ("school", r"schools?|स्कूल|विद्यालय|पाठशाला", {"school", "playground"}),
    ("hospital", r"hospital|अस्पताल", {"hospital"}),
    ("train", r"trains?|railgadi|ट्रेन|रेल|रेलगाड़ी", {"station", "train_interior"}),
    ("tree", r"trees?|ped|पेड़|पेड़ों|वृक्ष|बरगद|पीपल", NATURE),
    ("well", r"kuan|kuaan|कुआँ|कुआं|कुएँ|कुएं", set()),
    ("hut", r"huts?|jhopdi|झोपड़ी|झोंपड़ी", set()),
    ("tower", r"towers?|minar|मीनार|टावर", set()),
    ("bridge", r"bridge|पुल", {"river"}),
    ("cave", r"caves?|gufa|गुफा|गुफ़ा", {"cave"}),
]
_PRX = [(name, re.compile(rf"^(?:{pat})$", re.I), kits) for name, pat, kits in PLACES]
MAX_PLACES = 2


def place_named(word: str):
    """(place, the sets that are that place) for a word that names a place or building, else None."""
    for name, rx, kits in _PRX:
        if rx.match(word):
            return name, kits
    return None


def place_kits(name: str) -> set:
    return next((kits for n, _rx, kits in _PRX if n == name), set())
_STAR, _FALL, _SNOW = (re.compile(rf"^(?:{p})$", re.I) for p in (STAR, FALL, SNOW))
MEMORY = re.compile(r"remember|dream|wish|imagine|used to|once upon|yaad|sapna|kaash|socho|याद|सपना|सपने|काश|सोचो|"
                    r"कल्पना|बचपन|पुराना|पुरानी", re.I)
_STRIP = re.compile(r"[^\wऀ-ॿ-]+")
FX_DURATION = {"lightning": 1.6, "fireworks": 5.0, "falling_stars": 5.0, "birds": 5.0, "sparkles": 2.0, "wind": 4.0,
               "stars": 6.0}
STAY = {"rain", "snowfall", "rainbow", "moon", "sun", "butterflies"}   # these stay to the end of the scene
SKY_FX = {"falling_stars", "stars", "fireworks", "rainbow", "moon", "sun", "birds", "lightning"}
MAX_PROPS, MAX_FX = 3, 2


def _key(w: str) -> str:
    return _STRIP.sub("", str(w)).lower()


def _match(word: str):
    for name, rx, kind, how in _RX:
        if rx.match(word):
            return name, kind, how
    return None


def thing_named(text: str):
    """The lexicon entry a free-form "show" thing points to ("a red car" → car), or None."""
    for w in str(text).split():
        m = _match(_key(w))
        if m:
            return m
        p = place_named(_key(w))
        if p:
            return p[0], "place", "far"
    return None


def find_cues(lines: list[dict], spans: list, words: list[dict], scene_end: float) -> list[dict]:
    """[{name, kind, how, t0, t1, line, bubble}] in time order, at most MAX_PROPS props and MAX_FX effects."""
    cues: list[dict] = []
    seen: set[str] = set()

    def line_at(t: float) -> int:
        for i, sp in enumerate(spans):
            if sp[0] - 0.05 <= t <= sp[1] + 0.05:
                return i
        return -1

    def add(name, kind, how, t, li):
        if name in seen:
            return
        if kind == "prop" and sum(c["kind"] == "prop" for c in cues) >= MAX_PROPS:
            return
        if kind == "fx" and sum(c["kind"] == "fx" for c in cues) >= MAX_FX:
            return
        if kind == "place" and sum(c["kind"] == "place" for c in cues) >= MAX_PLACES:
            return
        text = str(lines[li].get("text", "")) if 0 <= li < len(lines) else ""
        bubble = kind in ("prop", "place") and bool(MEMORY.search(text)) and str(lines[li].get("speaker", "")).lower() != "narrator"
        t1 = scene_end if (kind in ("prop", "place") and not bubble) or name in STAY else min(scene_end, t + FX_DURATION.get(name, 4.0))
        if bubble:
            t1 = min(scene_end, t + 3.6)
        seen.add(name)
        cues.append({"name": name, "kind": kind, "how": "bubble" if bubble else how, "t0": round(max(0.0, t), 3),
                     "t1": round(t1, 3), "line": li})

    # 1. what the script asks for
    for i, ln in enumerate(lines):
        for item in ln.get("show") or []:
            thing = item.get("thing") if isinstance(item, dict) else str(item)
            m = thing_named(thing or "")
            if m and i < len(spans):
                how = (item.get("how") if isinstance(item, dict) else "") or m[2]
                add(m[0], m[1], "bubble" if how == "bubble" else m[2], spans[i][0] + 0.3, i)
    # 2. words said, line by line (a line's own words decide "falling stars" vs "stars", "snowfall")
    keyed = [dict(w, k=_key(w.get("w", ""))) for w in words]
    for w in keyed:
        k = w["k"]
        if not k:
            continue
        li = line_at(float(w["s"]))
        same_line = [x["k"] for x in keyed if line_at(float(x["s"])) == li]
        if _STAR.match(k):
            add("falling_stars" if any(_FALL.match(x) for x in same_line) else "stars", "fx", "sky", w["s"], li)
            continue
        if _SNOW.match(k) and any(_FALL.match(x) for x in same_line):
            add("snowfall", "fx", "around", w["s"], li)
            continue
        m = _match(k)
        if m:
            add(m[0], m[1], m[2], w["s"], li)
            continue
        p = place_named(k)
        if p:
            add(p[0], "place", "far", w["s"], li)
    cues.sort(key=lambda c: c["t0"])
    return cues
