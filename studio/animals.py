"""Animal characters sound like animals: a dog's "भौं-भौं!" is a bark, not a voice reading the word.

    animal_kind(character)      -> "dog" | "cat" | ... | ""   (from the character's species, else its look)
    split_line(text, kind)      -> (the animal's noises [(token, effect)], the words it really says)
    noise_clip(noises)          -> the samples of those noises, one after another, and when each one starts

The sounds themselves are made in studio/sfx.py (dog_bark, cat_meow, cow_moo, lion_roar, ...). A recording of your
own in <data>/music/sfx/<effect>.wav|mp3 (for example dog_bark.wav) replaces the built-in one.
"""
from __future__ import annotations

import re

import numpy as np

from studio import sfx

_DEV = "[ऀ-ॿ]*"     # the rest of a Hindi word (matras, anusvara, nukta)


def _en(words: str) -> str:
    return rf"\b(?:{words})\b"


# kind: (who it is: English words | Hindi words, its usual sound, [(a noise written in a line, its sound)])
ANIMALS = [
    ("dog", _en("dogs?|puppy|puppies|pup|hound|doggy|kutta|kutte") + "|कुत्त|पिल्ल|डॉगी", "dog_bark",
     [(r"गुर+" + _DEV + "|gr+|ग्र" + _DEV, "dog_growl"), (r"कूँ+|कूं+|कू+|whine|ku+", "dog_whine"),
      (r"भौं|भौ|भों|भो|bho+w*|bhau|bow+|wo+f|woof|arf|वूफ|वफ", "dog_bark")]),
    ("cat", _en("cats?|kitten|kitty|billi") + "|बिल्ल", "cat_meow",
     [(r"hiss+|फ+|s{3,}", "cat_hiss"), (r"मयाऊ" + _DEV + "|मयाउ" + _DEV + "|मयू" + _DEV + "|meo*w|mia+o*w|mew|म्याऊ" + _DEV, "cat_meow")]),
    ("cow", _en("cows?|bull|ox|calf|buffalo|gaay|gai") + "|गाय|बैल|बछड़|भैंस", "cow_moo",
     [(r"बाँ+|बां+|मूँ+|मूं+|मू+|mo+|hamba|हमबा|हम्बा|bha+", "cow_moo")]),
    ("lion", _en("lions?|tigers?|leopard|cheetah|panther|sher|bagh|lioness") + "|शेर|बाघ|चीता|तेंदुआ", "lion_roar",
     [(r"दहाड़" + _DEV + "|roa*r|gr+|गुर+" + _DEV + "|ra+", "lion_roar")]),
    ("bear", _en("bears?|bhalu") + "|भालू", "dog_growl",
     [(r"गुर+" + _DEV + "|gr+|roa*r|दहाड़" + _DEV, "dog_growl")]),
    ("bird", _en("birds?|parrot|sparrow|myna|cuckoo|robin|pigeon|chick|tota|chidiya|koyal") +
     "|चिड़िया|चिडिया|तोता|मैना|कोयल|कबूतर|गौरैया|पंछी|पक्षी", "bird",
     [(r"ची+ं*|चीं|चूँ+|चूं+|tweet|chirp|cheep|कुहू|कू+|co+|टें+|टे+|chee+", "bird")]),
    ("duck", _en("ducks?|duckling|batakh") + "|बत्तख|बतख", "duck_quack",
     [(r"quack|kwak|कवैक|क्वैक|कवाक|कैं+", "duck_quack")]),
    ("goat", _en("goats?|sheep|lamb|bakri|bhed") + "|बकरी|बकरा|भेड़|मेमन", "goat_baa",
     [(r"मैं+|में+|मे+|बे+|ba+|ble+t|me+h*", "goat_baa")]),
    ("horse", _en("horses?|pony|ghoda|colt|mare") + "|घोड़|घोड", "horse_neigh",
     [(r"हिन" + _DEV + "|ne+igh|nei+|हीं+|hi+n" + _DEV, "horse_neigh")]),
    ("elephant", _en("elephants?|hathi|haathi") + "|हाथी", "elephant_trumpet",
     [(r"चिंघाड़" + _DEV + "|trumpet|toot|पूँ+|पैं+|पो+ं*|pa+w*|pe+", "elephant_trumpet")]),
    ("crow", _en("crows?|raven|kauwa|kauva") + "|कौआ|कौवा", "crow_caw",
     [(r"काँव+|कांव+|काँ+|कां+|caw+|kaw+", "crow_caw")]),
    ("rooster", _en("rooster|roosters|hen|hens|chicken|cock|murga|murgi") + "|मुर्ग|मुरग", "rooster",
     [(r"कूँ+|कूं+|कुकड़ू" + _DEV + "|कुकडू" + _DEV + "|kukdu" + _DEV + "|kukdukoo|cock|dodle|do+|cluck|बक+|कुड़" + _DEV, "rooster")]),
    ("frog", _en("frogs?|toad|mendhak") + "|मेंढक|मेढक", "frog_croak",
     [(r"टर+" + _DEV + "|ribbit|croak|tar+", "frog_croak")]),
    ("wolf", _en("wolf|wolves|jackal|fox|bhediya|siyar") + "|भेड़िया|सियार|लोमड़ी", "wolf_howl",
     [(r"औ+|आ+ऊ+|हू+|howl|awo+|au+|u+", "wolf_howl")]),
    ("snake", _en("snakes?|cobra|python|serpent|naag|saanp") + "|साँप|सांप|नाग", "snake_hiss",
     [(r"स+|हिस" + _DEV + "|s+|hiss+|फुफ" + _DEV, "snake_hiss")]),
    ("monkey", _en("monkeys?|ape|chimp|chimpanzee|bandar|langur") + "|बंदर|लंगूर", "monkey",
     [(r"ऊ+|आ+|हू+|ची+|o+h*|a+h*|che+|ki+|ू+", "monkey")]),
    ("pig", _en("pigs?|piglet|suar") + "|सूअर|सुअर", "pig_oink",
     [(r"oink|ओइंक|घुर+" + _DEV + "|ghur+", "pig_oink")]),
    ("owl", _en("owls?|ullu") + "|उल्लू", "owl_hoot",
     [(r"हू+|ho+|who+|hu+", "owl_hoot")]),
    ("donkey", _en("donkeys?|gadha|mule") + "|गधा|गधे", "donkey",
     [(r"ढेंचू" + _DEV + "|ढेंचु" + _DEV + "|he+-?haw|he+|haw|dhenchu", "donkey")]),
]
_KIND = [(k, re.compile(who, re.I), usual, [(re.compile(rf"^(?:{p})$", re.I), name) for p, name in noises])
         for k, who, usual, noises in ANIMALS]
# long sounds are not repeated as often as a bark
LONG = {"cow_moo", "lion_roar", "wolf_howl", "horse_neigh", "elephant_trumpet", "dog_growl", "rooster", "donkey"}
# noises that are also everyday words (मैं "I", में "in", हो, आ, a, do...): a noise only when said twice or more in a
# row ("मैं-मैं") or when the whole line is noises
AMBIGUOUS = {"मैं", "में", "मे", "बे", "आ", "ऊ", "हू", "हो", "कू", "ची", "a", "o", "u", "he", "me", "ba", "do", "ho", "hu",
             "co", "ah", "oh", "ki", "pe", "s", "स"}
_SPLIT = re.compile(r"[\s\-–—,!?.।॥…\"'“”‘’:;~]+")
_STAGE = re.compile(r"\([^)]*\)|\[[^\]]*\]|\*[^*]*\*")


def stage_free(text: str) -> str:
    """A line without its stage directions: "(चिंटू को सहलाते हुए) भौं-भौं!" -> "भौं-भौं!". Nobody reads those aloud."""
    return re.sub(r"\s{2,}", " ", _STAGE.sub(" ", text or "")).strip()


def animal_kind(character: dict | None) -> str:
    """What animal a character is ("" for people, spirits, robots...): from its species, else from its look."""
    if not character:
        return ""
    for field in ("species", "visual_anchor"):
        text = str(character.get(field) or "")
        if not text:
            continue
        for k, who, _usual, _noises in _KIND:
            if who.search(text):
                return k
        if field == "species":       # a species was given and it is no animal: the look is not asked
            return ""
    return ""


def _norm(tok: str) -> str:
    """The same noise written in many ways: no halant, repeated letters once ("गुर्र्र्र" -> "गुर", "woooof" -> "wof")."""
    return re.sub(r"(.)\1+", r"\1", tok.replace("्", "").lower())


ONE_CALL = {"rooster", "donkey"}     # "कुकड़ू-कूँ", "hee-haw": the parts of one call, heard once


def _one_call(sounds: list) -> list:
    out = []
    for tok, name in sounds:
        if out and name in ONE_CALL and out[-1][1] == name:
            out[-1] = (out[-1][0] + "-" + tok, name)
        else:
            out.append((tok, name))
    return out


def split_line(text: str, kind: str) -> tuple[list[tuple[str, str]], str]:
    """The animal's noises in a line [(as written, effect)] and the words it really says (may be "")."""
    entry = next((e for e in _KIND if e[0] == kind), None)
    clean = stage_free(text)
    if not entry or not clean:
        return [], clean
    _k, _who, _usual, noises = entry
    toks = [t for t in _SPLIT.split(clean) if t]
    hits = [next((name for rx, name in noises if rx.match(_norm(t)) or rx.match(t.lower())), None) for t in toks]
    if all(hits):                       # the whole line is the animal's noises
        return _one_call(list(zip(toks, hits))), ""
    # a talking animal: only the noises before its first word and after its last one, e.g. "भौं-भौं! चलो चिंटू!"
    first = next(i for i, h in enumerate(hits) if not h)
    last = max(i for i, h in enumerate(hits) if not h)
    keep = [False] * len(toks)
    for run in (range(0, first), range(last + 1, len(toks))):
        run = list(run)
        if run and (len(run) >= 2 or _norm(toks[run[0]]) not in AMBIGUOUS):
            for i in run:
                keep[i] = True
    sounds = _one_call([(toks[i], hits[i]) for i in range(len(toks)) if keep[i]])
    rest = [toks[i] for i in range(len(toks)) if not keep[i]]
    if not sounds:
        return [], clean
    # the words it says, as written (punctuation kept), without the noises
    said = clean
    for tok, _n in sounds:
        said = re.sub(re.escape(tok) + r"[\-–—]?", " ", said, count=1)
    said = re.sub(r"[\s,\-–—]+([!?.।…])", r"\1", said)            # "हूँ, - !" -> "हूँ!"
    said = re.sub(r"([!?.।…])(?:\s*[!?.।…])+", r"\1", said)        # "! !" -> "!"
    said = re.sub(r"^[\s\-–—,!?.।…]+|[\s\-–—,]+$", "", re.sub(r"\s{2,}", " ", said)).strip()
    return sounds, (said if rest else "")


def noise_clip(sounds: list[tuple[str, str]]) -> tuple[np.ndarray, list[tuple[str, float, float]]]:
    """The noises one after another (a bark is short, a moo long; at most 5, long ones at most 2), and when each
    one is heard: [(as written, start, end)] in seconds."""
    out, marks, t = [], [], 0.0
    longs = 0
    for k, (tok, name) in enumerate(sounds[:5]):
        if name in LONG:
            longs += 1
            if longs > 2:
                continue
        x = sfx.effect(name)
        if x is None:
            continue
        x = x * (0.85 + 0.15 * ((k * 7) % 3) / 2)        # each bark a little different in strength
        gap = 0.12 if name not in LONG else 0.25
        out.append(x.astype(np.float32))
        out.append(np.zeros(int(gap * sfx.SR), dtype=np.float32))
        marks.append((tok, round(t, 3), round(t + len(x) / sfx.SR, 3)))
        t += len(x) / sfx.SR + gap
    if not out:
        return np.zeros(0, dtype=np.float32), []
    return np.concatenate(out[:-1]), marks
