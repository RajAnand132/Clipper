"""Toon character designs: turn a Character Vault entry (name, species, look description) into the design the 3D
runtime builds (web/studio3d/runtime.js + parts.js). Works for English and Hindi descriptions.

Any kind of character is built from four bodies (human, animal, robot, blob) plus parts: costumes and features
(helmets, capes, coats, wings, horns, tails, pads…), something held (a bat, a wand, a sword…), a pose (zombie,
float, proud…) and an effect (ghostly, glowing, shadowy). Nothing is tied to a niche.

Where the design comes from:
  1. the character's own `toon` dict: written by the AI designer (studio/concepts.py design_toon) when the character
     is created, or by hand. It wins.
  2. otherwise these word rules (ROLE_RULES, ANIMALS…), which already cover the common jobs, creatures and animals.
"""
from __future__ import annotations

import hashlib
import re

# kind -> (type, defaults)
ANIMALS = {
    "bear":     {"fur": "#9a6431", "belly": "#f0cf95", "ears": "round", "snout": "bear", "tail": "short", "scale": 1.12},
    "panda":    {"fur": "#f4f4f4", "belly": "#ffffff", "ears": "round", "snout": "bear", "tail": "short", "scale": 1.1, "earColor": "#222222"},
    "cat":      {"fur": "#f2a23a", "belly": "#fff1d6", "ears": "pointy", "snout": "cat", "tail": "long", "scale": 0.82},
    "tiger":    {"fur": "#f28a1f", "belly": "#fff1d6", "ears": "round", "snout": "cat", "tail": "long", "scale": 1.05},
    "lion":     {"fur": "#e8b04a", "belly": "#fff1c9", "ears": "round", "snout": "cat", "tail": "long", "scale": 1.1, "mane": "#a8571f"},
    "dog":      {"fur": "#c98a4b", "belly": "#f6e2c4", "ears": "floppy", "snout": "dog", "tail": "short", "scale": 0.9, "earColor": "#7a4a26"},
    "fox":      {"fur": "#e8692a", "belly": "#fff4e6", "ears": "pointy", "snout": "cat", "tail": "bushy", "scale": 0.88},
    "rabbit":   {"fur": "#f4f1ec", "belly": "#ffffff", "ears": "long", "snout": "small", "tail": "short", "scale": 0.8},
    "mouse":    {"fur": "#a8a8b0", "belly": "#e6e6ec", "ears": "big_round", "snout": "small", "tail": "long", "scale": 0.62},
    "monkey":   {"fur": "#7a4a26", "belly": "#f0cf95", "ears": "round", "snout": "monkey", "tail": "long", "scale": 0.9},
    "elephant": {"fur": "#9aa4b4", "belly": "#c3cad6", "ears": "elephant", "snout": "trunk", "tail": "short", "scale": 1.25},
    "pig":      {"fur": "#f4a6b0", "belly": "#ffd0d6", "ears": "pointy", "snout": "pig", "tail": "curly", "scale": 0.9},
    "cow":      {"fur": "#f4f4f4", "belly": "#f4c8c8", "ears": "horns", "snout": "pig", "tail": "long", "scale": 1.1},
    "deer":     {"fur": "#b9773a", "belly": "#f6e2c4", "ears": "pointy", "snout": "dog", "tail": "short", "scale": 0.95},
    "bird":     {"fur": "#3fa7e0", "belly": "#fff1c9", "ears": "none", "snout": "beak", "tail": "short", "scale": 0.72, "kind": "bird"},
    "owl":      {"fur": "#8a6a4a", "belly": "#e8d3b0", "ears": "pointy", "snout": "beak", "tail": "short", "scale": 0.75, "kind": "bird", "bigEyes": True},
    "duck":     {"fur": "#fff6d8", "belly": "#ffffff", "ears": "none", "snout": "beak", "tail": "short", "scale": 0.72, "kind": "bird"},
    "frog":     {"fur": "#5cbf4a", "belly": "#d8f0a8", "ears": "none", "snout": "small", "tail": "none", "scale": 0.7, "bigEyes": True},
    "squirrel": {"fur": "#b9652f", "belly": "#f6e2c4", "ears": "pointy", "snout": "small", "tail": "bushy", "scale": 0.68},
    "wolf":     {"fur": "#8d939c", "belly": "#e6e6ec", "ears": "pointy", "snout": "dog", "tail": "bushy", "scale": 1.05},
    "goat":     {"fur": "#f0ece4", "belly": "#ffffff", "ears": "horns", "snout": "dog", "tail": "short", "scale": 0.9},
    "dino":     {"fur": "#6cbf4a", "belly": "#f0e08a", "ears": "none", "snout": "dog", "tail": "dragon", "scale": 1.15},
    "dragon":   {"fur": "#3f9a3a", "belly": "#f2c12e", "ears": "none", "snout": "croc", "tail": "dragon", "scale": 1.2,
                 "parts": [{"part": "wings_bat", "color": "#2f6a2a"}, {"part": "horns", "color": "#f3ead6"}, {"part": "spikes"}]},
    "crocodile": {"fur": "#4f8a3a", "belly": "#d8e8a0", "ears": "none", "snout": "croc", "tail": "dragon", "scale": 1.05,
                  "pattern": "scales", "patternColor": "#3a6a2a"},
    "horse":    {"fur": "#8a5a2b", "belly": "#c98a4b", "ears": "pointy", "snout": "long", "tail": "long", "scale": 1.15, "mane": "#3b2414"},
    "zebra":    {"fur": "#f4f4f4", "belly": "#ffffff", "ears": "pointy", "snout": "long", "tail": "long", "scale": 1.1,
                 "pattern": "stripes", "patternColor": "#1a1a1a", "mane": "#1a1a1a"},
    "unicorn":  {"fur": "#ffffff", "belly": "#fbe8ff", "ears": "pointy", "snout": "long", "tail": "bushy", "scale": 1.05,
                 "mane": "#ff8ad8", "parts": [{"part": "horns", "color": "#f2c14e"}]},
    "donkey":   {"fur": "#9aa4b4", "belly": "#e6e6ec", "ears": "long", "snout": "long", "tail": "long", "scale": 1.0},
    "camel":    {"fur": "#d9a066", "belly": "#f0cf95", "ears": "small", "snout": "long", "tail": "short", "scale": 1.2},
    "snake":    {"fur": "#5cbf4a", "belly": "#f0e08a", "ears": "none", "snout": "small", "tail": "long", "scale": 0.8,
                 "arms": False, "legs": False, "pattern": "spots", "patternColor": "#2f6a2a"},
    "fish":     {"fur": "#ff8a1f", "belly": "#ffffff", "ears": "none", "snout": "small", "tail": "fish", "scale": 0.7,
                 "arms": False, "legs": False, "pattern": "stripes", "patternColor": "#ffffff"},
    "shark":    {"fur": "#7a8a9c", "belly": "#ffffff", "ears": "none", "snout": "croc", "tail": "fish", "scale": 1.1,
                 "arms": False, "legs": False},
    "turtle":   {"fur": "#7ab84a", "belly": "#f0e08a", "ears": "none", "snout": "small", "tail": "short", "scale": 0.8,
                 "parts": [{"part": "shell", "color": "#5a7a2a"}]},
    "penguin":  {"fur": "#2a2a2a", "belly": "#ffffff", "ears": "none", "snout": "beak", "tail": "short", "scale": 0.75, "kind": "bird"},
    "parrot":   {"fur": "#3fb14a", "belly": "#f2c12e", "ears": "none", "snout": "beak", "tail": "long", "scale": 0.7, "kind": "bird"},
    "peacock":  {"fur": "#1f6fd0", "belly": "#1fa2a0", "ears": "none", "snout": "beak", "tail": "bushy", "scale": 0.85, "kind": "bird",
                 "parts": [{"part": "antenna", "color": "#1fa2a0"}]},
    "eagle":    {"fur": "#6b4423", "belly": "#ffffff", "ears": "none", "snout": "beak", "tail": "short", "scale": 0.85, "kind": "bird"},
    "leopard":  {"fur": "#f2b23a", "belly": "#fff1d6", "ears": "round", "snout": "cat", "tail": "long", "scale": 1.0,
                 "pattern": "spots", "patternColor": "#3b2414"},
    "giraffe":  {"fur": "#f2c14e", "belly": "#fff1c9", "ears": "pointy", "snout": "long", "tail": "long", "scale": 1.3,
                 "pattern": "spots", "patternColor": "#a8571f", "parts": [{"part": "antenna", "color": "#a8571f"}]},
    "hen":      {"fur": "#ffffff", "belly": "#fff6d8", "ears": "none", "snout": "beak", "tail": "short", "scale": 0.7, "kind": "bird",
                 "parts": [{"part": "mohawk", "color": "#d8343c"}]},
}

KEYWORDS = [  # first match wins
    (r"robot|android|cyborg|रोबोट|बॉट", "robot"),
    (r"dragon|ड्रैगन", "dragon"), (r"crocodile|alligator|\bcroc\b|मगरमच्छ|घड़ियाल", "crocodile"), (r"unicorn", "unicorn"),
    (r"zebra|ज़ेबरा", "zebra"), (r"\bhorse|pony|घोड़ा|घोड़ी", "horse"), (r"donkey|गधा", "donkey"), (r"camel|ऊँट|ऊंट", "camel"),
    (r"snake|serpent|cobra|python|नाग|सांप|साँप", "snake"), (r"shark|शार्क", "shark"), (r"\bfish\b(?!\s*tail)|मछली", "fish"),
    (r"turtle|tortoise|कछुआ", "turtle"), (r"penguin|पेंगुइन", "penguin"), (r"parrot|तोता", "parrot"), (r"peacock|मोर", "peacock"),
    (r"eagle|hawk|falcon|बाज|चील", "eagle"), (r"leopard|cheetah|jaguar|तेंदुआ|चीता", "leopard"), (r"giraffe|जिराफ", "giraffe"),
    (r"\bhen\b|chicken|rooster|मुर्गी|मुर्गा", "hen"),
    (r"panda|पांडा", "panda"), (r"\bbears?\b|भालू|bhalu", "bear"), (r"kitten|\bcats?\b|बिल्ली|billi", "cat"),
    (r"tiger|बाघ|शेरा", "tiger"), (r"\blion|शेर|sher\b", "lion"), (r"puppy|\bdog|कुत्ता|पिल्ला|kutta", "dog"),
    (r"\bfox|लोमड़ी", "fox"), (r"rabbit|bunny|\bhare\b|खरगोश", "rabbit"), (r"mouse|\brat\b|चूहा|chuha", "mouse"),
    (r"monkey|\bape\b|बंदर|bandar", "monkey"), (r"elephant|हाथी|haathi|hathi", "elephant"), (r"\bpig|piglet|सुअर", "pig"),
    (r"\bcow|\bbull|calf|गाय|बैल", "cow"), (r"deer|fawn|हिरण", "deer"), (r"\bowl|उल्लू", "owl"), (r"duck|बत्तख", "duck"),
    (r"bird|sparrow|\bcrows?\b|\bchick\b|चिड़िया|कौआ|पक्षी|परिंदा|पंछी|panchhi|pakshi", "bird"), (r"frog|toad|मेंढक", "frog"),
    (r"squirrel|गिलहरी", "squirrel"), (r"wolf|भेड़िया", "wolf"), (r"goat|बकरी", "goat"), (r"dino|t-?rex|डायनासोर", "dino"),
    (r"blob|slime|rice ?ball|onigiri|\begg\b|dumpling|star creature|critter|cloud (?:baby|creature|friend)|बादल", "critter"),
]

# Jobs, roles and creatures: (word pattern, design changes). Several can apply ("old pirate king").
# Human roles keep a human body and add a costume; creatures change the body, skin, pose or effect.
ROLE_RULES = [
    # cricket by role, so a team is not eleven copies of one batsman
    (r"wicket-?keeper|keeper|विकेटकीपर|विकेट-कीपर", {"parts": [{"part": "cricket_helmet", "color": "#1d4fa0"}, {"part": "leg_pads"}, {"part": "gloves", "color": "#f2c12e"}], "pose": "hands_on_hips", "_adult": True}),
    (r"batsman|batter|opener|opening|बल्लेबाज", {"parts": [{"part": "cricket_helmet", "color": "#1d4fa0"}, {"part": "leg_pads"}, {"part": "gloves"}], "hold": "bat", "_adult": True}),
    (r"bowler|pacer|spinner|गेंदबाज", {"hat": "cap", "hatColor": "#1d4fa0", "hold": "ball", "_adult": True}),
    (r"cricket|captain|क्रिकेट|कप्तान", {"top": "#f4f4f4", "bottom": "#f4f4f4", "hat": "cap", "hatColor": "#1d4fa0", "_adult": True}),
    (r"football|soccer|फुटबॉल", {"parts": [{"part": "jersey_number"}], "hold": "ball", "_adult": True}),
    (r"hockey|हॉकी", {"parts": [{"part": "helmet"}], "hold": "hockey_stick"}),
    (r"tennis|badminton", {"top": "#f4f4f4", "hold": "racket"}),
    (r"boxer|boxing|wrestler|पहलवान", {"parts": [{"part": "gloves", "color": "#d8343c"}, {"part": "belt", "color": "#f2c14e"}], "pose": "proud", "_adult": True}),
    (r"police|\bcops?\b|constable|inspector|पुलिस|दरोगा|हवलदार", {"top": "#c8a96a", "bottom": "#8a7448", "parts": [{"part": "police_cap", "color": "#8a7448"}, {"part": "badge"}, {"part": "belt"}], "_adult": True}),
    (r"soldier|army|jawan|military|सैनिक|फौजी|जवान", {"top": "#4a5d3a", "bottom": "#4a5d3a", "parts": [{"part": "helmet", "color": "#4a5d3a"}, {"part": "belt"}, {"part": "boots"}], "_adult": True}),
    (r"doctor|surgeon|डॉक्टर", {"parts": [{"part": "lab_coat"}, {"part": "stethoscope"}], "_adult": True}),
    (r"nurse|नर्स", {"top": "#f4f4f4", "parts": [{"part": "apron"}], "_adult": True}),
    (r"scientist|professor|inventor|वैज्ञानिक", {"parts": [{"part": "lab_coat"}], "glasses": True, "_adult": True}),
    (r"chef|cook|baker|रसोइया|हलवाई", {"top": "#f4f4f4", "parts": [{"part": "chef_hat"}, {"part": "apron"}]}),
    (r"astronaut|spaceman|अंतरिक्ष यात्री", {"top": "#f4f4f4", "bottom": "#f4f4f4", "parts": [{"part": "spacesuit"}, {"part": "space_helmet"}, {"part": "oxygen_tank"}, {"part": "boots", "color": "#c7cdd6"}]}),
    (r"firefighter|fireman|अग्निशमन", {"top": "#d8343c", "bottom": "#2a2a2a", "parts": [{"part": "hard_hat", "color": "#d8343c"}, {"part": "boots"}], "_adult": True}),
    (r"builder|construction|engineer|mechanic|worker|मिस्त्री|मज़दूर", {"parts": [{"part": "hard_hat"}, {"part": "vest", "color": "#ff8a1f"}], "_adult": True}),
    (r"pirate|समुद्री डाकू", {"parts": [{"part": "eyepatch"}, {"part": "sash", "color": "#d8343c"}, {"part": "boots"}], "hold": "sword", "hat": "fedora", "hatColor": "#2a2a2a"}),
    (r"ninja|निंजा", {"top": "#1a1a1a", "bottom": "#1a1a1a", "parts": [{"part": "mask", "color": "#1a1a1a"}, {"part": "headband", "color": "#d8343c"}], "hold": "sword"}),
    (r"superhero|super hero|hero with|caped|सुपरहीरो", {"parts": [{"part": "cape"}, {"part": "mask"}, {"part": "belt", "color": "#f2c12e"}, {"part": "boots"}], "pose": "proud"}),
    (r"detective|जासूस", {"parts": [{"part": "coat", "color": "#9a7a52"}], "hat": "fedora", "hold": "magnifier", "_adult": True}),
    (r"singer|rockstar|गायक|गायिका", {"hold": "microphone"}),
    (r"painter|artist|चित्रकार", {"parts": [{"part": "beret"}, {"part": "apron", "color": "#c7cdd6"}], "hold": "paintbrush"}),
    (r"farmer|किसान", {"hat": "turban", "parts": [{"part": "vest", "color": "#9a6431"}], "hold": "stick", "_adult": True}),
    (r"teacher|शिक्षक|टीचर|masterji|मास्टर", {"glasses": True, "hold": "book", "_adult": True}),
    (r"student|schoolboy|schoolgirl|विद्यार्थी|छात्र", {"parts": [{"part": "backpack"}, {"part": "tie", "color": "#1d4fa0"}]}),
    (r"businessman|\bboss\b|lawyer|manager|वकील", {"parts": [{"part": "coat", "color": "#2a2f45"}, {"part": "tie"}], "hold": "briefcase", "_adult": True}),
    (r"priest|pandit|pujari|पंडित|पुजारी", {"top": "#ff8a1f", "parts": [{"part": "garland"}, {"part": "bindi"}], "_adult": True}),
    (r"sage|rishi|sadhu|yogi|monk|ऋषि|साधु|संत|मुनि|योगी", {"top": "#ff8a1f", "parts": [{"part": "robe", "color": "#ff8a1f"}, {"part": "long_beard"}, {"part": "garland", "color": "#8a5a2b"}], "hold": "staff", "_old": True}),
    (r"\bking\b|emperor|maharaja|राजा|सम्राट|महाराज", {"hat": "crown", "parts": [{"part": "cape", "color": "#8e1f2a"}, {"part": "necklace"}, {"part": "mustache"}], "pose": "proud", "_adult": True}),
    (r"queen|empress|maharani|रानी|महारानी", {"parts": [{"part": "tiara"}, {"part": "gown", "color": "#8e5bd8"}, {"part": "necklace"}], "_adult": True}),
    (r"prince|राजकुमार", {"hat": "crown", "parts": [{"part": "cape", "color": "#2f4fb0"}, {"part": "sash"}]}),
    (r"princess|राजकुमारी", {"parts": [{"part": "tiara"}, {"part": "gown"}]}),
    (r"wizard|magician|sorcerer|जादूगर", {"parts": [{"part": "wizard_hat"}, {"part": "robe", "color": "#2f4fb0"}, {"part": "long_beard"}], "hold": "staff", "_old": True}),
    (r"witch|churail|daayan|चुड़ैल|डायन", {"parts": [{"part": "witch_hat", "color": "#2a1a3a"}, {"part": "robe", "color": "#2a1a3a"}], "hold": "broom", "skin": "#a8c890", "_old": True}),
    (r"zombie|ज़ॉम्बी|जॉम्बी", {"skin": "#8fb07a", "top": "#6b5a48", "bottom": "#4a4a5a", "parts": [{"part": "rags"}], "pose": "zombie", "eyes": "glowing", "eyeColor": "#d8ff6b", "_adult": True}),
    (r"skeleton|कंकाल", {"skin": "#f4f1e6", "top": "#f4f1e6", "bottom": "#f4f1e6", "parts": [{"part": "ribs"}], "eyes": "glowing", "eyeColor": "#111111", "_adult": True}),
    (r"mummy|ममी", {"skin": "#efe6d2", "top": "#efe6d2", "bottom": "#efe6d2", "parts": [{"part": "wraps"}, {"part": "bandage_head"}], "pose": "zombie", "eyes": "glowing", "eyeColor": "#ffd23f"}),
    (r"vampire|dracula|पिशाच", {"skin": "#e8e0e8", "top": "#1a1a1a", "parts": [{"part": "cape", "color": "#1a0a1a"}, {"part": "fangs"}], "eyes": "glowing", "eyeColor": "#d8343c", "_adult": True}),
    (r"devil|demon|asura|राक्षस|असुर|दानव|शैतान", {"skin": "#c0392b", "parts": [{"part": "horns"}, {"part": "devil_tail"}], "eyes": "glowing", "eyeColor": "#ffd23f"}),
    (r"ghost|\bspirits?\b|phantom|bhoot|भूत|आत्मा|प्रेत", {"_type": "blob", "body": "#eef2ff", "band": False, "effect": "ghostly", "eyes": "glowing", "eyeColor": "#111111"}),
    (r"shadow creature|shadow monster|shadow man|साया", {"effect": "shadowy", "eyes": "glowing", "eyeColor": "#ff3b30"}),
    (r"angel|देवदूत|फ़रिश्ता|फरिश्ता", {"top": "#ffffff", "parts": [{"part": "wings_feather"}, {"part": "halo"}, {"part": "robe", "color": "#ffffff"}], "effect": "glowing"}),
    (r"fairy|\bpari\b|(?<![\u0900-\u097F])परी", {"parts": [{"part": "wings_fairy"}, {"part": "tiara"}], "hold": "wand", "pose": "float", "_female": True}),
    (r"mermaid|jalpari|जलपरी", {"parts": [{"part": "fish_tail"}, {"part": "flower"}], "_female": True}),
    (r"genie|jinn|जिन्न", {"skin": "#5aa8f0", "parts": [{"part": "fish_tail", "color": "#5aa8f0"}, {"part": "vest", "color": "#8e5bd8"}], "hat": "turban", "effect": "glowing", "glowColor": "#7ad0ff", "pose": "float"}),
    (r"\bgod\b|goddess|deity|bhagwan|devta|devi|भगवान|देवता|देवी", {"hat": "crown", "parts": [{"part": "halo"}, {"part": "garland"}, {"part": "robe", "color": "#f2c14e"}], "effect": "glowing"}),
    (r"alien|martian|एलियन", {"skin": "#7ad06b", "parts": [{"part": "antenna", "color": "#d8ff6b"}, {"part": "third_eye", "color": "#111111"}], "eyes": "big"}),
    (r"monster|ogre|troll|yeti|दैत्य", {"_scale": 1.25, "parts": [{"part": "horns", "color": "#f3ead6"}, {"part": "fangs"}], "eyes": "glowing", "eyeColor": "#ffd23f"}),
    (r"cyclops", {"parts": [{"part": "third_eye", "color": "#ffffff"}]}),
]
HELD = [  # "holding a …" / "with a …" → the thing in the hand
    (r"\bbat\b|बल्ला", "bat"), (r"sword|तलवार", "sword"), (r"\bwand\b|छड़ी", "wand"), (r"staff|लाठी|डंडा", "staff"),
    (r"broom|झाड़ू", "broom"), (r"trident|trishul|त्रिशूल", "trident"), (r"spear|भाला", "spear"), (r"shield|ढाल", "shield"),
    (r"microphone|\bmic\b|माइक", "microphone"), (r"trophy|ट्रॉफी", "trophy"), (r"torch|मशाल", "torch"), (r"flashlight", "flashlight"),
    (r"magnif", "magnifier"), (r"flute|बांसुरी|बाँसुरी", "flute"), (r"paintbrush|brush", "paintbrush"), (r"briefcase", "briefcase"),
    (r"lantern|लालटेन", "lantern"), (r"umbrella|छाता", "umbrella"), (r"\bbook\b|किताब", "book"), (r"balloon|गुब्बारा", "balloons"),
    (r"\bphone\b|mobile|फ़ोन|फोन", "phone"), (r"\bkey\b|चाबी", "key"), (r"\bball\b|गेंद", "ball"), (r"candle|मोमबत्ती", "candle"),
]
WORN = [  # words for single pieces worn
    (r"\bcape\b|लबादा", "cape"), (r"lab coat|white coat|\bcoat\b|कोट", "coat"), (r"\brobe\b|चोगा", "robe"),
    (r"\bwings?\b|पंख", "wings_feather"), (r"horns?|सींग", "horns"), (r"halo", "halo"), (r"\bmask\b|नकाब", "mask"),
    (r"sunglasses|goggles|काला चश्मा", "sunglasses"), (r"eye ?patch", "eyepatch"), (r"\bbeard\b|दाढ़ी", "beard"),
    (r"mustache|moustache|मूंछ|मूँछ", "mustache"), (r"backpack|school bag|बस्ता", "backpack"), (r"\btie\b|टाई", "tie"),
    (r"bow ?tie", "bow_tie"), (r"necklace|हार\b", "necklace"), (r"\bbelt\b", "belt"), (r"\bboots\b", "boots"),
    (r"helmet|हेलमेट", "helmet"), (r"witch hat|pointed hat", "witch_hat"), (r"top hat", "top_hat"), (r"beret", "beret"),
    (r"beanie|woolly hat|ऊनी टोपी", "beanie"), (r"headband|bandana", "headband"), (r"tiara", "tiara"), (r"apron", "apron"),
    (r"stethoscope", "stethoscope"), (r"\bvest\b|jacket|जैकेट", "vest"), (r"saree|sari|साड़ी", "saree"), (r"gown|lehenga|लहंगा", "gown"),
    (r"bindi|बिंदी", "bindi"), (r"garland|माला", "garland"), (r"ponytail|चोटी", "ponytail"), (r"mohawk", "mohawk"), (r"medal", "medal"),
    (r"fangs|नुकीले दांत", "fangs"), (r"antenna", "antenna"), (r"glowing eyes|चमकती आँखें|चमकती आंखें", "_glow_eyes"),
]
HUMAN = (r"human|boy|girl|man\b|woman|kid|child|detective|scientist|doctor|teacher|king|queen|prince|princess|farmer|"
         r"cricket|batsman|bowler|player|police|soldier|chef|pirate|ninja|astronaut|nurse|priest|sage|monk|wizard|witch|"
         r"zombie|skeleton|mummy|vampire|mermaid|fairy|angel|alien|genie|singer|artist|worker|boss|officer|"
         r"grand|uncle|aunt|mother|father|mom|dad|baby|student|police|chef|wizard|witch|hero|लड़का|लड़की|बच्चा|बच्ची|"
         r"दादा|दादी|नाना|नानी|राजा|रानी|राजकुमार|राजकुमारी|आदमी|औरत|मां|पापा|अंकल|आंटी|किसान|शिक्षक|डॉक्टर|जासूस")

COLORS = {
    "red": "#d8343c", "लाल": "#d8343c", "blue": "#2f7fe0", "नीला": "#2f7fe0", "नीली": "#2f7fe0", "green": "#3f9a3a",
    "हरा": "#3f9a3a", "हरी": "#3f9a3a", "yellow": "#f2c12e", "पीला": "#f2c12e", "पीली": "#f2c12e", "orange": "#ff8a1f",
    "नारंगी": "#ff8a1f", "pink": "#ff6fa5", "गुलाबी": "#ff6fa5", "purple": "#8e5bd8", "बैंगनी": "#8e5bd8",
    "white": "#f4f4f4", "सफेद": "#f4f4f4", "black": "#2a2a2a", "काला": "#2a2a2a", "काली": "#2a2a2a", "brown": "#9a6431",
    "भूरा": "#9a6431", "भूरी": "#9a6431", "golden": "#e8b04a", "gold": "#e8b04a", "सुनहरा": "#e8b04a", "grey": "#9aa4b4",
    "gray": "#9aa4b4", "स्लेटी": "#9aa4b4", "silver": "#c7cdd6", "teal": "#1fa2a0", "cream": "#f3e3c3", "beige": "#e6d2b0",
}
SKINS = ["#f2c39a", "#e9b48a", "#d9a072", "#c68a5c", "#a96f45", "#8d5a38"]
CLOTHES = ["#2f7fe0", "#d8343c", "#3f9a3a", "#ff8a1f", "#8e5bd8", "#1fa2a0", "#f2c12e", "#ff6fa5"]


def _h(text: str) -> int:
    return int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)


def _colors(text: str) -> list[str]:
    found = []
    for m in re.finditer(r"[\wऀ-ॿ]+", text.lower()):
        c = COLORS.get(m.group(0))
        if c and c not in found:
            found.append(c)
    return found


ITEMS = [  # a colour word right before one of these words colours that part
    (r"cap|hat|topi|टोपी|pagdi|पगड़ी|turban|crown", "hatColor"),
    (r"shirt|t-shirt|tshirt|kurta|कुर्ता|top|dress|frock|saree|sari|साड़ी|jacket|coat|sweater|hoodie|uniform|robe|vest|"
     r"kit|jersey|tracksuit|जर्सी", "top"),
    (r"pants|trousers|shorts|jeans|skirt|lehenga|pajama|dhoti|लहंगा", "bottom"),
    (r"scarf|muffler|bandana|ribbon|bow|दुपट्टा", "accColor"),
    (r"hair|बाल", "hair"),
    (r"shoes|boots|sneakers|जूते", "shoes"),
    (r"fur|body|skin", "fur"),
]


def _bound_colors(text: str) -> dict:
    """'orange cap, blue shirt' -> {'hatColor': orange, 'top': blue}."""
    toks = re.findall(r"[\wऀ-ॿ-]+", text.lower())
    out = {}
    for i, tok in enumerate(toks):
        c = COLORS.get(tok)
        if not c:
            continue
        for nxt in toks[i + 1:i + 4]:   # "blue India cricket kit": the colour may sit three words before the piece
            key = next((k for pat, k in ITEMS if re.fullmatch(pat, nxt)), None)
            if key:
                out.setdefault(key, c)
                break
    return out


def design_for(character: dict, fmt: dict | None = None) -> dict:
    """The toon design for one character. Deterministic: the same character always looks the same."""
    name = str(character.get("name") or "Friend")
    species = str(character.get("species") or "")
    look = str(character.get("visual_anchor") or "")
    text = f"{species} {look} {name}".lower()
    n = int(character.get("look_seed") or 0)
    seed = _h(name.lower() + (f"#{n}" if n else ""))   # Re-render 3D Look moves to the next look number
    bound = _bound_colors(f"{species} {look}")
    colors = [c for c in _colors(f"{species} {look}") if c not in bound.values()]   # colours not tied to a part
    kind = next((k for pat, k in KEYWORDS if re.search(pat, text)), None)
    if not kind and not re.search(HUMAN, text):
        kind = None
    if kind == "robot":
        d = {"type": "robot", "body": colors[0] if colors else "#9fb4c8", "accent": colors[1] if len(colors) > 1 else
             CLOTHES[seed % len(CLOTHES)], "scale": 0.95}
    elif kind == "critter":
        d = {"type": "critter", "body": colors[0] if colors else "#f4f1ea",
             "accent": colors[1] if len(colors) > 1 else "#2c4a2a",
             "band": bool(re.search(r"rice|onigiri|seaweed|nori|band", text)), "ears": bool(re.search(r"ear|cat|fox", text)),
             "scale": 0.85}
    elif kind in ANIMALS:
        base = dict(ANIMALS[kind])
        d = {"type": "animal", **base}
        if colors:
            d["fur"] = colors[0]
        if re.search(r"scarf|muffler|दुपट्टा|मफलर", text):
            d["accessory"], d["accColor"] = "scarf", (colors[1] if len(colors) > 1 else "#d8343c")
        elif re.search(r"bandana", text):
            d["accessory"], d["accColor"] = "bandana", (colors[1] if len(colors) > 1 else "#f2c12e")
        elif re.search(r"\bbow\b|ribbon|रिबन", text):
            d["accessory"], d["accColor"] = "bow", (colors[1] if len(colors) > 1 else "#ff4f9a")
        elif re.search(r"\bhat\b|cap\b|टोपी", text):
            d["accessory"], d["accColor"] = "hat", (colors[1] if len(colors) > 1 else CLOTHES[seed % len(CLOTHES)])
        if re.search(r"baby|cub|little|tiny|small|छोटा|छोटी|बच्चा", text):
            d["scale"] = round(d["scale"] * 0.78, 2)
            d["bigEyes"] = True
    else:
        from studio import tts
        fem = tts.guess_gender(f"{species} {look} {name}") == "female"
        child = bool(re.search(r"boy|girl|kid|child|baby|little|student|लड़का|लड़की|बच्चा|बच्ची|छोटा|छोटी", text)) or \
            bool(re.search(r"\byoung\b", text) and not re.search(r"young (?:man|woman|lady|adult)", text))
        old = bool(re.search(r"grand(?:pa|ma|father|mother|dad|mom)|\bold\b|elder|elderly|aged|दादा|दादी|नाना|नानी|बूढ़ा|बूढ़ी|बुजुर्ग", text))
        audience = (fmt or {}).get("audience", "")
        if not child and not old and "kid" in audience and not re.search(r"man\b|woman|adult|uncle|aunt|mother|father|teacher|king|queen", text):
            child = True
        d = {"type": "human", "gender": "f" if fem else "m", "age": "old" if old else ("child" if child else "adult"),
             "skin": SKINS[seed % len(SKINS)], "hair": ["#2a180e", "#3b2414", "#1a1a1a", "#5a3a22"][seed % 4],
             "hairStyle": ("bun" if old else "long") if fem else ("spiky" if child and seed % 3 == 0 else "short"),
             "top": colors[0] if colors else CLOTHES[seed % len(CLOTHES)],
             "bottom": colors[1] if len(colors) > 1 else ("#394058" if not fem else CLOTHES[(seed + 3) % len(CLOTHES)]),
             "accent": CLOTHES[(seed + 5) % len(CLOTHES)],
             "scale": 0.8 if child else (0.95 if old else 0.9)}
        if re.search(r"\bcap\b|टोपी", text) or (child and not fem and seed % 2 == 0):
            d["hat"], d["hatColor"] = "cap", CLOTHES[(seed + 2) % len(CLOTHES)]
            d["_auto_hat"] = not re.search(r"\bcap\b|टोपी", text)
        if re.search(r"turban|पगड़ी|साफा", text):
            d["hat"] = "turban"
        if re.search(r"king|queen|prince|princess|राजा|रानी|राजकुमार|राजकुमारी|crown|मुकुट", text):
            d["hat"] = "crown"
        if re.search(r"detective|जासूस|fedora", text):
            d["hat"], d["hatColor"] = "fedora", "#4a3b2e"
        if re.search(r"glasses|spectacles|scientist|professor|चश्मा|वैज्ञानिक", text) or old:
            d["glasses"] = True
        if re.search(r"scarf|muffler", text):
            d["accessory"] = "scarf"
        if fem and child and seed % 2 == 0:
            d["accessory"], d["accColor"] = "bow", CLOTHES[(seed + 4) % len(CLOTHES)]
    # colours named for a part ("orange cap", "blue shirt", "red scarf") go exactly there
    if d["type"] == "human":
        for k in ("top", "bottom", "hair", "shoes", "accColor"):
            if k in bound:
                d[k] = bound[k]
        if "hatColor" in bound:
            d["hatColor"] = bound["hatColor"]
            d.setdefault("hat", "cap")
    elif d["type"] == "animal":
        if "fur" in bound:
            d["fur"] = bound["fur"]
        if "accColor" in bound:
            d["accColor"] = bound["accColor"]
        if "hatColor" in bound:
            d["accessory"], d["accColor"] = "hat", bound["hatColor"]
        if "top" in bound and not d.get("accessory"):
            d["accessory"], d["accColor"] = "bandana", bound["top"]
    elif "top" in bound:
        d["body"] = bound["top"]
    _apply_roles(d, text, seed, fmt)
    if d.get("type") == "human":   # a colour the description names for a piece wins over a role's default kit
        for k in ("top", "bottom", "hatColor"):
            if k in bound:
                d[k] = bound[k]
    if d.get("type") != "human" and re.search(r"crown|मुकुट|ताज", text) and not any(p.get("part") == "crown" for p in d.get("parts", [])):
        d["parts"] = list(d.get("parts") or []) + [{"part": "crown"}]
        if d.get("accessory") == "hat":
            d.pop("accessory", None)
    toon = character.get("toon")
    if isinstance(toon, dict):
        t = clean_toon(toon)
        # the word rules know this is a person or a named animal: the designer adds costume, colours and things
        # to hold, but keeps the body (a "spirited boy" stays a boy)
        sure = re.search(PERSON, text) if d.get("type") == "human" else (d.get("type") in ("animal", "robot", "critter"))
        if sure:
            t.pop("type", None)
        # whole-body looks (glowing, ghostly, shadowy, floating, glowing eyes) only for beings that are like that,
        # never because they hold a glowing lamp
        if not re.search(SUPERNATURAL, text):
            for k in ("effect", "glowColor"):
                t.pop(k, None)
            if t.get("eyes") == "glowing":
                t.pop("eyes")
                t.pop("eyeColor", None)
            if t.get("pose") == "float":
                t.pop("pose")
        if t.get("type") and t["type"] != d.get("type"):
            # the designer chose another body (a living cricket ball, not a cricketer): the word rules' costume goes
            d = {k: v for k, v in d.items() if k not in ("parts", "hold", "hat", "hatColor", "pose", "effect", "glasses",
                                                         "accessory", "eyes", "eyeColor")}
            if t["type"] == "critter":
                d.setdefault("band", False)
                d["body"] = t.get("top") or t.get("fur") or d.get("body") or "#f4f1ea"
                if t.get("bottom"):
                    d["accent"] = t["bottom"]
        if t.get("type") == "robot":
            d["body"], d["accent"] = t.get("top") or d.get("body", "#9fb4c8"), t.get("bottom") or d.get("accent", "#2fb7ff")
        d.update(t)
        # what the description names exactly ("orange cap, blue shirt") always wins over a design's variation
        if d.get("type") == "human":
            for k in ("top", "bottom", "hair", "shoes", "hatColor"):
                if k in bound:
                    d[k] = bound[k]
            if re.search(r"\bcap\b|टोपी", text) and not any(p["part"] in HEADGEAR for p in d.get("parts", []) if re.search(p["part"].split("_")[0], text)):
                d["hat"] = "cap"
                d["parts"] = [p for p in d.get("parts", []) if p["part"] not in HEADGEAR]
        elif d.get("type") == "animal" and "fur" in bound:
            d["fur"] = bound["fur"]
    return d


PERSON = (r"\b(?:boy|girl|man|woman|men|women|lady|kid|child|human|person|hero|heroine|uncle|aunt|grandpa|grandma|"
          r"old man|old woman|sage|king|queen|prince|princess|teacher|doctor|farmer|storyteller|narrator)\b|लड़का|लड़की|"
          r"आदमी|औरत|बच्चा|बच्ची|दादा|दादी|नाना|नानी|ऋषि|राजा|रानी|मुनि|साधु")
SUPERNATURAL = (r"ghost|\bspirits?\b|phantom|\bgod\b|goddess|deity|divine being|angel|genie|jinn|demon|devil|"
                r"zombie|vampire|skeleton|mummy|alien|monster|fairy|witch|wizard|robot|shadow|celestial being|"
                r"भूत|आत्मा|प्रेत|देवता|देवी|भगवान|परी|राक्षस|असुर|जिन्न|चुड़ैल")

# pieces that replace each other: only the first of a group is kept
EXCLUSIVE = [{"helmet", "cricket_helmet", "hard_hat", "space_helmet", "police_cap", "witch_hat", "wizard_hat", "top_hat",
              "chef_hat", "beret", "beanie"},
             {"wings_feather", "wings_bat", "wings_fairy", "wings_butterfly"}, {"beard", "long_beard"},
             {"coat", "lab_coat", "spacesuit"}, {"robe", "gown", "saree"}]
HEADGEAR = EXCLUSIVE[0] | {"tiara", "bandage_head"}


def _apply_roles(d: dict, text: str, seed: int, fmt: dict | None) -> None:
    """Jobs, creatures, held things and worn pieces named in the description."""
    parts = list(d.get("parts") or [])
    auto_hat = d.pop("_auto_hat", False)
    for pat, ch in ROLE_RULES:
        if not re.search(pat, text):
            continue
        if auto_hat:      # a role brings its own look: no default kids' cap on a zombie or a policeman
            d.pop("hat", None)
            d.pop("hatColor", None)
            auto_hat = False
        ch = dict(ch)
        if ch.get("_type") == "blob" and d.get("type") == "critter":
            continue   # already a living thing (a rice ball spirit, a slime): it keeps its own look
        if ch.pop("_type", None) == "blob":
            d.clear()
            d.update({"type": "critter", "body": "#eef2ff", "accent": "#c7cdd6", "band": False, "ears": False, "scale": 0.9})
        if d.get("type") == "human":
            if ch.pop("_adult", False) and d.get("age") == "child" and not re.search(r"boy|girl|kid|child|little|young|लड़का|लड़की|बच्चा", text):
                d["age"], d["scale"] = "adult", 0.9
            if ch.pop("_old", False) and not re.search(r"young|boy|girl|kid|little", text):
                d["age"], d["scale"] = "old", 0.95
            if ch.pop("_female", False):
                d["gender"] = "f"
        for k in ("_adult", "_old", "_female"):
            ch.pop(k, None)
        if "_scale" in ch:
            d["scale"] = round(d.get("scale", 1) * ch.pop("_scale"), 2)
        parts += ch.pop("parts", [])
        for k, v in ch.items():
            if k in ("hat", "hatColor") and d.get("type") != "human":
                continue
            d.setdefault(k, v) if k in ("top", "bottom") and d.get("_colors_named") else d.__setitem__(k, v)
    held = next((name for pat, name in HELD if re.search(pat, text)), None)
    if held and not d.get("hold"):
        d["hold"] = held
    have = {p["part"] for p in parts}
    for pat, name in WORN:
        if not re.search(pat, text):
            continue
        if name == "_glow_eyes":
            d["eyes"] = "glowing"
        elif name not in have:
            parts.append({"part": name})
            have.add(name)
    kept, used = [], set()
    for p in parts:
        grp = next((i for i, g in enumerate(EXCLUSIVE) if p["part"] in g), None)
        key = f"group{grp}" if grp is not None else p["part"]
        if key in used:
            continue
        used.add(key)
        kept.append(p)
    parts = kept
    if any(p["part"] in HEADGEAR for p in parts):    # a helmet or a witch hat replaces any cap or crown
        d.pop("hat", None)
    # colours named for a piece ("red cape") go to that piece
    for p in parts:
        m = re.search(r"([\wऀ-ॿ]+)\s+" + re.escape(p["part"].split("_")[0]), text)
        if m and m.group(1) in COLORS and "color" not in p:
            p["color"] = COLORS[m.group(1)]
    if parts:
        d["parts"] = parts


# ---------------------------------------------------------------- designs written by the AI (or by hand)
BODIES = ("human", "animal", "robot", "blob")
ENUMS = {
    "gender": ("m", "f"), "age": ("child", "adult", "old"),
    "hairStyle": ("short", "long", "bun", "spiky", "bald"),
    "hat": ("cap", "turban", "crown", "fedora", ""),
    "ears": ("round", "big_round", "long", "pointy", "floppy", "elephant", "small", "horns", "none"),
    "snout": ("bear", "dog", "cat", "small", "pig", "trunk", "beak", "monkey", "croc", "long"),
    "tail": ("short", "long", "bushy", "curly", "dragon", "fish", "flat", "none"),
    "pattern": ("none", "stripes", "spots", "scales"),
    "eyes": ("normal", "big", "glowing"),
    "pose": ("", "normal", "zombie", "hunched", "proud", "float", "hands_on_hips"),
    "effect": ("", "none", "ghostly", "glowing", "shadowy"),
}
COLOR_KEYS = ("skin", "hair", "top", "bottom", "shoes", "fur", "belly", "mane", "patternColor", "eyeColor", "glowColor",
              "hatColor", "accColor", "body", "accent")
CSS = {"navy": "#1f2a44", "maroon": "#7a1f2a", "olive": "#6b7a2a", "khaki": "#c8a96a", "saffron": "#ff8a1f",
       "violet": "#8e5bd8", "lavender": "#b9a4e8", "cyan": "#1fc8d8", "magenta": "#d81f8e", "lime": "#8bd83a",
       "turquoise": "#1fa2a0", "tan": "#d2b48c", "peach": "#ffcfa8", "crimson": "#c0182a", "sky blue": "#7ac8ff",
       "dark green": "#2f6a2a", "light blue": "#9fd3ff", "dark blue": "#1d3f8a", "pale": "#f4efe6", "rust": "#b7410e"}


def color_of(v) -> str | None:
    """'#aabbcc', 'red', 'लाल', 'navy' → '#rrggbb' (or None)."""
    v = str(v or "").strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", v):
        return v
    if re.fullmatch(r"#[0-9a-f]{3}", v):
        return "#" + "".join(ch * 2 for ch in v[1:])
    return COLORS.get(v) or CSS.get(v)


def _part_names() -> set:
    """The part and held-item names the runtime knows (read from web/studio3d/parts.js and story.js)."""
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent.parent / "web" / "studio3d"
    try:
        js = (root / "parts.js").read_text(encoding="utf-8")
        story = (root / "story.js").read_text(encoding="utf-8")
    except OSError:
        return set()
    names = set()
    for block in ("const HEAD = {", "const BODY = {", "const HOLD = {"):
        i = js.find(block)
        j = js.find("\n};", i)
        names |= set(re.findall(r"^\s{2}([a-z_]+)\s*[:(]", js[i:j], re.M))
    i = story.find("export const PROPS = {")
    j = story.find("\n};", i)
    names |= {"prop:" + n for n in re.findall(r"^\s{2}([a-z_]+)\s*\(", story[i:j], re.M)}
    return names | {"leg_pads", "boots", "gloves"}


_KNOWN: set | None = None


def known_names() -> set:
    global _KNOWN
    if _KNOWN is None:
        _KNOWN = _part_names()
    return _KNOWN


def clean_toon(t: dict) -> dict:
    """Keep only what the runtime can build: known bodies, parts, held things, poses and effects; real colours."""
    out: dict = {}
    body = str(t.get("body") or t.get("type") or "").lower()
    if body in BODIES:
        out["type"] = "critter" if body == "blob" else body
    elif body in ("critter",):
        out["type"] = "critter"
    for k, allowed in ENUMS.items():
        if k in t and str(t[k]).lower() in allowed:
            out[k] = str(t[k]).lower()
    for k in COLOR_KEYS:
        c = color_of(t.get(k))
        if c:
            out[k] = c
    for k in ("glasses", "dress", "arms", "legs", "bigEyes", "band"):
        if isinstance(t.get(k), bool):
            out[k] = t[k]
    try:
        h = float(t.get("height") or t.get("scale") or 0)
        if 0.4 <= h <= 1.6:
            out["scale"] = round(h, 2)
    except (TypeError, ValueError):
        pass
    if out.get("eyes") == "big":
        out["bigEyes"] = True
    known = known_names()
    parts = []
    for p in t.get("parts") or []:
        name = str(p.get("part") if isinstance(p, dict) else p).strip().lower()
        if name in known and not name.startswith("prop:"):
            q = {"part": name}
            if isinstance(p, dict):
                for ck in ("color", "color2"):
                    c = color_of(p.get(ck))
                    if c:
                        q[ck] = c
            parts.append(q)
    if parts:
        out["parts"] = parts[:8]
    hold = str(t.get("hold") or "").strip().lower()
    if hold and (hold in known or f"prop:{hold}" in known):
        out["hold"] = hold
    return out


def catalog() -> dict:
    """What a design may use, for the AI designer's instructions: head/body parts and things to hold."""
    from pathlib import Path
    js = (Path(__file__).resolve().parent.parent.parent / "web" / "studio3d" / "parts.js").read_text(encoding="utf-8")
    i = js.find("const HOLD = {")
    hold = set(re.findall(r"^\s{2}([a-z_]+)\s*[:(]", js[i:js.find("\n};", i)], re.M))
    names = known_names()
    props = {n[5:] for n in names if n.startswith("prop:")}
    parts = sorted(n for n in names if not n.startswith("prop:") and n not in hold)
    return {"parts": parts, "hold": sorted(hold | props)}
