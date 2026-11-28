# Engineering Plan 11 — Theme Music, Sound Effects and Story Visuals ("talk about a car, see a car")

> **Plan ID**: `PLAN-11`
> **Status**: **In Development**: P1 (theme music), P3 (sound effects) and P4 (story visuals) are built; P2 and P5 to do
> **Builds on**: Plan 08 (soundtrack, formats), Plan 09 (3D runtime and Director), Plan 10 (progress)
> **Modules**: `studio/soundtrack.py`, `studio/sfx.py` (new), `studio/anim3d/director.py`, `studio/anim3d/props.py`
> (new), `web/studio3d/runtime.js`, `web/studio3d/props/` (new), `studio/storyteller.py`, `studio/formats.py`,
> `web/index.html`
> **Estimated effort**: about 3 weeks in 5 phases; each phase ships on its own.

---

## 1. Goal

Episodes should feel produced, not just animated:

1. **Music that fits the theme and the moment**: horror sounds like horror (drones, heartbeat, silence, stingers),
   comedy like comedy (pizzicato, boings), kids like kids (ukulele, xylophone), and the music changes with the
   scene instead of one loop for the whole episode.
2. **Sound effects**: footsteps when someone walks, a door creak, a car engine, a laugh track for comedy.
3. **Story visuals**: when a character talks about something, the viewer **sees it**: say "car" and a car drives
   into the scene, or appears in a thought bubble, or the camera cuts to it, at the exact word.

## 2. Where we are today

| Part | Today |
|---|---|
| Music | One synthesised loop per episode from 13 moods (`soundtrack.MOODS`), or your own tracks from `data/music/<mood>/`. Ducked under speech, -14 LUFS. |
| Ambience | 4 synthesised beds (rain, wind, night, hum). |
| Sound effects | None. |
| Things mentioned in dialogue | Not shown. The 3D set is chosen from the scene's place only (forest, village, room…). |

## 3. Music by theme and by scene

**3.1 A music cue per scene.** The script writer gives each scene a cue: `{"mood": "tension", "level": 1-3,
"sting_at": "line 3", "end": "hit|fade|cut"}`. Scenes cross-fade into each other's music; a big moment gets a
stinger (horror hit, comedy "boing", kids "ta-da"); a dramatic beat can drop to silence. Without a cue, the format
picks one from the line emotions (scared → tension, happy → playful…).

**3.2 A theme per format** (in `studio/formats.py`): instrument palette, tempo range, stinger set, how much silence.

| Format family | Palette | Stingers |
|---|---|---|
| Horror / thriller | low drones, heartbeat, reversed swells, sparse piano | sudden hit, whisper swell, silence before a reveal |
| Comedy | pizzicato strings, bassoon, bouncy bass | boing, slide whistle, rimshot, laugh |
| Kids | ukulele, xylophone, claps, glockenspiel | ta-da, sparkle, pop |
| Documentary / history | piano, strings, soft percussion | low boom for a fact |
| Anime / action | driving drums, synth strings | whoosh, impact |
| Motivational | rising piano and strings, big drums | swell to the last line |

**3.3 A series theme tune**: a short intro/outro motif stored on the series, same in every episode (continuity).

**3.4 Where the music comes from** (free first, in this order):

1. **Your own tracks** in `data/music/<mood>/` (already supported).
2. **A free music pack** downloaded on first use, sorted by mood: tracks under licences that allow use in videos
   (CC0, or CC BY with the credit added to the video description automatically, e.g. Kevin MacLeod's
   incompetech library). Each track's licence is checked and recorded before it goes in the pack.
3. **A better built-in synth**: more instruments, a melody layer, and variations per episode so two episodes
   never sound the same (today's loops are simple).
4. *Optional, off by default:* local AI music (e.g. MusicGen small on the CPU). It is slow on this laptop, and its
   model weights are non-commercial, so it is only for personal use. Better done on free Colab if at all.

## 4. Sound effects

`studio/sfx.py`: a library of short effects by name (footsteps-grass, footsteps-wood, door-creak, car-engine,
car-horn, phone-ring, wind-gust, thunder, laugh, gasp, whoosh, pop, boing…), from a CC0 effects pack plus
synthesised simple ones (whoosh, pop, boing, heartbeat). Effects are placed on the timeline by:

- **the Director's actions** (walk-in → footsteps on the set's ground, jump → whoosh + land, wave → none);
- **the things shown** (a car arriving brings its engine; see §5);
- **the script** (`"sfx": ["door-creak@line2"]`);
- **the format** (comedy laugh after a punchline; horror heartbeat under a scared line).

They are mixed under the dialogue in the same pass as the music, so there is no extra encode.

## 5. Story visuals: see what is talked about

**5.1 What to show, and when.** The script writer adds to any line: `"show": [{"thing": "car", "how": "enter"}]`.
Without it, a keyword spotter (English and Hindi, e.g. car/gaadi/गाड़ी, phone/फ़ोन, ball/गेंद, cake/केक, moon/चाँद,
house/घर, letter/चिट्ठी…) finds things in the line. The word timings we already have place the moment exactly on the
word.

**5.2 Four ways to show it** (the Director picks; the script can choose):

| How | When it fits | Example |
|---|---|---|
| **enter**: the thing appears in the set | it is here, now | "Look, a car!" → a car drives in from the side and stops |
| **bubble**: a thought bubble over the speaker | memories, wishes, things far away | "Papa's old car…" → bubble with a small car |
| **insert**: the camera cuts to it for 1–2 s | important objects, clues | "the key!" → close-up of a key on the ground |
| **card**: an animated picture card with the word | explainers, documentaries, facts | "The Taj Mahal was built in 1632" → card with a picture and the year |

**5.3 The props.** A library of ~100 everyday things that fit the cartoon look:

- **Built in code** in `runtime.js`, like the characters (cheap, any colour): ball, box, book, phone, cup, cake,
  lantern, key, letter, moon, star, sign, simple cars and bikes, house, boat…
- **Free 3D models (CC0)** for richer things: vehicles, furniture, food, city and nature kits (e.g. Kenney and
  Quaternius packs, both CC0), loaded as `.glb` by Three.js. A model is used only after its licence is checked;
  the list of models and licences is kept in `web/studio3d/props/LICENSES.md`.
- Each prop has: how it enters (drive, drop, pop, float, fade), where it goes (ground, hand, sky), its sound
  (car → engine), and Hindi and English words that call it.

**5.4 Kinetic captions**: the spoken keyword is highlighted in the caption with its small icon, which helps the
"talking to the viewer" feel of explainer and kids videos.

## 6. In the app

- Script editor: each line shows chips for what will be shown and heard ("🚗 car · drives in", "🔊 horn"),
  editable; each scene shows its music cue ("🎵 tension, ends with a hit").
- A quick preview of one scene (Three.js) before rendering the whole episode.
- The progress panel (Plan 10) gets a line for "Adding sound effects" if it becomes its own pass.

## 7. Phases

| Phase | What ships | Effort |
|---|---|---|
| **P1 Music by scene** | per-scene cues, cross-fades, stingers, format themes, series theme tune, better synth | 4–5 days |
| **P2 Free music pack** | mood-sorted free tracks downloaded on first use, licence check, credits in the description | 2 days |
| **P3 Sound effects** | `sfx.py`, CC0 pack + synthesised effects, placed by actions, script and format | 3 days |
| **P4 Story visuals** | keyword spotter (EN/HI), ~40 built-in props, enter/bubble/insert, prop sounds | 5–6 days |
| **P5 More props + cards** | CC0 `.glb` packs, info cards, kinetic captions, script-editor chips, scene preview | 4 days |

## 7b. Built so far

- **P1 theme music** (`studio/soundtrack.py`): `THEMES` (kids, comedy, bedtime, horror, thriller, noir, epic, scifi,
  retro, doc, drama, motivation) chosen per format; `scene_mood()` picks each scene's mood and loudness from its lines'
  emotions (or the script's scene `music`); `build_score()` makes one track for the episode: cross-fades on mood
  changes, the same mood continues without restarting, fade in/out, a five-note series tune at the start (same in
  every episode of a series), and a dip to near silence before a horror/thriller scare.
- **P3 sound effects** (`studio/sfx.py`): 25 effects synthesised locally (footsteps on grass/wood/snow/sand, whoosh,
  thud, pop, boing, slide whistle, ta-da, sparkle, heartbeat, horror hit, whisper swell, door creak, knock, car
  engine, car horn, phone ring, bell, thunder, wind gust, clock tick, bird, rimshot). Your own file in
  `data/music/sfx/<name>.*` replaces any of them. Placed from the 3D scene (walk-ins, jumps, bounces), from words in
  the dialogue (English and Hindi, at the word, with no false hits on कारण/सरकार/बस), from the script (`sfx` on a
  line) and from the theme (heartbeat on a scared line, horror hit or boing on a surprise, rimshot after a funny
  line, ta-da at a happy ending).
- Mixed in the existing single audio pass (music ducked under speech, effects not ducked, -14 LUFS).
- The script writer can now set `music` per scene and `sfx` per line.
- Not done: the free music pack (P2): the music is still the built-in synth unless you add your own tracks to
  `data/music/<mood>/`. A synthesised laugh track was left out: it would sound fake.
- Tests: `tests/test_sound.py`.

- **P4 story visuals** (`studio/anim3d/story.py`, `director.py` `_story()`, `web/studio3d/story.js`): words in the
  narration and dialogue (English, Hinglish, Hindi) become things and happenings on screen at the word:
  13 happenings (falling stars, starry sky, rain, snowfall, lightning, fireworks, rainbow, moon, sun, birds,
  butterflies, magic sparkles, wind) and 33 things (car, bicycle, ball, cake, gift, box, treasure chest, book,
  letter, map, key, phone, clock, lantern, candle, campfire, flowers, apple, mango, laddoos, honey, ice cream, egg,
  umbrella, drum, crown, kite, balloons, glowing orb, bell, boat, rocket, ghost). Things drive, drop, pop, float or
  fly in on the outer side of whoever names them; memories and wishes ("याद है…", "काश…") show in a thought bubble.
  The camera cuts to a sky shot or a close-up at the word, the characters look at it (faces lifted to the sky) and
  listeners react with surprise. At most 3 things and 2 happenings per scene. The script writer can ask with a
  line's `show`. Tests: `tests/test_story.py`.
- Voices: a voice that does not exist (e.g. `hi-IN-NeerjaNeural`) is replaced by a real one of the same language
  and gender; when the voice service cannot be reached, the production stops at once with Resume instead of
  making silent scenes.
- Each scene's background sound comes from its own place, time and weather (`sfx.scene_beds`,
  `soundtrack.build_ambience`). The sounds fade from scene to scene, and each kind has a set loudness (about 12 dB
  under the voice). They are:
  - rain, muffled when indoors, and wind in storms, snow and fog;
  - water by rivers, the sea and waterfalls;
  - a murmuring crowd in markets and stations, traffic on roads, the rattle of a train inside a train;
  - a low hum in space and labs;
  - birds by day and crickets at night outdoors.
- What is seen is heard (`sfx.screen_sfx`):
  - lightning is followed by thunder, and storms flash every 9–14 s;
  - a storm outside thunders while the scene is indoors;
  - falling stars and sparkles sparkle, fireworks bang, birds chirp;
  - things that fly in whoosh, pop up with a pop, drop with a thud, or drive in with an engine.
- Animals sound like animals (`studio/animals.py`). An animal character's noises in its line ("भौं-भौं!",
  "म्याऊँ", "गुर्र्र") play as its real sound: 20 made sounds, from the dog's bark, growl and whine to the owl and
  the donkey. A recording in `data/music/sfx/<name>.wav` replaces any of them.
  - The mouth moves with each sound, and a talking animal makes its sound, then speaks.
  - Words like "भौंका" or "roared" in other lines make the sound too.
  - Stage directions in brackets "(…)" are no longer read aloud by anyone.
- Places named in a line are shown (`story.PLACES`, 17 places: temple, haveli, palace or fort, castle, mountain,
  river, lake, waterfall, school, hospital, train, tree, well, hut, tower, bridge, cave; Hindi and English). At most
  2 per scene:
  - **In that very place** (a temple named in the temple), the camera turns to its main building or view
    (`sets.FOCUS`), everyone looks, and the speaker points.
  - **Elsewhere, outdoors**, the place rises into view in the distance, bigger so it stands over the roofs, with a
    high shot over the treetops. It stays in the background for the rest of the scene.
  - **Indoors, by water, or when remembered**, it appears in the speaker's thought bubble.
- The script writer is given all 47 sets. A general set an older script chose ("station" for a train compartment,
  "ruins" for a haveli) gives way to the place its words name, unless the owner fixed the place in the Location Vault.

## 8. Decisions for the owner

1. Music source: free pack with automatic credits in the description (recommended), built-in synth only, or both?
2. Comedy laugh track: on by default for Comedy, or off?
3. Start with P1 (music) or P4 (story visuals)?
