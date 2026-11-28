# Engineering Plan 12 — Sets and Environments That Fit Every Scene

> **Plan ID**: `PLAN-12`
> **Status**: **Built**: P1-P5 (understanding, 46 set kits, beauty pass, Location Vault, culture and era dressing). Waiting for the owner's check on real episodes
> **Builds on**: Plan 09 (3D runtime, Director), Plan 11 (story visuals, sound), Plan 10 (progress)
> **Modules**: `studio/anim3d/sets.py` (new), `studio/anim3d/director.py`, `web/studio3d/sets/` (new kits),
> `web/studio3d/runtime.js`, `studio/storyteller.py`, `studio/memory.py`, `web/index.html`
> **Estimated effort**: about 3 weeks in 5 phases; each phase ships on its own.

---

## 1. The problem (measured)

The 3D background of a scene is picked from **10 fixed worlds** by keywords in the scene's setting
(`director.WORLD_RULES`). Anything without a keyword falls back to an autumn forest:

| Scene setting | World used today |
|---|---|
| ancient architecture | autumn forest |
| temple courtyard at dawn | autumn forest (and "dawn" is ignored: plain day) |
| royal palace hall | autumn forest |
| railway station, hospital, cave, desert, underwater | autumn forest |
| river ghat with diyas | autumn forest |
| mountain evening | forest at sunset (no mountain) |
| busy city street | a village |

Each world is also always laid out the same way, lit with one of 5 moods, with no weather, era or culture, and a
place that comes back in a later scene or episode is not the same place.

## 2. Goal

Every scene's background should **look like the place the story says**, at the **right time and weather**, in the
**right culture and era**, be **beautiful** (depth, light, atmosphere) and **relatable** (things the audience knows
from their own life: a chai stall and rickshaws in an Indian street, diyas on a ghat, a school with a blackboard),
and a **place that returns is recognisably the same place**.

## 3. How a scene's set is decided

**3.1 The script writer describes the set**, as structured fields on every scene (one AI call, no extra wait):

```json
"set": {"place": "temple courtyard", "kit": "temple", "era": "ancient", "culture": "indian",
        "time": "dawn", "weather": "mist", "mood": "serene",
        "landmarks": ["stone shikhara tower", "bronze bell", "oil lamps"], "location_name": "Somnath Mandir"}
```

**3.2 Without it** (old scripts, no AI): a much larger word reader (English, Hinglish, Hindi) for places, times
(dawn, morning, noon, golden hour, dusk, night, midnight), weather (clear, clouds, overcast, rain, fog, storm, snow)
and eras.

**3.3 Locations remember themselves.** A **Location Vault** per series (like the Character Vault): "Dadi's house",
"Lord's", "the old temple". The first time a place appears, its layout, colours and landmarks are saved; every later
scene or episode at that place rebuilds it the same way (with today's time and weather).

## 4. The set library (from 10 worlds to about 40 kits)

Each **kit** is built from parts (ground, backdrop, buildings, props, sky, lights) with parameters, so one kit gives
many different places (a small village temple vs a grand ancient one, a modern vs an old station).

| Family | Kits |
|---|---|
| Nature | forest, jungle, meadow/field, river bank, lake, waterfall, mountain pass, hill top, desert, cave, beach, island, snow land, garden |
| Indian & cultural | temple, palace/fort, ancient ruins, ghat with steps, bazaar/market, village chowk, haveli courtyard, farm & fields, mela/fair |
| Urban | city street, highway & roadside dhaba, railway station, bus stop, school yard, classroom, hospital, office, shop, café, rooftop |
| Homes | living room, kitchen, bedroom, attic, verandah, courtyard |
| Special | stadium (done), stage/auditorium, space station, planet surface, underwater, castle, haunted house, graveyard, lab |

**Culture and market** change the dressing: an Indian street gets rickshaws, a chai stall, signboards, power lines
and rangoli; a US street gets mailboxes, fire hydrants and lawns; a Japanese one lanterns and vending machines.
**Era** swaps modern pieces for ancient ones (oil lamps for street lights, bullock carts for cars).

## 5. Beautiful: light, sky, depth, atmosphere

- **Time of day as a continuum** (sun position and colour, sky gradient, shadow length), not 5 fixed moods.
- **A real sky**: clouds, sun or moon disc, stars, and a painted far horizon (mountains, city skyline, sea) for depth.
- **Weather**: rain with puddles and wet shine, fog layers, storm clouds with lightning, snowfall, wind in trees.
- **Practical lights** that belong to the place: diyas, torches, street lamps, lit windows, neon, campfire, with a
  soft glow (bloom).
- **Depth layers**: foreground details framing the shot, the cast area kept clear in the middle, landmarks in the
  background of the establishing shot; atmospheric haze grows with distance.
- **Better shapes and materials**: more tree types, buildings with doors, windows, roofs, steps; temple towers,
  domes and arches; stone, brick, wood, metal looks; soft contact shadows.
- **Per-format grading** stays (horror darker and colder, kids brighter), applied on top.

## 6. Fits the story moment

- The establishing shot of each new place shows its landmark; the Director frames the cast against it.
- The set reacts to the story: an evening scene gets lamps lit; a storm scene gets wet ground; a festival scene gets
  lights and garlands; a scene "after the fire" can be damaged (later).
- Things the lines name (Plan 11 story visuals) are placed in the set naturally (a car on the road, not on grass).

## 7. In the app

- **Location Vault** tab: every place of the series with a picture, its name, kit, era and culture; rename, re-roll
  the layout ("New layout"), or fix it.
- **Script editor**: each scene shows a set chip ("🛕 Temple courtyard · dawn · mist") that can be changed.
- **Quick preview**: a still of a scene's set and cast in a few seconds before rendering the whole episode.

## 8. Phases

| Phase | What ships | Effort |
|---|---|---|
| **P1 Understanding** | the script writer's `set` fields; the big word reader (places, time, weather, era, culture, EN/HI); time-of-day and weather lighting; real sky with clouds/sun/moon/horizon | 3–4 days |
| **P2 Kits, part 1** | 15 most-needed kits: temple, palace/fort, ruins, ghat, bazaar, city street, highway/dhaba, station, school/classroom, hospital, home rooms, mountain, desert, river, cave | 5–6 days |
| **P3 Beauty pass** | depth layers, haze, practical lights with glow, better trees/buildings/materials, weather effects | 4 days |
| **P4 Location Vault** | places remembered per series (same layout every time), Location Vault tab, set chips in the script editor, quick preview | 3–4 days |
| **P5 Kits, part 2** | the remaining ~20 kits, culture dressings (India, US, Japan, UK), era swaps | 4–5 days |

Rendering stays on this laptop; each kit is tested to keep the frame rate (instanced repeats, simple far shapes).

## 8b. Built so far

- P1: `studio/anim3d/sets.py` reads place, time (dawn, morning, noon, golden, dusk, night, midnight), weather (clear,
  overcast, rain, storm, fog, snow), era and culture from the script writer's `set` on every scene, else from words in
  English, Hinglish and Hindi; horror stays dark and often misty; a named place (`location_name`) keeps its layout.
  `web/studio3d/sets.js`: light and sky colours by time of day, weather that greys the sky and dims the light, fog
  layers, clouds, sun disc and halo at dawn/dusk, moon and stars at night; rain, snow and storms over the whole scene.
- P2: 16 set kits: temple, palace/fort, ruins, ghat, bazaar, city street, highway dhaba, railway station, classroom,
  hospital ward, kitchen, bedroom, mountain pass, desert, river bank, cave (plus the earlier stadium and worlds).
- P3 beauty pass: every flame and lamp glows (soft halo); ground patches; far hills and bushes around nature sets; a
  city skyline behind street sets; clouds, sun halo, moon and stars.
- P4 Location Vault: every place an episode uses is saved once in the series (`locations` in series.json: name, set,
  era, culture, layout seed, landmarks). Later scenes and episodes rebuild it the same way; the script writer is told
  the known places and reuses their names. The series studio has a **📍 Locations** tab (picture of each place;
  rename, change set/era/culture, "New layout"); a renamed place is still found by its old name. In the script
  editor each scene has set chips (place, time of day, weather; "Auto" reads the setting) and a **👁 Preview**
  button that makes a still of the scene's set and cast in a few seconds, with no voices made.
  Routes: `GET /api/series/{id}/locations`, `GET .../locations/{lid}/image.jpg`, `POST .../locations/{lid}`,
  `POST /api/series/{id}/preview-scene`.
- P5: 22 more kits (train interior, office, cafe, library, lab, rooftop, playground, garden, lake, waterfall, jungle,
  fields, haveli, mela, stage, space station, alien planet, underwater, castle, haunted house, graveyard, bus stop):
  46 in all. Culture dressing (Japanese lanterns; Western mailbox and hydrant; Indian electric poles) and era swaps
  (ancient: torches; future: neon).
- Tests: `tests/test_sets.py` (settings that used to become a forest, time, weather, era, culture, horror, the
  script's set, named places, the Location Vault and its routes, the scene preview, all 46 sets rendered by day and
  on a rainy night).
- Not built: UK-specific dressing (Western is used); frame-time budget per kit not measured separately.

## 9. Tests

- Every kit builds and renders on its own and with a cast (no overlap with the cast area).
- The scene settings in section 1 all get the right kit, time and weather.
- A named place rebuilds identically in a later scene and episode.
- Frame-time budget per kit on this laptop.

## 10. Decisions for the owner

1. Start with P1 + P2 together (biggest visible change), or P1 alone first?
2. Which places matter most for your channels (to build first in P2)?
3. Should the quick preview (P4) come earlier?
