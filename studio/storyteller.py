"""AI Storyteller & Episodic Director for PeakCut/Clipper.
Analyzes previous episodes, pitches smart continuation concepts,
and writes full multi-character scripts with 3D visual generation prompts.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from studio import ai, config, formats, memory, tts, usage

log = logging.getLogger("peakcut.storyteller")

# words spoken per second by the voices, pauses between lines included (measured: Hindi scenes 2.09 words/s)
WORDS_PER_SEC = {"hi": 2.1, "en": 2.5, "es": 2.4, "fr": 2.4, "de": 2.2, "ja": 3.0}


def words_for(seconds: float, lang: str) -> int:
    """How many spoken words fill this many seconds in this language."""
    return int(round(float(seconds) * WORDS_PER_SEC.get((lang or "en").lower(), 2.3)))


def spoken_words(scene: dict) -> int:
    """The words a scene's voices will say (its lines, else its 'Speaker: text' dialogue)."""
    lines = [str(x.get("text") or "") for x in scene.get("lines") or []]
    if not any(lines):
        lines = [row.split(":", 1)[-1] for row in str(scene.get("dialogue") or "").splitlines()]
    return sum(len(t.split()) for t in lines)


def _length_rule(seconds: float, lang: str) -> str:
    w = words_for(seconds, lang)
    lines_lo, lines_hi = max(4, int(seconds / 9)), max(7, int(seconds / 5))
    return (f"about {w} words in {lang.upper()} (between {int(w * 0.9)} and {int(w * 1.2)} words): the voices speak about "
            f"{WORDS_PER_SEC.get(lang.lower(), 2.3)} words per second, so fewer words make a SHORTER video. Spread them over "
            f"{lines_lo} to {lines_hi} lines")

PITCH_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING"},
            "type": {"type": "STRING"},  # adventure, mystery, new_character
            "title": {"type": "STRING"},
            "logline": {"type": "STRING"},
            "hook": {"type": "STRING"},
            "featured_characters": {"type": "ARRAY", "items": {"type": "STRING"}},
            "new_character": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "species": {"type": "STRING"},
                    "visual_anchor": {"type": "STRING"},
                    "voice_id": {"type": "STRING"},
                    "personality": {"type": "STRING"}
                }
            }
        },
        "required": ["id", "type", "title", "logline", "hook", "featured_characters"]
    }
}

LINES_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "speaker": {"type": "STRING"},
            "text": {"type": "STRING"},
            "emotion": {"type": "STRING"},
            "sfx": {"type": "ARRAY", "items": {"type": "STRING"}},
            "show": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
                "thing": {"type": "STRING"}, "how": {"type": "STRING"}}}}
        },
        "required": ["speaker", "text"]
    }
}

SHOTS_SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "visual_prompt": {"type": "STRING"},
            "camera_motion": {"type": "STRING"}
        },
        "required": ["visual_prompt"]
    }
}

SCRIPT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "title": {"type": "STRING"},
        "synopsis": {"type": "STRING"},
        "unresolved_hook": {"type": "STRING"},
        "walkthrough": {"type": "OBJECT", "properties": {
            "why_this_episode": {"type": "STRING"}, "bridge_from_last": {"type": "STRING"},
            "journey": {"type": "STRING"}, "next_teaser": {"type": "STRING"}}},
        "new_characters": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "species": {"type": "STRING"},
                    "visual_anchor": {"type": "STRING"},
                    "voice_id": {"type": "STRING"},
                    "personality": {"type": "STRING"}
                },
                "required": ["name", "visual_anchor", "voice_id"]
            }
        },
        "scenes": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "scene_num": {"type": "INTEGER"},
                    "duration_sec": {"type": "NUMBER"},
                    "setting": {"type": "STRING"},
                    "characters": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "speaker": {"type": "STRING"},
                    "dialogue": {"type": "STRING"},
                    "voice_id": {"type": "STRING"},
                    "camera_motion": {"type": "STRING"},
                    "visual_prompt": {"type": "STRING"},
                    "lines": LINES_SCHEMA,
                    "shots": SHOTS_SCHEMA,
                    "teaser": {"type": "BOOLEAN"},
                    "music": {"type": "STRING"},
                    "set": {"type": "OBJECT", "properties": {
                        "place": {"type": "STRING"}, "kit": {"type": "STRING"}, "era": {"type": "STRING"},
                        "culture": {"type": "STRING"}, "time": {"type": "STRING"}, "weather": {"type": "STRING"},
                        "mood": {"type": "STRING"}, "landmarks": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "location_name": {"type": "STRING"}}}
                },
                "required": ["scene_num", "duration_sec", "setting", "speaker", "dialogue", "visual_prompt"]
            }
        },
        "music_mood": {"type": "STRING"}
    },
    "required": ["title", "synopsis", "scenes"]
}

SINGLE_SCENE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "scene_num": {"type": "INTEGER"},
        "duration_sec": {"type": "NUMBER"},
        "setting": {"type": "STRING"},
        "characters": {"type": "ARRAY", "items": {"type": "STRING"}},
        "speaker": {"type": "STRING"},
        "dialogue": {"type": "STRING"},
        "voice_id": {"type": "STRING"},
        "camera_motion": {"type": "STRING"},
        "visual_prompt": {"type": "STRING"}
    },
    "required": ["scene_num", "duration_sec", "setting", "speaker", "dialogue", "visual_prompt"]
}


# ---------------------------------------------------------------- Pitches

def pitch_next_episodes(series_id: str) -> list[dict]:
    """Analyzes prior episode history and returns 3 smart continuation pitches."""
    ctx = memory.get_continuity_context(series_id)
    if not ctx:
        return []

    ep_num = ctx.get("next_episode_num", 1)
    chars = ctx.get("characters", [])
    past = ctx.get("past_episodes", [])
    latest_hook = ctx.get("latest_unresolved_hook", "")
    lang = ctx.get("default_language", "en").lower()
    def_voice = tts.default_voice_for_lang(lang)

    char_desc = "\n".join([f"- {c['name']} ({c.get('species', 'Character')}): {c.get('personality', '')}" for c in chars]) or "None yet."
    past_desc = "\n".join([f"Episode {p['episode_num']}: {p['title']} - Summary: {p['summary']} (Hook: {p.get('unresolved_hook', 'None')})" for p in past]) or "This is the series debut (Episode 1)."

    lang_inst = f"Language: Hindi. Write titles, loglines, and hooks in natural, friendly Hindi (Devanagari script or clean transliteration appropriate for kids/family animation). Assign Hindi voice_ids (e.g. '{def_voice}')." if lang == "hi" else f"Language: {lang.upper()}. Write titles, loglines, and hooks in this language with voice_id '{def_voice}'."

    fmt = formats.resolve(memory.get_series(series_id))
    angles = fmt["story"]["pitch_types"]
    prompt = f"""You are the Lead Story Director for the series "{ctx.get('title')}".
Genre: {ctx.get('genre')}
{_brief_rule(ctx)}{_places_rule(ctx)}{formats.story_brief(fmt)}
{lang_inst}

EXISTING CHARACTERS:
{char_desc}

PREVIOUS EPISODE HISTORY:
{past_desc}

LATEST UNRESOLVED HOOK / CLIFFHANGER:
{latest_hook or "Fresh start for the series."}

TASK:
Propose exactly 3 unique, compelling story concepts for upcoming Episode {ep_num}, one for each angle
(set "type" to the angle name): {", ".join(f'"{a}"' for a in angles)}.
Each must fit the format's tone and audience. Pick up prior hooks where it makes sense. Fill "new_character" only
when a new person or creature joins the cast.

Format output strictly according to the schema.
"""

    models = ai.models() or ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
    for m in models:
        try:
            raw = usage.studio_call(m, prompt, PITCH_SCHEMA, "Studio: episode ideas", ctx.get("title", ""), timeout=30)
            res = raw[0] if isinstance(raw, tuple) else raw
            if isinstance(res, list) and len(res) >= 2:
                # Ensure ids are populated
                for i, p in enumerate(res):
                    if not p.get("id"):
                        p["id"] = f"pitch_{i+1}"
                return res
        except Exception as e:
            log.warning("Storyteller pitch call failed on model %s: %s", m, e)

    # Fallback if AI provider is unreachable
    return [
        {
            "id": "pitch_1",
            "type": "adventure",
            "title": f"The Great Valley Expedition (Episode {ep_num})",
            "logline": "The team sets out on an exciting expedition to explore the lush sunflower valley.",
            "hook": "They spot a sparkling reflection high up on the old windmill.",
            "featured_characters": [c["name"] for c in chars[:2]] or ["Hero"]
        },
        {
            "id": "pitch_2",
            "type": "mystery",
            "title": f"The Mystery of the Whispering Windmill (Episode {ep_num})",
            "logline": "Curious sounds lead the gang to investigate the old mill at sunset.",
            "hook": "Inside the mill gears, they find a golden key wrapped in a mysterious map.",
            "featured_characters": [c["name"] for c in chars[:2]] or ["Hero"]
        },
        {
            "id": "pitch_3",
            "type": "new_character",
            "title": f"A Friendly New Companion (Episode {ep_num})",
            "logline": "A playful baby owl arrives looking for a warm place to rest, bringing secrets from the forest.",
            "hook": "The owl gestures towards a hidden pathway behind the barn.",
            "featured_characters": [c["name"] for c in chars[:2]] or ["Hero"],
            "new_character": {
                "name": "Oliver",
                "species": "Baby Owl",
                "visual_anchor": "cute 3d cartoon baby owl, soft feathery textures, large golden curious eyes, tiny scarf",
                "voice_id": "en-US-JennyNeural",
                "personality": "Gentle, shy, loves books and nighttime stargazing"
            }
        }
    ]


# ---------------------------------------------------------------- Script Generation

def generate_episode_script(
    series_id: str,
    pitch_or_idea: dict | str,
    target_scenes: int = 12,
    scene_duration: int = 60,
    target_duration_min: float | None = None,
    cast: list | None = None,
    newcomer: bool = False
) -> dict:
    """Generates the full scene-by-scene script with dialogues and 3D visual generation prompts for long-form videos.
    cast: the Vault characters this episode must use (each gets real lines); newcomer: introduce one new character."""
    ctx = memory.get_continuity_context(series_id)
    if not ctx:
        return {}

    chars = ctx.get("characters", [])
    lang = ctx.get("default_language", "en").lower()
    def_narrator_voice = tts.default_voice_for_lang(lang)
    char_map = {c["name"].lower(): c for c in chars}
    char_desc = "\n".join([f"- {c['name']} ({c.get('species', '')}; {c.get('personality', '')}) (Voice: {c.get('voice_id', def_narrator_voice)}): Visual: {c.get('visual_anchor', '')}" for c in chars]) or "None yet."
    cast = [str(n).strip() for n in (cast or []) if str(n).strip()]
    cast_rule = ""
    if cast:
        cast_rule = ("\nCAST FOR THIS EPISODE (the user chose them): " + ", ".join(cast) + ".\n"
                     "Every one of them MUST have meaningful spoken lines in at least two scenes and a clear part in the "
                     "story. Other Vault characters may appear only when the story really needs them.\n")
    if newcomer:
        cast_rule += ("NEW CHARACTER: introduce exactly ONE new character who fits this story and the format (not in the "
                      "Vault). Give them lines and a real part, and describe them in 'new_characters' (name, species, "
                      "visual_anchor with colours tied to clothes or fur, personality, voice_id).\n")

    if isinstance(pitch_or_idea, dict):
        pitch_text = f"Title: {pitch_or_idea.get('title')}\nPremise: {pitch_or_idea.get('logline')}\nHook: {pitch_or_idea.get('hook')}"
        if pitch_or_idea.get("new_character"):
            nc = pitch_or_idea["new_character"]
            pitch_text += f"\nIntroduce New Character: {nc.get('name')} ({nc.get('species')}) - {nc.get('visual_anchor')}"
    else:
        pitch_text = f"User Premise: {pitch_or_idea}"

    lang_rule = (
        f"Language Requirement: HINDI. Write the episode title, synopsis, unresolved_hook, and character dialogues in natural, engaging Hindi (Devanagari script), e.g. 'अरे देखो! यहाँ क्या है!'. Default narrator voice_id: '{def_narrator_voice}'."
        if lang == "hi"
        else f"Language Requirement: {lang.upper()}. Write all dialogues, title, and synopsis in this language. Default narrator voice_id: '{def_narrator_voice}'."
    )

    if target_duration_min:
        target_min = int(round(target_duration_min))
        if not target_scenes or target_scenes < 3:
            target_scenes = max(3, min(25, int(round(target_min * 60 / scene_duration))))
    else:
        target_min = max(1, round(target_scenes * scene_duration / 60))
    fmt = formats.resolve(memory.get_series(series_id))
    prompt = f"""You are the Lead Screenwriter & Visual Director for the YouTube series "{ctx.get('title')}".
Genre: {ctx.get('genre')}
{_brief_rule(ctx)}{_places_rule(ctx)}{formats.story_brief(fmt)}
Aspect Ratio: {ctx.get('aspect_ratio', '16:9')}
{lang_rule}

CHARACTER VAULT & VISUAL ANCHORS:
{char_desc}

EPISODE PREMISE:
{pitch_text}
{cast_rule}
TASK:
Write a complete, captivating, long-form YouTube episode script with EXACTLY {target_scenes} scenes (target duration: ~{target_min} minutes total).

MANDATORY RULES FOR LONG-FORM VIDEO & SCENE LENGTH:
1. SCENE DURATION & PACING:
   - Each of the {target_scenes} scenes represents ~{scene_duration} seconds ({max(40, scene_duration - 10)} to {scene_duration + 10} seconds) of rich cinematic storytelling.
   - Set 'duration_sec': {scene_duration}.

2. SUBSTANTIAL SPOKEN DIALOGUE & NARRATION (CRITICAL FOR 1-MINUTE SCENES):
   - The 'dialogue' field is the voiceover track. Spoken aloud, it MUST naturally last ~{scene_duration} seconds!
   - Therefore, 'dialogue' CANNOT be a brief 1-line quip. Each scene MUST feature a substantial, multi-sentence narrative or character exchange ({_length_rule(scene_duration, lang)}).
   - For Narrator scenes: Provide evocative, atmospheric narrative descriptions that set up the environment, describe character thoughts, uncover clues, and build suspense or wonder.
   - For Character scenes: Provide extensive dialogue with expressive emotional reactions, lively conversational back-and-forth, humor, curiosity, and teamwork.
   - If a character is speaking, they can speak multiple sentences explaining their idea, reacting, asking questions, and advancing the scene.

3. Assign the correct 'voice_id' for each speaker based on the character vault (default narrator voice: '{def_narrator_voice}').
3c. 'set' on EVERY scene, describing where it happens so the 3D set fits the story:
    {{"place": "temple courtyard", "kit": one of {_kit_list()} (pick the closest: inside a train is
    train_interior, not station; an old mansion or its courtyard is haveli; a fair is mela), "era": ancient|modern|future, "culture": indian|western|japanese, "time": dawn|morning|noon|golden|
    dusk|night|midnight, "weather": clear|overcast|rain|storm|fog|snow, "mood": one or two words,
    "landmarks": 1-3 things seen there, "location_name": a short name for a place that may come back (e.g. "Dadi's
    house", "Lord's", "the old temple"), the SAME name every time the story returns there}}.
    Pick the time and weather that fit the moment (a scary scene at night in fog, a happy one in morning sun).
3b. 'walkthrough' (the showrunner's notes, in the episode's language, 1-2 sentences each, specific to THIS episode and
    its format, never generic): why_this_episode = why viewers will relate to it or care (the real-life feeling,
    question, fear, history or lesson it touches); bridge_from_last = how it follows the previous episode (or, for the
    first one, what it sets up); journey = what happens, briefly; next_teaser = what the ending sets up next.
4. 'visual_prompt': Highly detailed image-generation prompt (in English) matching the VISUAL STYLE DNA above:
   - Must explicitly describe the characters in frame using their persistent visual anchors.
   - Specify spatial positioning (e.g., 'Character A on the left smiling, Character B on the right pointing...').
   - Describe environment, lighting, mood and lens so it matches the format (dark and foggy for horror, bright for kids...).
4b. 'lines': the scene's spoken track as separate lines, in order: [{{"speaker": "Narrator" or a character name,
    "text": "...", "emotion": one of calm|happy|excited|sad|scared|angry|whisper|mysterious}}].
    'dialogue' must contain exactly the same lines written as "Speaker: text", one per line.
4c. 'shots': 2 to 4 camera shots for the scene, each {{"visual_prompt": "...", "camera_motion": one of
    dolly_in|dolly_out|pan_left|pan_right|tilt_up|tilt_down|zoom_punch|creep_in|drift_left|drift_right|shake|static}}.
    Vary framing (wide, medium, close-up, detail). The first shot's visual_prompt equals 'visual_prompt'.
4d. Set "teaser": true on the ONE scene that would make the best 45-second vertical teaser (the most gripping moment).
4e. Set "music_mood" for the episode: one of calm|playful|wonder|lullaby|epic|horror|tension|emotional|upbeat|synth|chiptune|quirky|jazz_noir.
    Each scene may set its own "music" from the same list when its feeling differs (a tense chase, a sad goodbye).
4f. A line may list sound effects heard as it is said, in "sfx": any of door_creak, knock, car_engine, car_horn,
    phone_ring, bell, thunder, wind_gust, clock_tick, bird, sparkle, heartbeat, horror_hit, whoosh, boing, pop,
    firework, splash, dog_bark, dog_growl, cat_meow, cow_moo, lion_roar, duck_quack, goat_baa, horse_neigh,
    elephant_trumpet, crow_caw, rooster, frog_croak, wolf_howl, snake_hiss, monkey, owl_hoot.
    An animal character's own noises are written in its line as the sound itself ("भौं-भौं!", "म्याऊँ!", "Woof!"),
    and the animation plays the real animal sound for them; stage directions go in brackets "(...)" and are not read.
    Use them only where the story needs them (a knock at the door, a car arriving), at most two per scene.
4g. The animation shows what the lines talk about. Write lines that name concrete things and happenings the viewer
    can see (falling stars, rain, lightning, fireworks, a rainbow, the moon, birds, butterflies, magic sparkles,
    wind, a ghost, a car, a bicycle, a ball, a cake, a gift, a box, a treasure chest, a book, a letter, a map, a
    key, a phone, a clock, a lantern, a candle, a campfire, flowers, an apple, laddoos, honey, ice cream, an egg,
    an umbrella, a drum, a crown, a kite, balloons, a glowing orb, a bell, a boat, a rocket).
    A line may also say what to show in "show": [{{"thing": "kite", "how": "enter" or "bubble"}}]; "bubble" puts
    it in a thought bubble (memories, wishes, imagination). At most two per scene.
5. COMPLETE EPISODIC STORY ARC (DO NOT CUT OFF IN BETWEEN):
   - The episode MUST be a complete standalone adventure that resolves its main quest or mystery within these {target_scenes} scenes!
   - Scenes 1 to 3: The Setup & Inciting Incident (discovering the mystery or problem).
   - Scenes 4 to {max(4, target_scenes - 3)}: The Investigation & Journey (overcoming obstacles, exploring temples/locations, working together).
   - Scenes {max(5, target_scenes - 2)} to {max(5, target_scenes - 1)}: THE CLIMAX & COMPLETE RESOLUTION (solving the central mystery, restoring the lost items/stars, triumphant celebration).
   - Final Scene {target_scenes}: Warm emotional reflection, gratitude, and a thrilling surprise cliffhanger/hook ('unresolved_hook') that teases the next episode!
   - The 'synopsis' field MUST describe the COMPLETE story arc from initial incident to triumphant resolution, never ending abruptly mid-sentence.
"""

    models = ai.models() or ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
    for m in models:
        try:
            raw = usage.studio_call(m, prompt, SCRIPT_SCHEMA, "Studio: episode script", ctx.get("title", ""), timeout=60)
            res = raw[0] if isinstance(raw, tuple) else raw
            if isinstance(res, dict) and "scenes" in res and len(res["scenes"]) >= 3:
                # Ensure voice_ids, default camera motions, and target durations
                for s in res["scenes"]:
                    spk = s.get("speaker", "").strip().lower()
                    if not s.get("voice_id"):
                        if spk in char_map and char_map[spk].get("voice_id"):
                            s["voice_id"] = char_map[spk]["voice_id"]
                        else:
                            s["voice_id"] = def_narrator_voice
                    _sync_legacy_fields(s)
                    if not s.get("camera_motion"):
                        s["camera_motion"] = "dolly_in"
                    if not s.get("duration_sec") or s.get("duration_sec") < 20:
                        s["duration_sec"] = float(scene_duration)
                _lengthen_short_scenes(res, scene_duration, lang, ctx.get("title", ""), char_desc)
                want = words_for(scene_duration, lang)
                said = [spoken_words(x) for x in res["scenes"]]
                res["length_check"] = {"target_sec": scene_duration * len(res["scenes"]),
                                       "estimated_sec": round(sum(said) / WORDS_PER_SEC.get(lang, 2.3) + 2 * len(said)),
                                       "short_scenes": [i + 1 for i, n in enumerate(said) if n < want * 0.75]}
                res["narrative_walkthrough"] = build_narrative_walkthrough(series_id, res, ep_num=len(ctx.get("episodes", [])) + 1)
                if cast:   # who the user chose, and anyone the AI still left without a line
                    res["cast"] = cast
                    res["cast_check"] = {"missing": missing_cast(res, cast)}
                return res
        except Exception as e:
            log.warning("Storyteller script generation failed on model %s: %s", m, e)

    # Robust multi-scene episodic fallback (for long-form videos: up to 24 scenes). It is a farm story, so only
    # kids & family formats use it; any other format says plainly that the AI is needed.
    if fmt.get("category") != "Kids & Family":
        return {"error": f"The AI could not write this {fmt['name']} script. Check the AI page (key, model, limits) and try again."}
    return _build_multi_scene_fallback(series_id, pitch_or_idea, target_scenes=target_scenes, scene_duration=scene_duration)


def _build_multi_scene_fallback(series_id: str, pitch_or_idea: dict | str, target_scenes: int = 12, scene_duration: int = 55) -> dict:
    """Generates a complete multi-scene episodic story arc matching target_scenes and scene_duration."""
    ctx = memory.get_continuity_context(series_id) or {}
    chars = ctx.get("characters", [])
    lang = (ctx.get("default_language") or "en").lower()
    def_narrator_voice = tts.default_voice_for_lang(lang)
    vstyle = ctx.get("visual_style") or "high-gloss 3D Pixar toy CGI, octane render, soft volumetric lighting, vibrant primary colors, 8k"

    lead_name = chars[0]["name"] if chars else ("Roo" if lang != "hi" else "छोटू")
    lead_voice = chars[0].get("voice_id", def_narrator_voice) if chars else def_narrator_voice
    lead_anchor = chars[0].get("visual_anchor", f"cute 3D cartoon {lead_name}") if chars else f"cute 3D cartoon {lead_name}"

    pal_name = chars[1]["name"] if len(chars) > 1 else ("Barnaby" if lang != "hi" else "भालू भाई")
    pal_voice = chars[1].get("voice_id", def_narrator_voice) if len(chars) > 1 else lead_voice
    pal_anchor = chars[1].get("visual_anchor", f"cute 3D cartoon {pal_name}") if len(chars) > 1 else lead_anchor

    title_seed = "The Golden Clue Adventure"
    if isinstance(pitch_or_idea, dict) and pitch_or_idea.get("title"):
        title_seed = pitch_or_idea["title"]
    elif isinstance(pitch_or_idea, str) and pitch_or_idea.strip():
        title_seed = pitch_or_idea.strip()[:40]

    if lang == "hi":
        fallback_title = f"{title_seed}" if any(ord(c) > 127 for c in title_seed) else f"{lead_name} और {pal_name} की सुनहरी खोज"
        fallback_synopsis = f"{lead_name} और {pal_name} ने मिलकर खेत में एक अनोखी चाबी ढूँढी और एक जादुई रहस्य को सुलझाया।"
        fallback_hook = "दूर जंगल के छोर से एक धीमी जादुई घंटी बजी, और एक नया गुप्त रास्ता दिखा।"
        
        templates = [
            {"setting": "हरे-भरे खेत और लाल बाड़े का सुंदर दृश्य", "speaker": "Narrator", "voice_id": def_narrator_voice, "camera": "pan_left",
             "dialogue": "सुप्रभात दोस्तों! आज की सुबह पंचतंत्र के इस जादुई हरे-भरे जंगल और पुराने खेत में बहुत ही अनोखी और रहस्यमयी है। पेड़ों की घनी डालियों से छनकर आती सुनहरी धूप पूरे रास्ते पर खिलते रंग-बिरंगे फूलों को चमका रही थी। हवा में एक मीठी सी खुशबू थी जो किसी बड़े रोमांच की तरफ इशारा कर रही थी। हमारे प्यारे जासूस, आज सुबह से ही कुछ नया और दिलचस्प खोजने के लिए पूरी तैयारी में थे।",
             "prompt": f"Wide establishing cinematic shot of sunny green farm, rustic wooden barn, golden volumetric sunbeams, {vstyle}"},
            {"setting": "बाड़े की लकड़ी की दीवार के पास", "speaker": lead_name, "voice_id": lead_voice, "camera": "dolly_in",
             "dialogue": "अरे भालू भाई, ज़रा यहाँ तो देखिए! इस पुरानी लकड़ी की बाड़ के ऊपर सुबह की धूप में कुछ बहुत तेज़ी से चमक रहा है। यह तो एक बहुत ही सुंदर और प्राचीन सुनहरी चाबी है! इस पर कुछ अजीब से जादुई निशान भी बने हुए हैं। क्या आपको लगता है कि यह वही चाबी है जिसका ज़िक्र जंगल की पुरानी कहानियों में आता था?",
             "prompt": f"Close-up 3D render of {lead_anchor} pointing excitedly at a glowing golden key resting on an old wooden fence, vibrant lighting, {vstyle}"},
            {"setting": "सुहावने सेब के बगीचे के रास्ते पर", "speaker": pal_name, "voice_id": pal_voice, "camera": "zoom_in",
             "dialogue": "छोटू, तुम बिल्कुल सही कह रहे हो! यह कोई मामूली चाबी नहीं है, बल्कि यह उस प्राचीन बगीचे के दरवाज़े की लग रही है जो सालों से बंद पड़ा है। अगर हम इस चाबी को उस पुराने दरवाज़े तक ले जाएं, तो शायद हमें वह खोया हुआ खज़ाना मिल जाए जिसके बारे में हमारे पुरखे बताया करते थे। चलो, बिना देर किए आगे का रास्ता ढूँढते हैं!",
             "prompt": f"Medium shot of {lead_anchor} and {pal_anchor} examining the mysterious golden key together with smiling curiosity, soft bokeh, {vstyle}"},
            {"setting": "फूलों से भरी पहाड़ी और बहती नदी के पास", "speaker": "Narrator", "voice_id": def_narrator_voice, "camera": "pan_right",
             "dialogue": "दोनों बहादुर दोस्त अपने कदम आगे बढ़ाते हुए फूलों की घाटी और कल-कल बहती नदी के किनारे चलने लगे। रास्ते में उन्हें हवा की सरसराहट और परिंदों के चहकने की मधुर आवाज़ें सुनाई दे रही थीं। हर कदम के साथ उनका उत्साह बढ़ता जा रहा था, क्योंकि वे जानते थे कि सच्ची दोस्ती और हिम्मत से वे किसी भी बड़ी पहेली को आसानी से सुलझा सकते हैं।",
             "prompt": f"Dynamic tracking shot of {lead_anchor} and {pal_anchor} happily walking through rolling green hills and colorful wildflowers, Pixar CGI, {vstyle}"},
            {"setting": "पुराने लकड़ी के दरवाज़े के सामने", "speaker": lead_name, "voice_id": lead_voice, "camera": "dolly_in",
             "dialogue": "देखो भालू भाई, हम आखिरकार उस विशालकाय रहस्यमयी दरवाज़े तक पहुँच ही गए! इस पर जंगली बेलें और रंग-बिरंगे काई जमे हुए हैं, और बीच में ठीक उसी आकार का एक चाबी का छेद बना हुआ है। मेरी धड़कनें तेज़ हो रही हैं। मैं धीरे से इस सुनहरी चाबी को ताले में घुमाने जा रहा हूँ। सब कुछ ठीक रहेगा ना?",
             "prompt": f"Low-angle 3D view of cute characters looking up at an overgrown ancient wooden door with an ornate keyhole, magical particles, {vstyle}"},
            {"setting": "जादुई बगीचे के अंदर चमचमाती धूप", "speaker": pal_name, "voice_id": pal_voice, "camera": "zoom_out",
             "dialogue": "क्लिक की आवाज़ आई और भारी दरवाज़ा धीरे-धीरे अपने आप खुलने लगा! ज़रा अपनी आँखों पर यकीन करो छोटू, अंदर तो मीठे जादुई फलों, चमकती तितलियों और बहुरंगी फव्वारों का एक अद्भुत नज़ारा है! हमारी मेहनत और समझदारी रंग लाई, हमने जंगल का सबसे बड़ा खोया हुआ रहस्य आखिरकार खोल ही दिया!",
             "prompt": f"Joyful celebratory wide shot of {lead_anchor} and {pal_anchor} cheering as the gate opens to reveal a sunlit wonderland, colorful balloons and confetti, {vstyle}"},
            {"setting": "शाम के वक्त सुंदर खेत के बीच", "speaker": "Narrator", "voice_id": def_narrator_voice, "camera": "orbit",
             "dialogue": "ढलती हुई शाम के साथ आसमान में नारंगी और गुलाबी रंग बिखरने लगे थे। हमारे दोनों प्यारे जासूस थके हुए लेकिन बेहद खुश थे। उन्होंने आज यह साबित कर दिखाया कि जब सच्चे दोस्त मिलकर किसी पहेली की तह तक जाने की ठान लेते हैं, तो नामुमकिन भी मुमकिन हो जाता है। पूरा जंगल आज उनकी समझदारी और बहादुरी के गीत गा रहा था।",
             "prompt": f"Warm twilight 3D render of happy friends sharing apples beside the cozy barn, soft purple and amber sky, high gloss render, {vstyle}"},
            {"setting": "दूर जंगल के छोर पर रहस्यमयी रोशनी", "speaker": lead_name, "voice_id": lead_voice, "camera": "dolly_in",
             "dialogue": "लेकिन ज़रा रुको भालू भाई! क्या तुमने वह देखा? दूर उस पुरानी पहाड़ी और पवनचक्की के ऊपर अचानक एक नीली जादुई रोशनी चमकने लगी है और हवा में एक नई धुन गूंज रही है! ऐसा लगता है कि आज का रहस्य तो सिर्फ एक शुरुआत थी, और कल एक और बहुत बड़ा रोमांच हमारा इंतज़ार कर रहा है!",
             "prompt": f"Atmospheric dusk shot of {lead_anchor} looking toward a distant glowing portal in the whispering woods, mysterious golden sparkles, {vstyle}"},
        ]
    else:
        fallback_title = title_seed or f"{lead_name}'s Great Discovery"
        fallback_synopsis = f"{lead_name} and {pal_name} discover a mysterious golden key on the farm and work together to unlock a forgotten garden treasure."
        fallback_hook = "A soft, melodic chime echoes from the distant windmill, revealing an ancient clue."
        
        templates = [
            {"setting": "Sunny green farmyard with red wooden barn", "speaker": "Narrator", "voice_id": def_narrator_voice, "camera": "pan_left",
             "dialogue": "Good morning, explorers! It was a radiant, golden sunrise across the rolling green hills of the farm, where wildflowers swayed gently in the breeze. Warm sunbeams filtered through the tall apple trees, painting the rustic wooden barn in rich amber tones. Everything felt calm and peaceful, yet an undeniable sense of magic whispered through the morning air, hinting that today was not going to be an ordinary day.",
             "prompt": f"Wide establishing cinematic shot of sunny green farm, rustic wooden barn, golden volumetric sunbeams, {vstyle}"},
            {"setting": "Near the wooden fence and barn doors", "speaker": lead_name, "voice_id": lead_voice, "camera": "dolly_in",
             "dialogue": "Hey partner, come take a close look at this! Resting right here on the sunlit fence post is an ornate, glowing golden key with mysterious carvings etched along its spine. Someone must have left it here very recently, or maybe it has been waiting decades for us to uncover its secret. What incredible hidden lock do you think this unlocks?",
             "prompt": f"Close-up 3D render of {lead_anchor} pointing excitedly at a glowing golden key resting on an old wooden fence, rich depth of field, {vstyle}"},
            {"setting": "Along the sunlit orchard pathway", "speaker": pal_name, "voice_id": pal_voice, "camera": "zoom_in",
             "dialogue": "That looks remarkably like the key from the old valley legends our elders used to speak of! If the stories are true, this unlocks the overgrown iron arbor gate at the edge of the forgotten orchard. We have solved tricky puzzles before, and together there is nothing we cannot figure out. Let us follow the cobblestone path and see where it leads!",
             "prompt": f"Medium shot of {lead_anchor} and {pal_anchor} examining the mysterious golden key together with smiling curiosity, soft bokeh, {vstyle}"},
            {"setting": "Rolling wildflower hills and babbling brook", "speaker": "Narrator", "voice_id": def_narrator_voice, "camera": "pan_right",
             "dialogue": "Side by side, our two adventurous friends marched happily through the vibrant sunflower fields and across the whispering wooden footbridge. The gentle burble of the stream matched the rhythm of their footsteps, and songbirds chirped cheerily overhead. Every turn of the trail brought new clues, reminding them that true discovery is sweetest when shared with a loyal companion.",
             "prompt": f"Dynamic tracking shot of {lead_anchor} and {pal_anchor} happily walking through rolling green hills and colorful wildflowers, Pixar CGI, {vstyle}"},
            {"setting": "Before the overgrown mossy garden gate", "speaker": lead_name, "voice_id": lead_voice, "camera": "dolly_in",
             "dialogue": "Here it is! An ancient, ivy-draped wooden gate with a gleaming brass keyhole nestled right in the center. My heart is beating with excitement! I am carefully inserting the golden key into the lock now. Let us turn it together on the count of three—one, two, three!",
             "prompt": f"Low-angle 3D view of cute characters looking up at an overgrown ancient wooden door with an ornate keyhole, magical particles, {vstyle}"},
            {"setting": "Inside the sunlit enchanted garden", "speaker": pal_name, "voice_id": pal_voice, "camera": "zoom_out",
             "dialogue": "With a crisp, satisfying click, the heavy gate swung wide open! Feast your eyes on this wondrous paradise—glowing crystalline fruits, fluttering rainbow butterflies, and a fountain of sparkling sweet water! All our hard work and deduction paid off, and we have revealed the valley's greatest wonder together!",
             "prompt": f"Joyful celebratory wide shot of {lead_anchor} and {pal_anchor} cheering as the gate opens to reveal a sunlit wonderland, colorful balloons and confetti, {vstyle}"},
            {"setting": "Cozy sunset pasture beside the barn", "speaker": "Narrator", "voice_id": def_narrator_voice, "camera": "orbit",
             "dialogue": "As golden dusk melted into a tranquil purple twilight, our triumphant heroes gathered beside the warm lantern light of the barn. Sharing sweet apples and recounting their favorite moments of the journey, they knew that true courage and teamwork had turned a simple mystery into an unforgettable triumph.",
             "prompt": f"Warm twilight 3D render of happy friends sharing apples beside the cozy barn, soft purple and amber sky, high gloss render, {vstyle}"},
            {"setting": "Edge of the forest at twilight", "speaker": lead_name, "voice_id": lead_voice, "camera": "dolly_in",
             "dialogue": "Wait just a second, partner! Did you catch that faint, shimmering melody drifting down from the old windmill on the far ridge? Look at those mysterious azure sparkles swirling in the evening breeze! Something tells me today's breakthrough was only chapter one, and tomorrow's quest will be even bigger!",
             "prompt": f"Atmospheric dusk shot of {lead_anchor} looking toward a distant glowing portal in the whispering woods, mysterious golden sparkles, {vstyle}"},
        ]

    count = max(3, min(int(target_scenes or 12), 24))
    scenes = []
    dur_target = float(scene_duration or 55.0)
    for i in range(count):
        idx = i % len(templates)
        t = templates[idx]
        sc_num = i + 1
        dur = dur_target
        scenes.append({
            "scene_num": sc_num,
            "duration_sec": dur,
            "setting": t["setting"],
            "characters": [lead_name, pal_name],
            "speaker": t["speaker"],
            "dialogue": t["dialogue"],
            "voice_id": t["voice_id"],
            "camera_motion": t["camera"],
            "visual_prompt": t["prompt"]
        })

    fallback_script = {
        "title": fallback_title,
        "synopsis": fallback_synopsis,
        "unresolved_hook": fallback_hook,
        "scenes": scenes
    }
    fallback_script["narrative_walkthrough"] = build_narrative_walkthrough(series_id, fallback_script, ep_num=len(ctx.get("episodes", [])) + 1)
    return fallback_script


def generate_single_scene(series_id: str, context: dict) -> dict:
    """Generates or auto-completes a single episodic scene based on full story context and prior scenes."""
    ctx = memory.get_continuity_context(series_id)
    if not ctx:
        return {}

    chars = ctx.get("characters", [])
    lang = (ctx.get("default_language") or "en").lower()
    def_narrator_voice = tts.default_voice_for_lang(lang)
    char_map = {c["name"].lower(): c for c in chars}
    char_desc = "\n".join([f"- {c['name']} (Voice: {c.get('voice_id', def_narrator_voice)}): Visual: {c.get('visual_anchor', '')}" for c in chars]) or "None yet."

    title = context.get("title") or context.get("episode_title") or ctx.get("title") or "Episode"
    synopsis = context.get("synopsis") or "An exciting 3D adventure"
    scenes = context.get("scenes") or []
    target_scene_num = int(context.get("target_scene_num") or (len(scenes) + 1))
    target_dur = float(context.get("target_duration") or context.get("scene_duration") or 60)
    user_instruction = (context.get("instruction") or "").strip()

    prior_scenes_summary = []
    for sc in scenes:
        num = sc.get("scene_num") or 1
        if num < target_scene_num:
            dlg = (sc.get("dialogue") or "").strip()
            dlg_preview = (dlg[:160] + "...") if len(dlg) > 160 else dlg
            prior_scenes_summary.append(
                f"Scene {num} [{sc.get('setting', 'Unknown')}]: Speaker={sc.get('speaker', 'Narrator')}. Dialogue: \"{dlg_preview}\""
            )

    following_scenes_summary = []
    for sc in scenes:
        num = sc.get("scene_num") or 1
        if num > target_scene_num:
            dlg = (sc.get("dialogue") or "").strip()
            dlg_preview = (dlg[:120] + "...") if len(dlg) > 120 else dlg
            following_scenes_summary.append(
                f"Scene {num} [{sc.get('setting', 'Unknown')}]: Speaker={sc.get('speaker', 'Narrator')}. Dialogue: \"{dlg_preview}\""
            )

    prior_ctx_text = "\n".join(prior_scenes_summary) if prior_scenes_summary else "This is the opening scene (Scene 1) of the episode."
    following_ctx_text = f"\nSubsequent Scene Plans:\n" + "\n".join(following_scenes_summary) if following_scenes_summary else ""
    instruction_text = f"\nDirector's Specific Scene Direction: {user_instruction}\n" if user_instruction else ""

    lang_rule = (
        f"Language Requirement: HINDI. Write the 'dialogue' in natural, engaging Hindi (Devanagari script), e.g. 'अरे देखो! यहाँ क्या है!'. Default narrator voice_id: '{def_narrator_voice}'."
        if lang == "hi"
        else f"Language Requirement: {lang.upper()}. Write 'dialogue' in this language. Default narrator voice_id: '{def_narrator_voice}'."
    )

    prompt = f"""You are the Lead Screenwriter & Visual Director for the 3D animated series "{ctx.get('title')}".
Genre: {ctx.get('genre')}
{_brief_rule(ctx)}{_places_rule(ctx)}Global 3D Visual Style: {ctx.get('visual_style')}
Aspect Ratio: {ctx.get('aspect_ratio', '16:9')}
{lang_rule}

CHARACTER VAULT & VISUAL ANCHORS:
{char_desc}

EPISODE PREMISE:
Title: {title}
Synopsis: {synopsis}

STORY CONTINUITY (PREVIOUS SCENES):
{prior_ctx_text}{following_ctx_text}{instruction_text}

TASK:
Write Scene {target_scene_num} directly continuing the narrative arc and story events from the preceding scenes!

MANDATORY RULES:
1. SCENE DURATION & DIALOGUE LENGTH:
   - Target duration: {int(target_dur)} seconds.
   - The 'dialogue' is the spoken voiceover track. It MUST be substantial and take ~{int(target_dur)} seconds to speak aloud ({_length_rule(target_dur, lang)}).
   - If Narrator: Provide rich atmospheric scene-setting, suspense, curiosity, and emotional storytelling.
   - If Character: Express vibrant personality, emotion, dialogue, teamwork, and reaction to the unfolding events.
2. SPEAKER & VOICE:
   - Choose the speaker logically (Narrator or one of the characters from the Character Vault).
   - Assign their persistent 'voice_id' (Narrator: '{def_narrator_voice}').
3. 3D VISUAL PROMPT:
   - Detailed 3D prompt written in English for high-end Pixar/Octane CGI 3D image synthesis.
   - Include character visual anchors, camera perspective, lighting, rich textures, and dramatic 3D composition.
4. CAMERA MOTION:
   - Select the most cinematic camera movement: 'dolly_in', 'dolly_out', 'pan_left', 'pan_right', 'zoom_in', 'zoom_out', or 'orbit'.
"""

    models = ai.models() or ["gemini-2.5-flash", "gemini-3.5-flash-lite"]
    for m in models:
        try:
            raw = usage.studio_call(m, prompt, SINGLE_SCENE_SCHEMA, "Studio: one scene", ctx.get("title", ""), timeout=45)
            res = raw[0] if isinstance(raw, tuple) else raw
            if isinstance(res, dict) and res.get("dialogue") and res.get("visual_prompt"):
                res["scene_num"] = target_scene_num
                res["duration_sec"] = float(res.get("duration_sec") or target_dur)
                spk = res.get("speaker", "").strip().lower()
                if not res.get("voice_id"):
                    if spk in char_map and char_map[spk].get("voice_id"):
                        res["voice_id"] = char_map[spk]["voice_id"]
                    else:
                        res["voice_id"] = def_narrator_voice
                if not res.get("camera_motion"):
                    res["camera_motion"] = "dolly_in"
                if not res.get("setting"):
                    res["setting"] = f"Scene {target_scene_num} Setting"
                if not res.get("characters"):
                    res["characters"] = [c["name"] for c in chars]
                return res
        except Exception as e:
            log.warning("Storyteller single scene generation failed on %s: %s", m, e)

    # Procedural fallback if AI is offline
    return _build_single_scene_fallback(ctx, title, synopsis, scenes, target_scene_num, target_dur, lang, def_narrator_voice, char_map)


def _build_single_scene_fallback(
    ctx: dict,
    title: str,
    synopsis: str,
    scenes: list[dict],
    target_scene_num: int,
    target_dur: float,
    lang: str,
    def_narrator_voice: str,
    char_map: dict
) -> dict:
    """Procedural fallback to generate a coherent continuation scene when AI call is offline."""
    chars = ctx.get("characters", [])
    vstyle = ctx.get("visual_style") or "high-gloss 3D Pixar toy CGI, octane render, soft volumetric lighting, vibrant primary colors, 8k"

    lead_name = chars[0]["name"] if chars else ("Roo" if lang != "hi" else "वीर")
    lead_voice = chars[0].get("voice_id", def_narrator_voice) if chars else def_narrator_voice
    lead_anchor = chars[0].get("visual_anchor", f"cute 3D cartoon {lead_name}") if chars else f"cute 3D cartoon {lead_name}"

    pal_name = chars[1]["name"] if len(chars) > 1 else ("Barnaby" if lang != "hi" else "गोलू")
    pal_voice = chars[1].get("voice_id", def_narrator_voice) if len(chars) > 1 else lead_voice
    pal_anchor = chars[1].get("visual_anchor", f"cute 3D cartoon {pal_name}") if len(chars) > 1 else lead_anchor

    prev_scene = scenes[-1] if scenes else None
    prev_setting = prev_scene.get("setting", "") if prev_scene else ""
    prev_speaker = prev_scene.get("speaker", "") if prev_scene else ""

    if prev_speaker == lead_name:
        chosen_speaker = pal_name
        chosen_voice = pal_voice
    elif prev_speaker == pal_name:
        chosen_speaker = "Narrator"
        chosen_voice = def_narrator_voice
    else:
        chosen_speaker = lead_name
        chosen_voice = lead_voice

    camera_motions = ["dolly_in", "zoom_in", "pan_left", "orbit", "pan_right", "dolly_out"]
    chosen_cam = camera_motions[(target_scene_num - 1) % len(camera_motions)]

    if lang == "hi":
        fallback_setting = f"{prev_setting} से आगे का रास्ता" if prev_setting else f"दृश्य {target_scene_num} - रहस्यमयी स्थान"
        if chosen_speaker == "Narrator":
            dlg = f"कहानी के इस नए मोड़ पर, वातावरण और भी रोमांचक हो गया। हवा में एक हल्की सी सिहरन थी और चारों तरफ फैली रहस्यमयी रोशनी ने एक नया रास्ता दिखाया। हमारे बहादुर साथी बिना किसी डर के आगे बढ़ रहे थे, क्योंकि वे जानते थे कि हर पहेली का हल हिम्मत और समझदारी में छुपा होता है।"
        elif chosen_speaker == lead_name:
            dlg = f"अरे {pal_name}, ज़रा यहाँ देखो! मुझे लगता है कि हम अपनी मंजिल के बहुत करीब पहुँच चुके हैं। सामने जो चमकती हुई संरचना दिखाई दे रही है, वह ज़रूर किसी बड़े रहस्य का दरवाज़ा है। चलो मिलकर इसे ध्यान से देखते हैं और पता लगाते हैं कि आगे क्या छुपा है!"
        else:
            dlg = f"{lead_name}, तुम बिल्कुल सही कह रहे हो! यह नज़ारा सचमुच अद्भुत है। हमें बहुत सावधानी से कदम बढ़ाने होंगे ताकि कोई भी ज़रूरी सुराग हमसे छूट न जाए। मुझे पूरा भरोसा है कि हमारी दोस्ती और लगन से हम इस रहस्य को ज़रूर सुलझा लेंगे!"
        vprompt = f"Cinematic 3D render of {lead_anchor} and {pal_anchor} exploring {fallback_setting}, dynamic volumetric godrays, glowing atmospheric magical sparkles, octane render, {vstyle}"
    else:
        fallback_setting = f"Path advancing from {prev_setting}" if prev_setting else f"Scene {target_scene_num} - Enchanted Realm"
        if chosen_speaker == "Narrator":
            dlg = f"At this thrilling juncture of their adventure, the atmosphere grew even more enchanting. Soft luminous particles drifted through the air, highlighting a newly uncovered pathway ahead. Our courageous friends pressed forward with unwavering curiosity, determined to uncover every piece of the puzzle."
        elif chosen_speaker == lead_name:
            dlg = f"Look closely over there, {pal_name}! I believe we are closer to the heart of the mystery than ever before. That shimmering architecture in the distance must hold the answer we have been searching for. Let us work together and see what secrets it reveals!"
        else:
            dlg = f"You are absolutely right, {lead_name}! This is truly an astonishing sight. We must examine the clues carefully so we do not miss anything important. Together, with our teamwork, there is no challenge we cannot overcome!"
        vprompt = f"Cinematic 3D render of {lead_anchor} and {pal_anchor} exploring {fallback_setting}, dynamic volumetric godrays, glowing atmospheric magical sparkles, octane render, {vstyle}"

    return {
        "scene_num": target_scene_num,
        "duration_sec": float(target_dur),
        "setting": fallback_setting,
        "characters": [lead_name, pal_name],
        "speaker": chosen_speaker,
        "voice_id": chosen_voice,
        "camera_motion": chosen_cam,
        "dialogue": dlg,
        "visual_prompt": vprompt
    }


NARRATIVE_SCHEMA = {"type": "OBJECT", "properties": {
    "why_this_episode": {"type": "STRING"}, "bridge_from_last": {"type": "STRING"},
    "journey": {"type": "STRING"}, "next_teaser": {"type": "STRING"}},
    "required": ["why_this_episode", "bridge_from_last", "journey", "next_teaser"]}

# when no AI can write it: a "why" that fits the kind of show, not the same kids' line for every format
WHY_BY_CATEGORY = {
    "en": {"Kids & Family": "It turns a small everyday problem kids know into a fun adventure, with a feeling they recognise.",
           "Horror & Thriller": "It plays on a fear everyone shares: something familiar that turns out not to be safe.",
           "Documentary & Education": "It brings a real story from the past close, through the people who lived it.",
           "Anime & Stylised": "It gives the heroes a challenge that tests what they believe in.",
           "Cinematic Fiction": "It puts the characters in a choice viewers have faced themselves.",
           "Faceless Channels": "It speaks to a struggle many viewers are going through right now."},
    "hi": {"Kids & Family": "यह एपिसोड बच्चों की रोज़ की एक छोटी-सी परेशानी को मज़ेदार रोमांच में बदल देता है, जिससे वे खुद को जोड़ पाते हैं।",
           "Horror & Thriller": "यह उस डर को छूता है जो हम सब जानते हैं: कोई जानी-पहचानी चीज़ जो अचानक सुरक्षित नहीं लगती।",
           "Documentary & Education": "यह अतीत की एक सच्ची कहानी को उन लोगों के ज़रिए पास लाता है जिन्होंने उसे जिया।",
           "Anime & Stylised": "यह हमारे नायकों के सामने ऐसी चुनौती रखता है जो उनके विश्वास की परीक्षा लेती है।",
           "Cinematic Fiction": "यह किरदारों को ऐसे फ़ैसले के सामने खड़ा करता है जिसका सामना दर्शक खुद कर चुके हैं।",
           "Faceless Channels": "यह उस संघर्ष की बात करता है जिससे आज बहुत से दर्शक गुज़र रहे हैं।"},
}


def _clean_walk(w) -> dict:
    if not isinstance(w, dict):
        return {}
    keys = ("why_this_episode", "bridge_from_last", "journey", "next_teaser")
    return {k: str(w.get(k) or "").strip()[:600] for k in keys if str(w.get(k) or "").strip()}


def _walk_from_ai(s: dict, script_or_ep: dict, ep_num: int, prev_ep: dict | None) -> dict:
    """One AI call that writes the four notes from the episode itself (for episodes made before the script writer
    wrote them)."""
    if not ai.ready():
        return {}
    fmt = formats.resolve(s)
    lang = (s.get("default_language") or "en").lower()
    lines = []
    for sc in (script_or_ep.get("scenes") or script_or_ep.get("script") or [])[:10]:
        for ln in (sc.get("lines") or [])[:2]:
            if ln.get("text"):
                lines.append(f"{ln.get('speaker', '')}: {ln['text']}")
    prompt = f"""You are the showrunner of the YouTube series "{s.get('title', '')}" ({fmt['name']}, {fmt['category']};
audience {fmt['audience']}; tone: {fmt['story']['tone']}).
Write short notes about Episode {ep_num}: "{script_or_ep.get('title', '')}", in the language "{lang}"{' (Devanagari)' if lang == 'hi' else ''}.
What happens: {str(script_or_ep.get('synopsis') or script_or_ep.get('summary') or '')[:900]}
Some lines: {' | '.join(lines)[:900] or '-'}
Ending / hook: {script_or_ep.get('unresolved_hook') or '-'}
Previous episode: {(f"{prev_ep.get('title', '')}: {str(prev_ep.get('summary', ''))[:300]} (hook: {prev_ep.get('unresolved_hook', '')})") if prev_ep else 'none, this is the first episode'}

1-2 sentences each, specific to THIS episode and format, never generic: why_this_episode (why viewers will relate
to it or care: the real-life feeling, question, fear, history or lesson it touches), bridge_from_last, journey,
next_teaser.
"""
    for m in ai.models() or []:
        try:
            raw = usage.studio_call(m, prompt, NARRATIVE_SCHEMA, "Studio: director's notes", s.get("title", ""),
                                    timeout=30, temperature=0.7)
            w = _clean_walk(raw[0] if isinstance(raw, tuple) else raw)
            if len(w) >= 3:
                return w
        except Exception as e:  # noqa: BLE001
            log.warning("director's notes from %s failed: %s", m, e)
    return {}


def build_narrative_walkthrough(series_id: str, script_or_ep: dict, ep_num: int | None = None) -> dict:
    """The Director's Narrative for an episode: why it was chosen (what makes it relatable), how it follows the last
    one, what happens, and what comes next, plus the same as one spoken text.

    Written for THIS episode: by the script writer along with the script (its 'walkthrough'), else by one AI call
    from the episode, else from the episode's own facts with a 'why' that fits the kind of show."""
    s = memory.get_series(series_id) or {}
    series_title = s.get("title", "3D Series")
    lang = (s.get("default_language") or "en").lower()
    episodes = s.get("episodes", [])
    fmt = formats.resolve(s)

    current_ep_num = ep_num or script_or_ep.get("episode_num") or (len(episodes) + 1)
    title = script_or_ep.get("title") or f"Episode {current_ep_num}"
    synopsis = script_or_ep.get("synopsis") or script_or_ep.get("summary") or ""
    hook = script_or_ep.get("unresolved_hook") or ""
    prev_ep = None
    if current_ep_num > 1 and episodes:
        prev_ep = next((e for e in episodes if e.get("episode_num") == current_ep_num - 1), None)

    w = _clean_walk(script_or_ep.get("walkthrough")) or _walk_from_ai(s, script_or_ep, current_ep_num, prev_ep)
    hi = lang == "hi"
    why = w.get("why_this_episode") or WHY_BY_CATEGORY["hi" if hi else "en"].get(fmt["category"]) or ""
    if w.get("bridge_from_last"):
        bridge = w["bridge_from_last"]
    elif prev_ep:
        bridge = (f"पिछले एपिसोड '{prev_ep.get('title', '')}' के अंत में: {prev_ep.get('unresolved_hook') or prev_ep.get('summary', '')}"
                  if hi else f"Last time, in '{prev_ep.get('title', '')}': {prev_ep.get('unresolved_hook') or prev_ep.get('summary', '')}")
    else:
        bridge = (f"'{series_title}' का पहला एपिसोड: यहीं से कहानी शुरू होती है।" if hi
                  else f"The first episode of '{series_title}': where the story begins.")
    journey = w.get("journey") or synopsis
    teaser = w.get("next_teaser") or hook
    if hi:
        spoken = (f"नमस्ते! '{series_title}' के एपिसोड {current_ep_num}, '{title}' में आपका स्वागत है। {bridge} "
                  f"{why} {journey} {teaser}").strip()
    else:
        spoken = (f"Welcome to Episode {current_ep_num} of {series_title}: '{title}'. {bridge} {why} {journey} "
                  f"{teaser}").strip()
    return {
        "episode_num": current_ep_num,
        "title": title,
        "context_motivation": why,
        "previous_bridge": bridge,
        "current_journey": journey,
        "next_teaser": teaser,
        "full_spoken_script": re.sub(r"\s+", " ", spoken).replace("।।", "।"),
        "written_by": "script" if script_or_ep.get("walkthrough") else ("ai" if w else "template"),
    }


def get_or_create_episode_narrative(series_id: str, ep_num: int) -> dict:
    """Returns or generates the narrative walkthrough for an existing episode."""
    ep = memory.get_episode(series_id, ep_num)
    if not ep:
        return {}
    nw = ep.get("narrative_walkthrough")
    if nw and nw.get("written_by") in ("script", "ai"):
        return nw
    walkthrough = build_narrative_walkthrough(series_id, ep, ep_num)
    ep["narrative_walkthrough"] = walkthrough
    memory.add_episode(series_id, ep)
    return walkthrough



def get_market_trends(country: str = "IN") -> list[dict]:
    """Returns curated and AI-analyzed viral 3D animation series concepts tailored to the selected country/market.

    Each blueprint includes title, genre, target audience, visual aesthetic, logline, viral hook, and character seeds.
    """
    country_code = (country or "IN").strip().upper()

    trends_map = {
        "IN": [
            {
                "id": "in_panchatantra_3d",
                "title": "Panchatantra 3D: Forest Detective Friends",
                "category": "🔥 140M+ Monthly Views Trend",
                "genre": "3D Moral Cartoon Fables",
                "target_audience": "Preschool & Kids (Ages 3-8)",
                "default_language": "hi",
                "logline": "In the enchanted forest of Naimisha, wise little Bhalu Bhai (Brown Bear) and his speedy bunny pal Chhotu solve daily animal mysteries using kindness, wits, and ancient moral fables.",
                "hook": "Every episode leaves a curious footprint or nature clue that unlocks the secret tree of wisdom.",
                "visual_style": "high-gloss 3D Pixar toy CGI, octane render, soft volumetric lighting, vibrant primary colors, 8k",
                "character_seed": [
                    {"name": "Bhalu Bhai", "species": "Brown Bear", "personality": "Wise, calm, loves sweet mangoes and problem solving", "visual_anchor": "cute chubby brown bear, bright yellow knit scarf, glossy Pixar eyes", "voice_id": "hi-IN-MadhurNeural"},
                    {"name": "Chhotu", "species": "White Bunny", "personality": "Brave, energetic, super-fast explorer", "visual_anchor": "tiny fluffy white bunny cub, sky blue bow tie, pink inner ears", "voice_id": "hi-IN-SwaraNeural"}
                ],
                "sample_episodes": ["The Mystery of the Vanishing Honey Pot", "The Singing River Riddle", "The Brave Little Firefly's Lantern"]
            },
            {
                "id": "in_mythology_wonder",
                "title": "Bal Veer & The Secret Sky Kingdom",
                "category": "Mythology Wonder 3D",
                "genre": "Mythological Fantasy 3D",
                "target_audience": "Kids & Family (Ages 5-11)",
                "default_language": "hi",
                "logline": "A spirited young Indian boy discovers magic feather sandals that let him hop across golden monsoon cloud temples, helping celestial baby critters solve playful cosmic puzzles.",
                "hook": "Collecting the 7 mystic glowing lotus petals hidden across ancient sacred groves.",
                "visual_style": "dreamy 3D cinematic animation, golden hour volumetric godrays, glowing celestial magic, vibrant Indian motifs, 8k",
                "character_seed": [
                    {"name": "Veer", "species": "Young Hero", "personality": "Playful, adventurous, compassionate and daring", "visual_anchor": "spirited 3d indian cartoon boy, crimson cape, glowing feather sneakers", "voice_id": "hi-IN-MadhurNeural"},
                    {"name": "Golu", "species": "Baby Cloud Critter", "personality": "Cute, giggly, floats around like cotton candy", "visual_anchor": "sparkling chubby baby cloud with rosy cheeks and tiny golden crown", "voice_id": "hi-IN-SwaraNeural"}
                ],
                "sample_episodes": ["The Golden Cloud Bridge", "The Mischievous Wind Sprite", "The Celestial Lotus Awakening"]
            },
            {
                "id": "in_gully_inventors",
                "title": "Gully Gang 3D: The Secret Toy Inventors",
                "category": "STEM & Town Adventures",
                "genre": "Modern Neighborhood 3D",
                "target_audience": "Kids (Ages 4-10)",
                "default_language": "hi",
                "logline": "Two clever neighborhood kids build hilarious DIY gadgets from recycled rickshaw bells and wooden gears, rescuing lost street puppies and fixing town mysteries.",
                "hook": "Their secret rooftop treehouse mailbox receives mystery envelopes from a mysterious neighbor.",
                "visual_style": "colorful 3D claymation aesthetic, stylized modern Indian streets, sunlit pastel buildings, warm textures",
                "character_seed": [
                    {"name": "Kabir", "species": "Kid Tinkerer", "personality": "Passionate inventor with a pocket full of tools", "visual_anchor": "spunky 3d boy with magnifying goggles and cool tool apron", "voice_id": "hi-IN-MadhurNeural"},
                    {"name": "Ananya", "species": "Tech Whiz", "personality": "Logical, witty, quick with puzzles", "visual_anchor": "bright girl with high ponytail, denim jacket and glowing smartwatch", "voice_id": "hi-IN-SwaraNeural"}
                ],
                "sample_episodes": ["The Flying Rickshaw Gadget", "The Case of the Missing Mangoes", "The Midnight Rooftop Signal"]
            },
            {
                "id": "in_aryavarta_detectives",
                "title": "Aryavarta 3D: Royal Palace Mysteries",
                "category": "🔥 Realistic Historical Human Drama Trend",
                "genre": "Cinematic Historical 3D Drama",
                "target_audience": "Family & Youth (Ages 10+)",
                "default_language": "hi",
                "logline": "In an ancient majestic Indian kingdom, wise scholar Acharya Dev and the quick-witted Princess Malini solve deep political riddles, lost relic thefts, and palace conspiracies.",
                "hook": "Every episode decodes an ancient Sanskrit cipher etched on copper temple plates.",
                "visual_style": "cinematic 3D live-action aesthetic, photorealistic human characters, natural golden hour lighting, rich ancient silk attire, 8k cinematic",
                "character_seed": [
                    {"name": "Acharya Dev", "species": "Human Royal Scholar", "personality": "Wise investigator of ancient secrets", "visual_anchor": "dignified Indian scholar with saffron robes, rudraksha mala, sharp expressive eyes", "voice_id": "hi-IN-MadhurNeural"},
                    {"name": "Princess Malini", "species": "Human Archer & Strategist", "personality": "Courageous, quick-witted, tactical", "visual_anchor": "brave Indian princess in royal silk armor with golden recurve bow", "voice_id": "hi-IN-SwaraNeural"}
                ],
                "sample_episodes": ["The Mystery of the Stolen Scepter", "The Whispering Stone Inscription", "The Siege of the Sun Temple"]
            },
            {
                "id": "in_dadi_bedtime",
                "title": "Dadi Ma's 3D Bedtime Jadoo",
                "category": "Cozy Bedtime / Lullaby",
                "genre": "Calm Bedtime 3D Fables",
                "target_audience": "Toddlers & Preschool (Ages 2-6)",
                "default_language": "hi",
                "logline": "Gentle, soothing nighttime stories where glowing moonlit forest creatures tuck into bed, learning sweet lessons of gratitude, kindness, and sweet dreams.",
                "hook": "Soft twinkling stars and calming melodies designed to relax kids into peaceful sleep.",
                "visual_style": "soft pastel 3D squishy toy aesthetic, cozy twilight glow, glowing stars, pillowy soft textures",
                "character_seed": [
                    {"name": "Dadi Ma", "species": "Warm Storyteller", "personality": "Loving, gentle, soothing bedtime voice", "visual_anchor": "kind smiling Indian grandmother with silver hair bun, warm pink shawl", "voice_id": "hi-IN-SwaraNeural"},
                    {"name": "Tara", "species": "Twinkling Star", "personality": "Sleepy, sweet baby star that glimmers softly", "visual_anchor": "glowing golden star with cute cartoon smile and nightcap", "voice_id": "hi-IN-SwaraNeural"}
                ],
                "sample_episodes": ["The Sleepy Moon Bear", "The River That Sings Lullabies", "Where Do Dreams Go?"]
            }
        ],
        "US": [
            {
                "id": "us_cyber_detectives",
                "title": "Cyber Detectives: Neo-Metropolis 2099",
                "category": "🔥 Realistic 3D Human Sci-Fi Trend",
                "genre": "Cinematic 3D Human Sci-Fi Drama",
                "target_audience": "Teens & Adults (Ages 13+)",
                "default_language": "en",
                "logline": "In a rain-slicked neon metropolis, human Cyber Detective Kabir and neural engineer Dr. Maya solve high-stakes technological mysteries and uncover rogue AI syndicates.",
                "hook": "Every crime scene contains a glitching memory shard that reveals a piece of the city's hidden conspiracy.",
                "visual_style": "hyper-realistic 3D Unreal Engine 5 render, cinematic lighting, realistic human skin textures, ray tracing, neon rain reflections, 8k photorealistic",
                "character_seed": [
                    {"name": "Inspector Kabir", "species": "Human Cyber Detective", "personality": "Sharp, observant, relentless truth seeker", "visual_anchor": "tall human detective in dark trenchcoat with neon collar glow, detailed realistic facial features", "voice_id": "en-US-ChristopherNeural"},
                    {"name": "Dr. Maya", "species": "Human Neural Scientist", "personality": "Brilliant, cautious, tech strategist", "visual_anchor": "sharp human female scientist with holographic glasses and lab tech suit", "voice_id": "en-US-JennyNeural"}
                ],
                "sample_episodes": ["The Ghost in the Hologram", "The Neon Blackout Mystery", "The Quantum Cipher Heist"]
            },
            {
                "id": "us_monster_trucks",
                "title": "Monster Truck Rescue Squad 3D",
                "category": "🔥 180M+ Monthly Views Phenomenon",
                "genre": "Vehicles & Teamwork 3D",
                "target_audience": "Toddlers & Preschool (Ages 2-6)",
                "default_language": "en",
                "logline": "Max the shiny red monster truck and his mini excavator pals build obstacle bridges, clear muddy roadways, and rescue stranded toy cars in Gearville.",
                "hook": "Every episode ends with an epic stunt ramp launch that solves a city challenge.",
                "visual_style": "high-gloss 3D Pixar toy CGI, shiny candy car paint, chunky rubber tires, vibrant primary colors, 8k",
                "character_seed": [
                    {"name": "Max", "species": "Monster Truck", "personality": "Brave, loud, cheerful leader", "visual_anchor": "candy red monster truck with big friendly cartoon eyes in windshield", "voice_id": "en-US-ChristopherNeural"},
                    {"name": "Pip", "species": "Mini Excavator", "personality": "Eager, energetic digger", "visual_anchor": "sunny yellow mini excavator with cute hard hat", "voice_id": "en-US-JennyNeural"}
                ],
                "sample_episodes": ["The Muddy Mountain Slide", "The Giant Ramp Rescue", "The Mystery Tunnel Bridge"]
            },
            {
                "id": "us_cosmo_critters",
                "title": "Cosmo Critters: Tiny Space Explorers",
                "category": "Space Discovery 3D",
                "genre": "Sci-Fi Kids 3D",
                "target_audience": "Kids (Ages 4-8)",
                "default_language": "en",
                "logline": "Four baby animal astronauts rocket across bouncy candy planets, collecting glowing cosmic stardust to power their spaceship's bubble engine.",
                "hook": "Each planet has a unique gravitational quirk (bouncy gravity, floating bubbles, color-changing ground).",
                "visual_style": "whimsical 3D cartoon, neon nebula volumetric glows, cute round astronaut suits, 8k",
                "character_seed": [
                    {"name": "Nova", "species": "Space Fox", "personality": "Clever navigator, loves stargazing", "visual_anchor": "orange fox in white NASA-style cartoon spacesuit with golden visor", "voice_id": "en-US-ChristopherNeural"},
                    {"name": "Orbit", "species": "Alien Puff", "personality": "Curious little floating alien pet", "visual_anchor": "sparkling turquoise fuzzy creature that glows when happy", "voice_id": "en-US-JennyNeural"}
                ],
                "sample_episodes": ["The Bouncy Jelly Asteroid", "The Lost Stardust Compass", "The Singing Ring of Saturn"]
            },
            {
                "id": "us_dino_daycare",
                "title": "Dino Daycare: Prehistoric Pals",
                "category": "Cute Dinosaurs",
                "genre": "Preschool 3D Fun",
                "target_audience": "Toddlers (Ages 2-5)",
                "default_language": "en",
                "logline": "Baby T-Rex and his gentle herbivore buddies learn sharing, roaring softly, and building gigantic block castles under the watchful eye of Mama Bronto.",
                "hook": "A volcano that erupts confetti and rainbow bubbles when the dinos clean up their toys.",
                "visual_style": "squishy 3D toy vinyl aesthetic, vibrant pastel prehistoric foliage, soft rounded edges",
                "character_seed": [
                    {"name": "Rexy", "species": "Baby T-Rex", "personality": "Excited, clumsy, learns to be gentle", "visual_anchor": "chubby emerald green baby dinosaur with tiny orange spots", "voice_id": "en-US-ChristopherNeural"},
                    {"name": "Penny", "species": "Baby Triceratops", "personality": "Thoughtful, loves stacking colorful blocks", "visual_anchor": "sweet lavender baby triceratops with soft pink horns", "voice_id": "en-US-JennyNeural"}
                ],
                "sample_episodes": ["Rexy's Gentle Roar", "The Big Block Tower", "The Rainbow Bubble Volcano"]
            },
            {
                "id": "us_backyard_detectives",
                "title": "Backyard Detective Club 3D",
                "category": "Mystery & Nature",
                "genre": "Adventure Mystery",
                "target_audience": "Kids (Ages 5-10)",
                "default_language": "en",
                "logline": "Two curious siblings shrink down with a magic looking-glass to explore the buzzing miniature society of garden bugs, frogs, and hedgehogs.",
                "hook": "Decoding miniature blueprints left by the Secret Squirrel Society.",
                "visual_style": "macro 3D depth of field, lush sunlit garden, vibrant dew drops, Pixar lighting",
                "character_seed": [
                    {"name": "Leo", "species": "Boy Explorer", "personality": "Observant, keeps a nature journal", "visual_anchor": "cute 3d boy in explorer vest with large magnifying glass", "voice_id": "en-US-ChristopherNeural"},
                    {"name": "Bella", "species": "Bug Whisperer", "personality": "Feisty, climbs everything, loves beetles", "visual_anchor": "energetic girl with braided pigtails and ladybug backpack", "voice_id": "en-US-JennyNeural"}
                ],
                "sample_episodes": ["The Mystery of the Acorn Vault", "The Firefly Traffic Jam", "The Secret Under the Flowerpot"]
            }
        ],
        "JP": [
            {
                "id": "jp_bento_town",
                "title": "Bento Town: Cute Food Spirits 3D",
                "category": "Chibi Anime 3D",
                "genre": "Whimsical Food Fantasy",
                "target_audience": "Kids & All Ages",
                "default_language": "ja",
                "logline": "In a cozy wooden bento box world, Onigiri-kun and Tamago-chan embark on cute culinary quests, helping hungry forest spirits find harmony.",
                "hook": "Secret delicious recipe magic that blooms into glowing sakura petals.",
                "visual_style": "chibi 3D anime, glossy porcelain glaze textures, kawaii expressions, pastel lighting",
                "character_seed": [
                    {"name": "Onigiri-kun", "species": "Rice Ball Spirit", "personality": "Loyal, cheerful, loves traveling", "visual_anchor": "smiling triangular rice ball with nori belt and blushing cheeks", "voice_id": "ja-JP-KeitaNeural"},
                    {"name": "Tamago-chan", "species": "Egg Roll Fairy", "personality": "Sweet, bubbly, dances gracefully", "visual_anchor": "golden sweet tamagoyaki fairy with tiny butter wings", "voice_id": "ja-JP-NanamiNeural"}
                ],
                "sample_episodes": ["The Golden Sesame Seed Quest", "The Sparkling Miso River", "The Great Cherry Blossom Feast"]
            },
            {
                "id": "jp_cloud_railway",
                "title": "Kitten Express: Cloud Railway 3D",
                "category": "Soothing Fantasy",
                "genre": "Gentle Adventure 3D",
                "target_audience": "Kids & Family",
                "default_language": "ja",
                "logline": "A fluffy calico kitten conducts a glowing miniature steam locomotive across floating cloud stations, delivering dreams and starlight letters.",
                "hook": "Mysterious golden tickets that take passengers to forgotten childhood memories.",
                "visual_style": "Studio Ghibli warmth meets 3D Pixar toy rendering, soft twilight atmosphere",
                "character_seed": [
                    {"name": "Conductor Mochi", "species": "Calico Kitten", "personality": "Polite, punctual, carries a pocket watch", "visual_anchor": "fluffy calico kitten in navy blue train conductor hat and brass whistle", "voice_id": "ja-JP-NanamiNeural"},
                    {"name": "Sparky", "species": "Firefly Lantern", "personality": "Gentle guiding light of the locomotive", "visual_anchor": "warm glowing firefly inside a brass vintage carriage lantern", "voice_id": "ja-JP-KeitaNeural"}
                ],
                "sample_episodes": ["The Sunset Cloud Station", "The Letter to the Moon", "The Whistle That Plays Melodies"]
            }
        ],
        "GB": [
            {
                "id": "gb_bramblewood",
                "title": "Bramblewood Hollow: Storybook Friends",
                "category": "Classic Storybook 3D",
                "genre": "Gentle Woodland Adventures",
                "target_audience": "Preschool & Kids (Ages 3-7)",
                "default_language": "en",
                "logline": "Barnaby the cozy badger and Pippa the hedgehog solve neighborly woodland conundrums, bake blackberry pies, and share afternoon tea.",
                "hook": "Finding hidden woodland treasures marked on Grandpa Badger's vintage map.",
                "visual_style": "Beatrix Potter-inspired 3D storybook, soft tactile felt & wood textures, warm teatime lighting",
                "character_seed": [
                    {"name": "Barnaby", "species": "Badger", "personality": "Wise, pipe-smoking gentleness, loves tea", "visual_anchor": "kind badgeman in tweed waistcoat and round brass spectacles", "voice_id": "en-GB-RyanNeural"},
                    {"name": "Pippa", "species": "Hedgehog", "personality": "Sprightly, carries an apron with blackberry stains", "visual_anchor": "cute hedgehog with soft quills and a gingham checked apron", "voice_id": "en-GB-SoniaNeural"}
                ],
                "sample_episodes": ["The Mystery of the Teapot Key", "The Autumn Blackberry Festival", "The Lost Windmill Sail"]
            }
        ]
    }

    # Return trends for matching country or fallback to India/US
    if country_code in trends_map:
        return trends_map[country_code]
    elif country_code in ("US", "CA", "AU"):
        return trends_map["US"]
    elif country_code in ("JP", "KR"):
        return trends_map["JP"]
    elif country_code in ("GB", "IE", "NZ"):
        return trends_map["GB"]
    else:
        return trends_map["IN"]



def _sync_legacy_fields(s: dict) -> None:
    """The script editor shows `speaker`, `dialogue` and `visual_prompt`; fill them from `lines` / `shots`
    so both views agree (production.normalize_scene treats an edit of the old fields as the new truth)."""
    lines = [x for x in (s.get("lines") or []) if (x.get("text") or "").strip()]
    if lines:
        s["dialogue"] = "\n".join(f"{x.get('speaker') or 'Narrator'}: {x['text'].strip()}" for x in lines)
        talkers = [x.get("speaker") for x in lines if (x.get("speaker") or "").lower() != "narrator"]
        s["speaker"] = talkers[0] if talkers else "Narrator"
        s["characters"] = sorted(set(s.get("characters") or []) | set(t for t in talkers if t))
    shots = [x for x in (s.get("shots") or []) if (x.get("visual_prompt") or "").strip()]
    if shots:
        if not (s.get("visual_prompt") or "").strip():
            s["visual_prompt"] = shots[0]["visual_prompt"]
        elif shots[0]["visual_prompt"].strip() != s["visual_prompt"].strip():
            shots.insert(0, {"visual_prompt": s["visual_prompt"], "camera_motion": s.get("camera_motion", "")})
        s["shots"] = shots


def missing_cast(script: dict, cast: list) -> list:
    """The chosen characters who got no line in the script."""
    said = set()
    for sc in script.get("scenes", []) or []:
        for ln in sc.get("lines") or []:
            said.add(str(ln.get("speaker") or "").strip().lower())
        if sc.get("speaker"):
            said.add(str(sc["speaker"]).strip().lower())
        for row in str(sc.get("dialogue") or "").splitlines():
            if ":" in row:
                said.add(row.split(":", 1)[0].strip().lower())
    return [n for n in cast if n.strip().lower() not in said]


LENGTHEN_SCHEMA = {"type": "OBJECT", "properties": {"scenes": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
    "scene_num": {"type": "INTEGER"},
    "lines": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "speaker": {"type": "STRING"}, "text": {"type": "STRING"}, "emotion": {"type": "STRING"}},
        "required": ["speaker", "text"]}}},
    "required": ["scene_num", "lines"]}}}, "required": ["scenes"]}


def _lengthen_short_scenes(script: dict, scene_duration: float, lang: str, series_title: str, char_desc: str) -> None:
    """Scenes whose lines are too few for the chosen scene length (an AI often writes half) get their lines
    extended by one more AI call: same story, same speakers, more back-and-forth and description."""
    want = words_for(scene_duration, lang)
    scenes = script.get("scenes") or []
    short = [sc for sc in scenes if spoken_words(sc) < want * 0.8]
    if not short or not ai.ready():
        return
    rows = [{"scene_num": sc.get("scene_num") or i + 1, "setting": sc.get("setting", ""),
             "lines": [{"speaker": x.get("speaker"), "text": x.get("text"), "emotion": x.get("emotion", "")}
                       for x in sc.get("lines") or []] or [{"speaker": sc.get("speaker", "Narrator"), "text": sc.get("dialogue", "")}]}
            for i, sc in enumerate(scenes) if sc in short]
    prompt = f"""These scenes of the series "{series_title}" are too short. Each must be spoken for about
{int(scene_duration)} seconds, which is about {want} words in {lang.upper()} (the voices speak about
{WORDS_PER_SEC.get(lang, 2.3)} words per second). Rewrite each scene's lines to about {want} words in total.
Keep its story, events, order, speakers and language exactly; add natural back-and-forth, reactions, questions,
feelings and narrator description. Speakers may only be the ones already in the scene, the Narrator, or these:
{char_desc}
Use "emotion" from calm|happy|excited|sad|scared|angry|whisper|mysterious|surprised.

SCENES:
{json.dumps(rows, ensure_ascii=False)[:12000]}
"""
    for m in ai.models() or []:
        try:
            raw = usage.studio_call(m, prompt, LENGTHEN_SCHEMA, "Studio: lengthen scenes", series_title, timeout=90,
                                    temperature=0.6)
            res = raw[0] if isinstance(raw, tuple) else raw
            longer = {int(x.get("scene_num") or 0): x.get("lines") or [] for x in (res or {}).get("scenes", [])}
            for i, sc in enumerate(scenes):
                new = [x for x in longer.get(int(sc.get("scene_num") or i + 1), []) if str(x.get("text") or "").strip()]
                if new and sum(len(str(x["text"]).split()) for x in new) > spoken_words(sc):
                    sc["lines"] = new
                    _sync_legacy_fields(sc)
            return
        except Exception as e:  # noqa: BLE001
            log.warning("lengthening scenes with %s failed: %s", m, e)


def _brief_rule(ctx: dict) -> str:
    """The creator's own concept for the series (pasted when it was created): every idea and script follows it."""
    b = str(ctx.get("brief") or "").strip()
    return f"SERIES CONCEPT FROM THE CREATOR (follow its world, characters, tone and facts):\n{b[:4000]}\n" if b else ""



def _places_rule(ctx: dict) -> str:
    """Places the series already has (Location Vault): the story reuses their exact names when it goes back there."""
    names = [n for n in (ctx.get("locations") or []) if n][:30]
    return ("KNOWN PLACES of this series (when a scene happens in one of them, use its exact name as the set's "
            "location_name): " + "; ".join(names) + "\n") if names else ""



def _kit_list() -> str:
    """Every set the 3D studio can build (studio/anim3d/sets.py), for the script writer's 'kit'."""
    from studio.anim3d import sets as _sets
    return "|".join(_sets.KITS)
