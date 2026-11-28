# Engineering Plan 10 — Episode Production Progress (what is happening, how long it takes)

> **Plan ID**: `PLAN-10`
> **Status**: **Built, in testing** (live test by the owner pending)
> **Builds on**: Plan 08 (production engine), Plan 09 (3D renderer)
> **Modules**: `studio/progress.py` (new), `studio/production.py`, `studio/series.py`, `studio/concat.py`,
> `studio/soundtrack.py`, `studio/memory.py`, `studio/server.py`, `web/index.html`, `tests/test_progress.py`

---

## 1. The problem

While an episode was being made, the screen showed one number and one line:

- The percentage moved only when a new scene started (8% → 21% → 34%…) and then stood still for 4+ minutes.
- The line read "Scene 1: animating frame 915/915 (about 0m 0s left)" and stayed there through the slow steps
  after the animation (grade, captions and voice; joining; music; the short), which reported nothing.
- No scene count, no list of what is done or next, no total time left, no timer.
- It lived only on the page where Approve was pressed: a reload or coming back later showed nothing.

A real Horror episode (6 scenes, 3 min 45 s) took 25 minutes, more than half of it with no visible progress.
The Horror film grain made every scene 200–240 MB and the episode 1.3 GB.

## 2. What the user sees now

**Production panel** (Script tab):

```
MAKING THE EPISODE                                  44%      2m 12s      2m 37s
Episode 3 · Bhalu ka Jadui Pul                      DONE     ELAPSED     TIME LEFT
Scene 2 of 3 · 1 finished
[█████████████████░░░░░░░░░░░░░░░░░░░░░]
Now: Scene 2 of 3: Animating 3D · frame 61 / 147                 for 26s · 41%
[█████████░░░░░░░░░░░]

✅ Scene 1   jungle mein nadi ka kinara · 10s   Finished          1m 57s   ▶
🎬 Scene 2   village, sunset · 6s               Animating 3D 61/147   26s
○  Scene 3   forest at night · 5s               Waiting
○  Final     Joining the scenes                  Waiting
○  Final     Adding music and ambience           Waiting
○  Final     Cutting the 9:16 short              Waiting
```

- **Timers**: elapsed (whole episode) and time left tick every second; the current step shows how long it has been
  running; each finished scene and final step shows how long it took. They count from the server's clock, so a
  reload does not reset them.
- **Every step reports**: voices, every frame of the 3D animation, and (through ffmpeg's own progress output) the
  finishing pass of each scene, joining the scenes, the music mix and the short.
- **▶ on a finished scene** plays it while the rest of the episode is still being made.
- **Other tabs**: a slim banner (Episode 3 · 44% · what is happening · elapsed · left · Open).
- **Sidebar**: the AI Series Studio badge shows the percentage; its tooltip says what is happening.
- **When done**: "Episode 3 is ready! Made in 4m 46s"; the finished card and the episode list show "Rendered in".
- **After a reload or a restart**: the page asks the server for running productions and shows the panel again.
  A production stopped by closing PeakCut shows "Stopped part-way" with **Resume production** (the approved script
  is saved; finished scenes are reused from the scene cache).
- Background refreshes no longer rebuild the studio while audio or video is playing on it (this was also what
  cut off the Director's Narrative mid-sentence).

## 3. How it works

- `studio/progress.py` `Tracker`: every scene is a piece of work weighted by its length (voice 6%, animation or
  pictures 62%, finishing 32%); the final steps are the last 10% (join 25%, music 15%, short 60% of that).
  Reused scenes count as done at once and are left out of the speed.
- **Time left** = this episode's own speed once 4% of the new work is done and 20 s have passed; before that, the
  speed remembered from the last episodes on this machine (`render_speed.json` in the data folder).
- The full status goes to `on_status` (series engine → `GET /api/series/{sid}/episodes/{n}/status`) and to
  `episodes/ep_NNN/progress.json` once a second.
- `progress.ffmpeg()` runs ffmpeg with `-progress pipe:1` and turns `out_time` into a fraction.
- New routes: `GET /api/series/{sid}/productions`, `POST /api/series/{sid}/episodes/{n}/resume`,
  `GET /api/series/{sid}/episodes/{n}/scene/{idx}` (a finished scene).
- The episode record keeps `render_seconds` and `render_steps` (time per scene and per final step).

## 4. Speed fixes done with it

| Change | Measured |
|---|---|
| On 3D, the grade's `colorbalance` (RGB round trip, most of the finishing time) is replaced by the same tint as a `lutyuv` shift of the colour channels | Horror finishing of 15 s: **78 s → 23 s** |
| On 3D, film grain a third as strong | (part of the line above) |
| Bitrate cap 8 Mbit/s on scenes, joins and shorts | Horror 15 s: **82 MB → 4.8 MB** |
| 3D keeps its 24 fps (no conversion to 30) | fewer frames to grade and encode |

`ENGINE_VERSION` went to 4, so scenes made before are made again once.

## 5. Tests

`tests/test_progress.py` (offline): longer scenes weigh more; the status names the scene, the count and the frame;
the percentage never goes backwards; times per scene and step; reused scenes; the status file; the remembered
speed; ffmpeg progress; a whole episode through the series engine (every scene reports voice, pictures and
finishing; the final steps report while running; a time-left estimate exists; render time is kept on the episode);
a production stopped by a restart is reported with resume. Also checked live in a real browser with a real 3D
episode: found after opening the page, timers tick, survives a reload, banner on other tabs, scene preview plays,
finished card and toast, no page errors.

## 6. Later

- Cancel button (stop a production cleanly).
- Per-format speed memory (Horror vs Kids) once there are enough runs.
- Queue view when several episodes are approved one after another.
