"""Video Format registry: every kind of video the AI Studio can make.

A *format* is the complete production recipe for one kind of video (3D kids cartoon, horror story, anime, history
documentary, ...). It tells every stage of the pipeline what to do:

    story     -> storyteller.py  (tone, structure beats, the 3 pitch angles, narrated vs dialogue)
    visual    -> providers.py    (style DNA added to every image prompt, negative prompt)
    motion    -> production.py   (camera moves, seconds per shot, transitions)
    grade     -> production.py   (FFmpeg colour grade: contrast, saturation, grain, vignette)
    voice     -> tts.py          (narrator per language, speaking rate and pitch)
    sound     -> soundtrack.py   (music mood, ambience bed, ducking)
    captions  -> render.py       (caption template and position)

A series stores `format` (an id from FORMATS) plus optional overrides (`visual_style`, `aspect_ratio`, ...).
`resolve(series)` merges the two, so old series without a format keep working (they resolve to "kids_3d").
Adding a new kind of video is one entry in FORMATS: no other file has to change.
"""
from __future__ import annotations

import copy

DEFAULT_FORMAT = "kids_3d"

# Narrator voices per language. Keys are edge-tts voice ids (see tts.VOICE_CATALOG).
_NARR_WARM = {"en": "en-US-ChristopherNeural", "hi": "hi-IN-MadhurNeural", "es": "es-ES-AlvaroNeural",
              "fr": "fr-FR-HenriNeural", "de": "de-DE-ConradNeural", "ja": "ja-JP-KeitaNeural"}
_NARR_DEEP = {"en": "en-US-GuyNeural", "hi": "hi-IN-MadhurNeural", "es": "es-ES-AlvaroNeural",
              "fr": "fr-FR-HenriNeural", "de": "de-DE-ConradNeural", "ja": "ja-JP-KeitaNeural"}
_NARR_SOFT = {"en": "en-GB-SoniaNeural", "hi": "hi-IN-SwaraNeural", "es": "es-ES-ElviraNeural",
              "fr": "fr-FR-DeniseNeural", "de": "de-DE-KatjaNeural", "ja": "ja-JP-NanamiNeural"}
_NARR_BRIGHT = {"en": "en-US-JennyNeural", "hi": "hi-IN-SwaraNeural", "es": "es-MX-DaliaNeural",
                "fr": "fr-FR-DeniseNeural", "de": "de-DE-KatjaNeural", "ja": "ja-JP-NanamiNeural"}

# Reusable colour grades (FFmpeg -vf chains, applied after the shots are joined)
_G_NONE = ""
_G_VIBRANT = "eq=saturation=1.18:contrast=1.04"
_G_ANIME = "eq=saturation=1.25:contrast=1.06:gamma=1.02,unsharp=5:5:0.6"
_G_HORROR = ("eq=contrast=1.18:saturation=0.45:brightness=-0.05:gamma=0.92,"
             "colorbalance=rs=-0.06:gs=-0.02:bs=0.07:rm=-0.04:bm=0.05,vignette=angle=PI/3.6,noise=alls=14:allf=t+u")
_G_DOC = "eq=contrast=1.06:saturation=0.85,curves=preset=medium_contrast,vignette=angle=PI/5"
_G_VINTAGE = "curves=preset=vintage,eq=saturation=0.8,vignette=angle=PI/4,noise=alls=8:allf=t+u"
_G_NOIR = "hue=s=0,eq=contrast=1.35:brightness=-0.03,vignette=angle=PI/3.5,noise=alls=12:allf=t+u"
_G_SCIFI = "eq=contrast=1.1:saturation=1.1,colorbalance=bs=0.08:rs=-0.03:bh=0.05:rh=0.04"
_G_WARM = "eq=saturation=1.05:gamma=1.03,colorbalance=rm=0.05:bm=-0.04"
_G_DREAM = "eq=saturation=0.95:brightness=0.02:gamma=1.04,gblur=sigma=0.6,vignette=angle=PI/5"
_G_CINE = "eq=contrast=1.08:saturation=0.92,colorbalance=rs=0.03:bs=-0.03:rh=-0.02:bh=0.04,vignette=angle=PI/5"

_MOVES_GENTLE = ["dolly_in", "pan_right", "dolly_out", "pan_left", "tilt_up"]
_MOVES_DYNAMIC = ["dolly_in", "pan_left", "zoom_punch", "pan_right", "dolly_out", "tilt_down"]
_MOVES_HORROR = ["creep_in", "drift_left", "creep_in", "shake", "drift_right", "creep_out"]
_MOVES_DOC = ["dolly_in", "pan_right", "pan_left", "dolly_out", "tilt_down"]


def _f(id, name, emoji, category, dimension, description, *, style, negative="", grade=_G_NONE,
       moves=_MOVES_GENTLE, shot_sec=5.0, transition="fade", narrator=_NARR_WARM, rate="+0%", pitch="+0Hz",
       music="calm", ambience="", music_db=-12, caption="b-hormozi", caption_pos=0.89, narration="mixed",
       tone="", structure=None, pitch_types=None, audience="general", aspect="16:9", scene_sec=40,
       examples=""):
    return {
        "id": id, "name": name, "emoji": emoji, "category": category, "dimension": dimension,
        "description": description, "audience": audience, "aspect_ratio": aspect, "examples": examples,
        "visual": {"style": style, "negative": negative or "text, watermark, logo, signature, blurry, deformed, extra limbs"},
        "motion": {"moves": list(moves), "shot_sec": shot_sec, "transition": transition},
        "grade": grade,
        "voice": {"narrator": dict(narrator), "rate": rate, "pitch": pitch},
        "sound": {"music": music, "ambience": ambience, "music_db": music_db},
        "captions": {"template": caption, "position": caption_pos},
        "story": {
            "narration": narration,  # narrated | dialogue | mixed
            "tone": tone,
            "structure": structure or ["Hook", "Setup", "Rising tension", "Climax", "Resolution", "Tease the next one"],
            "pitch_types": pitch_types or ["adventure", "mystery", "new_character"],
            "scene_sec": scene_sec,
        },
    }


FORMATS: dict[str, dict] = {f["id"]: f for f in [
    # ------------------------------------------------------------------ kids & family animation
    _f("chhota_bheem", "Chhota Bheem (Dholakpur 2D/3D Cartoon)", "🥋", "Kids & Family", "2d",
       "Vibrant Indian 2D/3D cartoon adventures in Dholakpur with Chhota Bheem, Chutki, Raju, Jaggu, and Kalia. High-energy comedy, teamwork, and heroic fun.",
       style="vibrant 2D/3D Indian cartoon animation style, Chhota Bheem aesthetic, bold clean outlines, cel shading, colorful Dholakpur village, bright primary colors, TV animation film still",
       negative="photorealistic, real human photo, gloomy, dark, text, watermark, blurry",
       grade=_G_VIBRANT, moves=_MOVES_DYNAMIC, shot_sec=4.0, music="playful",
       narrator=_NARR_WARM, rate="+6%", pitch="+0Hz", caption="b-bounce", narration="dialogue",
       tone="Heroic, hilarious, high-energy Indian cartoon banter, delicious laddoos, fast-paced friendship adventures.",
       structure=["Dholakpur festival/laddoo hook", "Trouble or rival challenge appears", "Bheem and friends assemble", "Clever plan & action feat", "Triumphant laddoo feast", "Laughs and next adventure teaser"],
       pitch_types=["dholakpur_adventure", "laddoo_mystery", "village_heroics"], scene_sec=35,
       examples="laddoo thief, village fair, jungle rescue, friendly wrestling match"),
    _f("kids_3d", "3D Kids Cartoon", "🧸", "Kids & Family", "3d",
       "Bright, glossy 3D cartoon episodes for kids, with a recurring cast (RooRoo / Cocomelon style energy).",
       style="high-gloss 3D Pixar toy CGI, cute chibi proportions, octane render, soft volumetric lighting, vibrant primary colors, 8k",
       grade=_G_VIBRANT, music="playful", caption="b-bounce", narration="mixed", audience="kids 3-8",
       tone="Warm, funny, gentle stakes, simple words, one small lesson per episode, lots of character reactions.",
       structure=["Fun hook", "Problem appears", "Try and fail (comedy)", "Teamwork idea", "Success", "Lesson + cute tease"],
       pitch_types=["adventure", "mystery", "new_character"], scene_sec=35,
       examples="farm animals, rescue trucks, space critters, dinosaurs"),
    _f("pixar_family", "3D Family Film", "🎬", "Kids & Family", "3d",
       "Cinematic 3D animated short-film storytelling for all ages, emotional and polished.",
       style="cinematic 3D animated feature film still, Pixar Disney quality, expressive characters, subsurface scattering, "
             "golden hour volumetric light, shallow depth of field, 8k",
       grade=_G_CINE, music="wonder", caption="b-clean", narration="mixed",
       tone="Heartfelt, emotional, humour with heart, a clear character want and a change by the end.",
       structure=["Ordinary world", "Inciting incident", "The journey", "Lowest point", "Brave choice", "Heartfelt ending"],
       pitch_types=["heartwarming", "adventure", "new_character"], scene_sec=45),
    _f("cartoon_2d", "2D Cartoon", "✏️", "Kids & Family", "2d",
       "Flat, bold 2D cartoon look with thick outlines, like classic TV cartoons.",
       style="flat 2D cartoon illustration, bold black outlines, cel shading, vibrant flat colors, clean vector art, "
             "TV animation style background",
       negative="photorealistic, 3d render, text, watermark, blurry",
       grade=_G_VIBRANT, moves=_MOVES_DYNAMIC, shot_sec=4.0, music="playful", caption="b-word",
       tone="Snappy, slapstick, exaggerated reactions, short punchy lines.",
       pitch_types=["comedy", "adventure", "new_character"], scene_sec=30),
    _f("bedtime", "Bedtime Story", "🌙", "Kids & Family", "2d",
       "Soothing watercolor storybook tales, slow narration, calm music. Good for long sleep videos.",
       style="soft watercolor children's storybook illustration, gentle pastel colors, dreamy, warm lamplight, "
             "hand-painted texture, cozy",
       negative="harsh lighting, scary, photorealistic, text, watermark",
       grade=_G_DREAM, moves=["dolly_in", "pan_right", "dolly_in", "pan_left"], shot_sec=8.0, transition="fadeblack",
       narrator=_NARR_SOFT, rate="-12%", pitch="-2Hz", music="lullaby", ambience="night", music_db=-10,
       caption="b-minimal", narration="narrated", audience="kids 2-8",
       tone="Calm, slow, kind, repetitive soothing phrases, no conflict that would scare a child, ends with sleep.",
       structure=["Gentle opening", "A small wish", "A quiet journey", "A kind discovery", "Coming home", "Goodnight"],
       pitch_types=["gentle_journey", "friendship", "nature_wonder"], scene_sec=60),

    # ------------------------------------------------------------------ anime & stylised
    _f("anime", "Anime", "⚔️", "Anime & Stylised", "anime",
       "Japanese anime look: dramatic lighting, emotional close-ups, action beats.",
       style="high quality anime key visual, detailed cel shading, dramatic lighting, Makoto Shinkai sky, "
             "studio anime film still, sharp lineart",
       negative="3d render, photorealistic, western cartoon, text, watermark, blurry",
       grade=_G_ANIME, moves=_MOVES_DYNAMIC, shot_sec=3.5, music="epic", caption="b-mrbeast", narration="dialogue",
       tone="Intense emotions, inner monologue, rivalries, power-ups, dramatic pauses and declarations.",
       structure=["Cold open action", "Character motivation", "Rival / threat", "Training or struggle",
                  "Climactic clash", "Cliffhanger"],
       pitch_types=["battle", "rivalry", "mystery"], scene_sec=35),
    _f("pixel", "Retro Pixel Art", "👾", "Anime & Stylised", "2d",
       "16-bit pixel-art game style stories, great for gaming lore.",
       style="16-bit pixel art scene, retro video game style, limited palette, crisp pixels, parallax background",
       negative="photorealistic, blurry, smooth gradients, text, watermark",
       grade="eq=saturation=1.2", moves=["pan_right", "pan_left", "static"], shot_sec=4.0, transition="cut",
       music="chiptune", caption="b-rapid", narration="mixed",
       tone="Playful gamer humour, quests, bosses, levels, items.",
       pitch_types=["quest", "boss_fight", "secret_level"], scene_sec=30),
    _f("claymation", "Clay / Stop-Motion", "🧱", "Anime & Stylised", "3d",
       "Handmade claymation look, charming and tactile.",
       style="claymation stop-motion scene, plasticine characters with fingerprints texture, handmade miniature set, "
             "soft studio lighting, Aardman style",
       grade=_G_WARM, moves=["static", "dolly_in", "pan_right"], shot_sec=4.5, music="quirky", caption="b-fill",
       tone="Quirky, British-dry humour, small-scale big drama.",
       pitch_types=["comedy", "adventure", "invention"], scene_sec=35),

    # ------------------------------------------------------------------ horror & thriller
    _f("horror", "Horror Story", "👻", "Horror & Thriller", "photoreal",
       "Cinematic horror: dark, desaturated, slow creeping camera, drones and dread. Narrated with character lines.",
       style="cinematic horror film still, dark moody low-key lighting, deep shadows, fog, desaturated cold tones, "
             "35mm film grain, unsettling atmosphere, photorealistic",
       negative="bright, cheerful, cartoon, cute, text, watermark, gore",
       grade=_G_HORROR, moves=_MOVES_HORROR, shot_sec=5.5, transition="fadeblack", narrator=_NARR_DEEP,
       rate="-8%", pitch="-4Hz", music="horror", ambience="wind", music_db=-9, caption="b-minimal",
       caption_pos=0.86, narration="mixed", audience="teens & adults",
       tone="Slow-burn dread, sensory detail (sounds, cold, smells), short sentences at scary moments, "
            "never explain the monster fully, a final twist. No gore.",
       structure=["Unsettling hook", "Normal life with a wrong detail", "Strange events escalate",
                  "Investigation", "The terrifying reveal", "Twist ending"],
       pitch_types=["haunting", "creature", "psychological"], scene_sec=45),
    _f("scary_narration", "Scary Story Narration", "🕯️", "Horror & Thriller", "photoreal",
       "Faceless 'true scary stories' channel: one narrator, first-person, dark imagery.",
       style="dark atmospheric photograph, night, lonely location, eerie light source, mist, found-footage feel, "
             "photorealistic, film grain",
       negative="people smiling, cartoon, bright colors, text, watermark, gore",
       grade=_G_HORROR, moves=_MOVES_HORROR, shot_sec=6.5, transition="fadeblack", narrator=_NARR_DEEP,
       rate="-6%", pitch="-3Hz", music="horror", ambience="rain", music_db=-11, caption="b-minimal",
       narration="narrated", audience="teens & adults",
       tone="First person ('I'), confessional, realistic details (dates, places), builds slowly, ends unresolved.",
       structure=["'This happened to me...' hook", "Background", "First strange sign", "It gets worse",
                  "The night it happened", "What I still can't explain"],
       pitch_types=["true_story", "urban_legend", "rules_horror"], scene_sec=60),
    _f("thriller", "Mystery Thriller", "🕵️", "Horror & Thriller", "photoreal",
       "Detective / mystery thriller with clues, suspects and a reveal.",
       style="neo-noir cinematic thriller still, rain-soaked city at night, neon reflections, dramatic rim light, "
             "anamorphic lens, photorealistic",
       grade=_G_CINE + ",eq=saturation=0.85", moves=_MOVES_DOC, shot_sec=5.0, narrator=_NARR_DEEP, music="tension",
       ambience="rain", caption="b-clean", narration="mixed",
       tone="Clues planted fairly, red herrings, sharp dialogue, a satisfying reveal.",
       pitch_types=["whodunit", "chase", "conspiracy"], scene_sec=40),
    _f("noir", "Noir (Black & White)", "🎩", "Horror & Thriller", "photoreal",
       "1940s black-and-white film noir with hard-boiled narration.",
       style="1940s film noir still, black and white, venetian blind shadows, fedora, cigarette smoke, high contrast",
       grade=_G_NOIR, moves=_MOVES_DOC, shot_sec=5.5, transition="fadeblack", narrator=_NARR_DEEP, rate="-4%",
       music="jazz_noir", ambience="rain", caption="b-minimal", narration="narrated",
       tone="Hard-boiled first-person narration, similes, cynical detective, femme fatale, double-cross.",
       pitch_types=["case", "betrayal", "heist"], scene_sec=45),

    # ------------------------------------------------------------------ documentary & education
    _f("history_doc", "History Documentary", "🏛️", "Documentary & Education", "photoreal",
       "Documentary narration over cinematic historical recreations.",
       style="cinematic historical recreation, epic wide shot, period-accurate costumes and architecture, "
             "dramatic natural light, photorealistic, documentary still",
       grade=_G_DOC, moves=_MOVES_DOC, shot_sec=6.0, narrator=_NARR_DEEP, rate="-2%", music="epic", music_db=-14,
       caption="b-clean", narration="narrated", audience="general",
       tone="Authoritative, factual, vivid scene-setting, surprising facts, no invented dates or numbers.",
       structure=["Shocking fact hook", "Context", "Key figures", "Turning point", "Consequences", "Legacy today"],
       pitch_types=["empire", "battle", "mystery_of_history"], scene_sec=50),
    _f("true_crime", "True Crime", "🔎", "Documentary & Education", "photoreal",
       "Investigative true-crime documentary style (keep it respectful, fictional names by default).",
       style="investigative documentary still, evidence board, police tape, moody interior, overcast light, "
             "photorealistic, 35mm",
       grade=_G_DOC + ",eq=saturation=0.7", moves=_MOVES_DOC, shot_sec=6.0, narrator=_NARR_DEEP, music="tension",
       caption="b-clean", narration="narrated", audience="adults",
       tone="Measured, investigative, timeline-driven, respectful to victims, no graphic violence.",
       structure=["The night everything changed", "Who they were", "The investigation", "The break",
                  "The truth", "Questions that remain"],
       pitch_types=["cold_case", "disappearance", "con_artist"], scene_sec=55),
    _f("explainer", "Facts & Explainer", "💡", "Documentary & Education", "3d",
       "Fast, visual explainers and top-10 facts videos.",
       style="clean 3D isometric illustration, soft studio lighting, bright infographic style, minimal background, "
             "high detail",
       grade=_G_VIBRANT, moves=_MOVES_DYNAMIC, shot_sec=3.5, transition="cut", narrator=_NARR_BRIGHT, rate="+6%",
       music="upbeat", music_db=-14, caption="b-hormozi", narration="narrated",
       tone="Curious, energetic, one idea per scene, analogies, 'but here is the crazy part' turns.",
       structure=["Big question hook", "Simple explanation", "Surprising detail", "Real example", "Mind-blown fact",
                  "Recap + question to comments"],
       pitch_types=["how_it_works", "top_facts", "what_if"], scene_sec=30),
    _f("mythology", "Mythology Epic", "🔱", "Documentary & Education", "3d",
       "Epic retellings of myths (Indian, Greek, Norse...) with godrays and grand scale.",
       style="epic mythological 3D cinematic art, divine golden godrays, grand temples, celestial glow, "
             "ornate costumes, dramatic scale, 8k",
       grade=_G_WARM + ",vignette=angle=PI/5", moves=_MOVES_GENTLE, shot_sec=5.5, narrator=_NARR_DEEP, rate="-4%",
       music="epic", caption="b-clean", narration="mixed",
       tone="Grand, reverent, moral at the heart, vivid divine imagery, faithful to the source tradition.",
       pitch_types=["legend", "battle_of_gods", "moral_tale"], scene_sec=45),

    # ------------------------------------------------------------------ cinematic fiction
    _f("scifi", "Sci-Fi Cinematic", "🚀", "Cinematic Fiction", "photoreal",
       "Cinematic science fiction: spaceships, cyberpunk cities, AI and alien worlds.",
       style="cinematic sci-fi film still, futuristic, volumetric neon haze, massive scale, octane render, "
             "anamorphic lens flare, photorealistic, 8k",
       grade=_G_SCIFI, moves=_MOVES_DYNAMIC, shot_sec=5.0, narrator=_NARR_DEEP, music="synth", ambience="hum",
       caption="b-clean", narration="mixed",
       tone="Big ideas, wonder and danger, crisp dialogue, a twist about technology or humanity.",
       pitch_types=["first_contact", "rogue_ai", "space_survival"], scene_sec=40),
    _f("fantasy", "Fantasy Epic", "🐉", "Cinematic Fiction", "3d",
       "Dragons, kingdoms, magic and quests.",
       style="epic fantasy concept art, cinematic, magical glowing particles, ancient castles, dramatic skies, "
             "highly detailed, 8k",
       grade=_G_WARM, moves=_MOVES_GENTLE, shot_sec=5.0, music="epic", caption="b-clean", narration="mixed",
       tone="Wonder, prophecy, loyalty, a clear quest and a cost to magic.",
       pitch_types=["quest", "prophecy", "new_ally"], scene_sec=45),
    _f("sports_drama", "Sports Drama", "🏏", "Cinematic Fiction", "3d",
       "Matches, rivalries and comebacks told as an animated drama: the stadium, the tension, the last ball.",
       style="animated 3D sports drama, packed stadium, floodlights, players in team kits, dramatic match moments, "
             "vivid colours, cinematic",
       grade=_G_VIBRANT, moves=_MOVES_DYNAMIC, shot_sec=4.0, music="epic", music_db=-10, caption="b-mrbeast",
       narration="mixed", audience="sports fans, teens & adults",
       tone="Pressure, momentum swings, team spirit, a hero moment, the crowd's roar; real tension, clear stakes.",
       structure=["The stakes", "Early setback", "Fightback", "Turning point", "The final push", "Victory or heartbreak"],
       pitch_types=["comeback", "rivalry", "underdog"], scene_sec=40,
       examples="a last-day Test win, a final-over chase, an underdog team's first trophy"),
    _f("photoreal_drama", "Cinematic Drama", "🎭", "Cinematic Fiction", "photoreal",
       "Live-action style drama with realistic people.",
       style="cinematic live-action film still, photorealistic people, natural golden hour lighting, 35mm lens bokeh, "
             "emotional expression, 8k",
       grade=_G_CINE, moves=_MOVES_GENTLE, shot_sec=5.0, music="emotional", caption="b-clean", narration="dialogue",
       tone="Grounded, emotional subtext, real conflict between people, a meaningful choice.",
       pitch_types=["family_drama", "romance", "betrayal"], scene_sec=45),
    _f("comedy", "Comedy Sketch", "😂", "Cinematic Fiction", "2d",
       "Short comedy sketches with fast cuts and punchlines.",
       style="bright colorful cartoon illustration, exaggerated expressions, comic style, clean background",
       grade=_G_VIBRANT, moves=["zoom_punch", "static", "pan_left", "zoom_punch"], shot_sec=3.0, transition="cut",
       narrator=_NARR_BRIGHT, rate="+8%", music="quirky", caption="b-word", narration="dialogue",
       tone="Setup-punchline rhythm, escalation, callbacks, one absurd twist.",
       pitch_types=["relatable", "absurd", "parody"], scene_sec=25),

    # ------------------------------------------------------------------ faceless channels
    _f("motivational", "Motivational / Stoic", "🔥", "Faceless Channels", "photoreal",
       "Deep-voice motivational and stoic wisdom videos over cinematic imagery.",
       style="cinematic dramatic photograph, lone figure, mountain summit or storm, epic sky, high contrast, "
             "moody, photorealistic",
       grade=_G_CINE + ",eq=saturation=0.8", moves=["dolly_in", "dolly_in", "pan_right", "creep_in"], shot_sec=5.0,
       narrator=_NARR_DEEP, rate="-5%", pitch="-3Hz", music="emotional", music_db=-10, caption="b-mrbeast",
       narration="narrated", audience="adults",
       tone="Direct 'you' address, short powerful sentences, a story or quote, a call to action.",
       structure=["Hard truth hook", "The struggle", "Story or quote", "The lesson", "What to do today", "Final line"],
       pitch_types=["discipline", "stoic_lesson", "comeback_story"], scene_sec=35, aspect="9:16"),
]}


# One-click looks for the New Series dialog, per family of formats. The format's own look always comes first.
LOOKS = {
    "Kids & Family": [
        ("🧸", "Glossy toy 3D", "high-gloss 3D toy CGI, cute rounded proportions, soft lighting, vibrant primary colors"),
        ("🌈", "Pastel storybook", "soft pastel 3D storybook animation, gentle lighting, rounded shapes, cosy colors"),
        ("🌞", "Sunny village", "bright sunny 3D cartoon village, warm colors, clean shapes, cheerful lighting"),
        ("🌙", "Bedtime glow", "dreamy night-time 3D cartoon, warm lantern glow, stars, soft blues"),
    ],
    "Anime & Stylised": [
        ("⚔️", "Anime action", "3D anime style, bold colors, dynamic lighting, expressive characters"),
        ("🌸", "Soft slice-of-life", "soft anime style, pastel sky, gentle sunlight, calm everyday scenes"),
        ("👾", "Retro pixel", "retro pixel-art look, limited bright palette, chunky shapes"),
        ("🧱", "Clay stop-motion", "clay stop-motion look, handmade textures, warm studio lighting"),
    ],
    "Horror & Thriller": [
        ("👻", "Haunted night", "dark haunted night, cold blue moonlight, fog, deep shadows, desaturated"),
        ("🕯️", "Candle-lit dread", "candle-lit interiors, warm flicker against black shadows, dust, unsettling quiet"),
        ("🌲", "Folk horror forest", "misty old forest at dusk, twisted trees, muted greens and greys, eerie silence"),
        ("📼", "Found footage", "grainy found-footage look, harsh torch light, dark corners, handheld feel"),
    ],
    "Documentary & Education": [
        ("🏛️", "Epic history", "epic historical scenes, golden hour light, ancient architecture, cinematic"),
        ("💡", "Clean explainer", "clean bright 3D explainer look, simple shapes, clear colors, studio light"),
        ("🔱", "Mythic glow", "mythic 3D scenes, golden godrays, glowing temples, rich saffron and blue"),
        ("🔎", "Dark case file", "dark investigative look, cold desk light, maps and files, muted tones"),
    ],
    "Cinematic Fiction": [
        ("🎬", "Cinematic drama", "cinematic 3D drama, natural golden hour light, warm tones, shallow focus"),
        ("🚀", "Sci-fi neon", "sci-fi 3D world, neon lights, metal corridors, cool blue haze"),
        ("🐉", "Fantasy epic", "fantasy 3D world, castles and mountains, magical glow, rich colors"),
        ("😂", "Bright comedy", "bright punchy 3D comedy look, saturated colors, clean sets"),
    ],
    "Faceless Channels": [
        ("🔥", "Epic motivation", "epic dramatic skies, lone figure, high contrast, moody light"),
        ("🌅", "Calm wisdom", "calm sunrise landscapes, soft warm light, quiet and spacious"),
        ("🏙️", "City grind", "night city streets, neon reflections, rain, focused mood"),
    ],
}


def looks_for(fmt: dict) -> list[dict]:
    """The format's own look, then the other looks of its family."""
    own = {"emoji": fmt["emoji"], "label": fmt["name"], "style": fmt["visual"]["style"]}
    rest = [{"emoji": e, "label": l, "style": st} for e, l, st in LOOKS.get(fmt["category"], [])]
    return [own] + rest


def list_formats() -> list[dict]:
    """Compact list for the UI picker."""
    return [{
        "id": f["id"], "name": f["name"], "emoji": f["emoji"], "category": f["category"],
        "dimension": f["dimension"], "description": f["description"], "audience": f["audience"],
        "aspect_ratio": f["aspect_ratio"], "visual_style": f["visual"]["style"],
        "narration": f["story"]["narration"], "music": f["sound"]["music"], "examples": f.get("examples", ""),
        "looks": looks_for(f),
    } for f in FORMATS.values()]


def get(format_id: str | None) -> dict:
    return copy.deepcopy(FORMATS.get(format_id or "", FORMATS[DEFAULT_FORMAT]))


def guess(genre: str = "", visual_style: str = "") -> str:
    """Pick a format for an old series that has none, from its free-text genre and style."""
    text = f"{genre} {visual_style}".lower()
    rules = [("horror", "horror"), ("scary", "scary_narration"), ("creepy", "scary_narration"),
             ("noir", "noir"), ("thriller", "thriller"), ("detective", "thriller"), ("anime", "anime"),
             ("pixel", "pixel"), ("clay", "claymation"), ("bedtime", "bedtime"), ("lullab", "bedtime"),
             ("watercolor", "bedtime"), ("history", "history_doc"), ("crime", "true_crime"),
             ("myth", "mythology"), ("sci-fi", "scifi"), ("cyberpunk", "scifi"), ("space", "scifi"),
             ("fantasy", "fantasy"), ("dragon", "fantasy"), ("motivat", "motivational"), ("stoic", "motivational"),
             ("fact", "explainer"), ("explain", "explainer"), ("comedy", "comedy"), ("2d", "cartoon_2d"),
             ("drama", "photoreal_drama"), ("photoreal", "photoreal_drama"), ("pixar", "kids_3d"),
             ("cartoon", "kids_3d")]
    for word, fid in rules:
        if word in text:
            return fid
    return DEFAULT_FORMAT


def resolve(series: dict | None) -> dict:
    """The effective recipe for a series: its format with the series' own overrides on top."""
    series = series or {}
    fid = series.get("format") or guess(series.get("genre", ""), series.get("visual_style", ""))
    fmt = get(fid)
    if series.get("visual_style"):
        fmt["visual"]["style"] = series["visual_style"]
    if series.get("aspect_ratio") in ("16:9", "9:16"):
        fmt["aspect_ratio"] = series["aspect_ratio"]
    ov = series.get("format_overrides") or {}
    for section in ("visual", "motion", "voice", "sound", "captions", "story"):
        if isinstance(ov.get(section), dict):
            fmt[section].update(ov[section])
    if isinstance(ov.get("grade"), str):
        fmt["grade"] = ov["grade"]
    return fmt


def narrator_voice(fmt: dict, lang: str = "en") -> str:
    voices = fmt["voice"]["narrator"]
    return voices.get((lang or "en").lower()) or voices.get("en") or "en-US-ChristopherNeural"


def story_brief(fmt: dict) -> str:
    """The format's rules as text for the storyteller prompts."""
    st = fmt["story"]
    mode = {"narrated": "Mostly a single NARRATOR voice telling the story; characters speak only short quoted lines.",
            "dialogue": "Mostly CHARACTER DIALOGUE between the cast; the narrator only bridges scenes briefly.",
            "mixed": "A mix of NARRATOR lines and CHARACTER DIALOGUE in every scene."}.get(st["narration"], "")
    return (f"VIDEO FORMAT: {fmt['emoji']} {fmt['name']} ({fmt['dimension'].upper()}) for {fmt['audience']}.\n"
            f"TONE & RULES: {st['tone']}\n"
            f"VOICE MODE: {mode}\n"
            f"STORY STRUCTURE (spread across the scenes in order): {' -> '.join(st['structure'])}\n"
            f"VISUAL STYLE DNA: {fmt['visual']['style']}"
            + ("\nANIMATION: every scene is ACTED by animated 3D cartoon characters, so write for performance: give "
               "EVERY line an 'emotion' (happy, excited, surprised, sad, angry, scared, whisper, mysterious, calm); "
               "greetings make characters wave, excitement makes them bounce, a happy last line makes everyone jump. "
               "Name the place in 'setting' with plain words: forest, autumn forest, village, market, farm, beach, "
               "snow, home/room, school, space; add 'night' or 'evening' when it is dark. Keep each scene to the "
               "2-4 characters who are actually there."
               if fmt.get("render", "anim3d") == "anim3d" else ""))
