"""Theme music and sound effects (studio/soundtrack.py, studio/sfx.py), offline.

    python tests/test_sound.py

Checks every effect is made, the dialogue words that call effects (English and Hindi, without false hits),
the theme per format, the mood per scene, the effects planned from a 3D scene, the score (length, cross-fades,
dip before a scare) and the final mix with music and effects."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")
data = Path(tempfile.mkdtemp(prefix="peakcut-sound-"))
os.environ["PEAKCUT_DATA"] = str(data)

from studio import concat, formats, sfx, soundtrack  # noqa: E402


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


# ---------------------------------------------------------------- the effects
bad = [n for n in sfx.EFFECTS if (x := sfx.effect(n)) is None or len(x) < 500 or len(x) > 6 * sfx.SR or np.max(np.abs(x)) < 0.1]
check(f"all {len(sfx.EFFECTS)} effects are made, audible and short", not bad)
check("an effect sounds the same every time", np.array_equal(sfx.EFFECTS["thud"](np.random.default_rng(1)),
                                                              sfx.EFFECTS["thud"](np.random.default_rng(1))))

# ---------------------------------------------------------------- words that call effects
def names(text):
    words = [{"w": w, "s": float(i), "e": i + 0.5} for i, w in enumerate(text.split())]
    return [n for _t, n in sfx.words_to_sfx(words)]


check("'car' and 'गाड़ी' bring a car engine", names("the car") == ["car_engine"] and names("वो गाड़ी आई") == ["car_engine"])
check("'दरवाज़ा' and 'door' bring a creak", names("दरवाज़ा खोलो") == ["door_creak"] and names("open the door!") == ["door_creak"])
check("'phone', 'thunder', 'घंटी' are found", names("phone") == ["phone_ring"] and names("thunder") == ["thunder"]
      and names("घंटी बजी") == ["bell"])
check("no false hits: कारण, सरकार, बस, हवाई", names("कारण सरकार बस हवाई") == [])

# ---------------------------------------------------------------- themes and moods
h, k = soundtrack.theme_for(formats.get("horror")), soundtrack.theme_for(formats.get("kids_3d"))
check("horror has a horror theme with a scare stinger and dips", h["name"] == "horror" and h["base"] == "horror"
      and h["stings"]["surprise"] == "horror_hit" and h.get("dip"))
check("kids has a playful theme with a ta-da ending", k["base"] == "playful" and k["stings"]["end"] == "tada")
check("comedy gets boings and rimshots", soundtrack.theme_for(formats.get("comedy"))["stings"]["funny"] == "rimshot")
check("the script's episode mood wins", soundtrack.theme_for(formats.get("kids_3d"), "epic")["base"] == "epic")
scared = [{"emotion": "scared"}, {"emotion": "scared"}, {"emotion": "calm"}]
check("two scared lines make a tense scene, loud", soundtrack.scene_mood(scared, h) == ("horror", 3))
check("a sad scene gets the sad mood, soft", soundtrack.scene_mood([{"emotion": "sad"}], k) == ("emotional", 1))
check("a scene's own music wins", soundtrack.scene_mood(scared, h, "lullaby") == ("lullaby", 2))
check("no emotions: the theme's base mood", soundtrack.scene_mood([{}], k) == ("playful", 2))

# ---------------------------------------------------------------- effects planned from a 3D scene
spec = {"world": {"preset": "snow"}, "cast": [{"id": "a", "enter": {"from_x": -8, "t0": 0.0, "t1": 2.0}}, {"id": "b"}],
        "actions": [{"who": "a", "type": "jump", "t0": 5.0, "t1": 6.0}, {"who": "b", "type": "bounce", "t0": 3.0, "t1": 4.0}]}
lines = [{"speaker": "A", "text": "Who is at the door?", "emotion": "scared"},
         {"speaker": "B", "text": "Yay!", "emotion": "happy", "sfx": ["bell"]}]
spans = [(2.0, 4.0), (6.5, 7.5)]
words = [{"w": "door?", "s": 3.5, "e": 3.9}]
ev = sfx.plan_scene(spec, words, lines, spans, k, 9.0, last_scene=True)
got = [n for _t, n, _g in ev]
check("walking in on snow makes snowy footsteps", got.count("step_snow") >= 4)
check("a jump makes a whoosh and a landing", "whoosh" in got and "thud" in got
      and next(t for t, n, _ in ev if n == "thud") > next(t for t, n, _ in ev if n == "whoosh"))
check("a kids bounce pops", "pop" in got)
check("the word 'door' creaks at the word", any(n == "door_creak" and abs(t - 3.5) < 0.01 for t, n, _ in ev))
check("the script's own effect plays at its line", any(n == "bell" and abs(t - 6.5) < 0.01 for t, n, _ in ev))
check("a happy ending gets the ta-da", any(n == "tada" for n in got))
hv = [n for _t, n, _g in sfx.plan_scene(None, [], lines, spans, h, 9.0)]
check("a scared line in horror gets a heartbeat", "heartbeat" in hv)
check("documentaries have no footsteps", not any(n.startswith("step_") for _t, n, _g in
                                                    sfx.plan_scene(spec, [], [], [], soundtrack.theme_for(formats.get("history_doc")), 9.0)))
track = sfx.render_track([(1.0, "thud", 1.0), (3.0, "pop", 1.0)], 5.0)
check("the effects track is as long as the episode, with the effects at their times",
      len(track) == 5 * sfx.SR and np.max(np.abs(track[:int(0.9 * sfx.SR)])) < 1e-6
      and np.max(np.abs(track[sfx.SR:int(1.3 * sfx.SR)])) > 0.3)

# ---------------------------------------------------------------- the score
segs = [(0.0, 10.0, "calm", 2), (10.0, 20.0, "calm", 3), (20.0, 30.0, "tension", 2)]
sc = soundtrack.build_score(segs, 30.0, 7, h, dips=[25.0])
check("the score is as long as the episode", sc is not None and len(sc) == 30 * soundtrack.SR)
rms = lambda a, b: float(np.sqrt(np.mean(sc[int(a * soundtrack.SR):int(b * soundtrack.SR)] ** 2)))  # noqa: E731
check("it fades in and out", rms(0, 0.05) < rms(5, 6) and rms(29.9, 30) < rms(15, 16))
check("the music drops just before the scare", rms(24.6, 24.85) < 0.5 * rms(22, 23))
check("no gap where the mood changes", rms(19.6, 20.4) > 0.2 * rms(15, 16))

# ---------------------------------------------------------------- the final mix
vid = data / "v.mp4"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=320x180:d=6", "-f", "lavfi", "-i",
                "sine=frequency=300:duration=6", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(vid)], check=True,
               creationflags=concat.NO_WINDOW)
import soundfile  # noqa: E402
mf, ff = data / "score.wav", data / "fx.wav"
soundfile.write(str(mf), soundtrack.build_score([(0, 6, "playful", 2)], 6.0, 1, k), soundtrack.SR)
soundfile.write(str(ff), sfx.render_track([(2.0, "tada", 1.0)], 6.0), sfx.SR)
out = data / "mixed.mp4"
ok = soundtrack.mix_video(vid, out, music_file=mf, sfx_file=ff, seed=1)
dur = concat._get_duration(out)
check("the video is mixed with its score and effects", ok and abs(dur - 6.0) < 0.3)
# ---------------------------------------------------------------- each scene's background sound, and what is seen is heard
from studio import animals  # noqa: E402
beds = lambda w: [k for k, _l, _m in sfx.scene_beds(w)]  # noqa: E731
check("rain is heard when it rains", "rain" in beds({"preset": "village", "weather": "rain", "time": "morning"}))
check("a storm has rain and wind", beds({"preset": "city_street", "weather": "storm"})[:2] == ["rain", "wind"])
check("rain is muffled indoors", sfx.scene_beds({"preset": "train_interior", "weather": "rain"})[0] == ("rain", 0.85, True))
check("a train rattles, a market murmurs, a river rushes",
      "train" in beds({"preset": "train_interior"}) and beds({"preset": "bazaar"}) == ["crowd"] and beds({"preset": "ghat"}) == ["water"])
check("birds by day, crickets at night", beds({"preset": "village", "time": "morning"}) == ["birds"]
      and beds({"preset": "temple", "time": "night"}) == ["night"])
storm = {"duration": 40, "world": {"preset": "city_street", "weather": "storm"},
         "story": {"fx": [{"name": "lightning", "t0": 2.0, "t1": 4.0}, {"name": "falling_stars", "t0": 20.0, "t1": 24.0}],
                   "props": [{"name": "kite", "how": "fly", "t0": 30.0}]}}
ev = sfx.screen_sfx(storm)
check("lightning is followed by thunder", any(n == "thunder" and 2.5 < t < 3.0 for t, n, _g in ev))
check("falling stars sparkle, a kite flying in whooshes", any(n == "sparkle" and t == 20.0 for t, n, _g in ev)
      and any(n == "whoosh" and t == 30.0 for t, n, _g in ev))
inside = {"duration": 40, "world": {"preset": "train_interior", "weather": "storm"}, "story": {"fx": []}}
check("a storm outside thunders now and then while the scene is indoors",
      len([1 for _t, n, _g in sfx.screen_sfx(inside) if n == "thunder"]) >= 3)
amb = soundtrack.build_ambience([(0, 5, [("birds", 0.7, False)]), (5, 10, [("rain", 1.0, False)])], 10.0, 1)
arms = lambda a, b: float(np.sqrt(np.mean(amb[int(a * soundtrack.SR):int(b * soundtrack.SR)] ** 2)))  # noqa: E731
check("the rain starts where the rainy scene starts", arms(7, 9) > 2 * arms(2, 4) and len(amb) == 10 * soundtrack.SR)

# ---------------------------------------------------------------- animals sound like animals
check("a dog is a dog, a boy is not", animals.animal_kind({"species": "Indian street dog"}) == "dog"
      and animals.animal_kind({"species": "10-year-old boy"}) == "" and animals.animal_kind({"species": "", "visual_anchor": "brown dog"}) == "dog")
check("a dog's line of barks is barks", animals.split_line("(चिंटू को सहलाते हुए) भौं-भौं!", "dog") == ([("भौं", "dog_bark"), ("भौं", "dog_bark")], ""))
check("a growl is a growl", animals.split_line("गुर्र्र्र…", "dog")[0][0][1] == "dog_growl")
check("a talking dog barks, then talks", animals.split_line("Woof woof! चलो चिंटू!", "dog")[1] == "चलो चिंटू!")
check("a goat saying मैं (I) is talking, not bleating", animals.split_line("मैं जाऊँगा बाज़ार", "goat") == ([], "मैं जाऊँगा बाज़ार"))
check("a crow's caws, then its words", animals.split_line("काँव-काँव! राम का घर कहाँ है?", "crow")[1] == "राम का घर कहाँ है?")
check("stage directions are never read aloud", animals.stage_free("(धीरे से) चलो [laughs] अब") == "चलो अब")
clip, marks = animals.noise_clip([("भौं", "dog_bark"), ("भौं", "dog_bark")])
check("two barks, each with its time", len(marks) == 2 and marks[1][1] > marks[0][2] and len(clip) > 0.4 * sfx.SR)
check("every animal sound is made", all(sfx.effect(n) is not None and float(np.max(np.abs(sfx.effect(n)))) > 0.3 for n in
      ["dog_bark", "dog_growl", "cat_meow", "cow_moo", "lion_roar", "duck_quack", "goat_baa", "horse_neigh",
       "elephant_trumpet", "crow_caw", "rooster", "frog_croak", "wolf_howl", "snake_hiss", "monkey", "pig_oink", "owl_hoot", "donkey"]))
check("a narrator saying the dog barked makes it bark", [n for _t, n in sfx.words_to_sfx([{"w": "भौंका", "s": 1.0}])] == ["dog_bark"])
check("an animal's own noise is not doubled by the word reader", sfx.words_to_sfx([{"w": "भौंक", "s": 1.0, "fx": True}]) == [])
print("ALL PASS")
