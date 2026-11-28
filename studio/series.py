"""Series Production Orchestrator for PeakCut/Clipper.
Coordinates background rendering of approved episodic scripts:
synthesizes character audio, renders 3D parallax visuals, applies subtitles,
and stitches complete 16:9 Long Videos and 9:16 Shorts.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from studio import config, formats, memory, production, visuals
from studio import progress as prog

log = logging.getLogger("peakcut.series")

_active_tasks: dict[str, dict] = {}  # f"{sid}:{ep_num}" -> {"status", "progress", "error"}


def _ep_dir(series_id: str, ep_num: int) -> Path:
    return config.DATA_DIR / "series" / series_id / "episodes" / f"ep_{ep_num:03d}"


def get_production_status(series_id: str, ep_num: int) -> dict:
    key = f"{series_id}:{ep_num}"
    if key in _active_tasks:
        return {**_active_tasks[key], "now": time.time()}
    ep = memory.get_episode(series_id, ep_num)
    if ep:
        failed = ep.get("status") == "failed"
        return {"status": ep.get("status", "draft"), "progress": 100 if ep.get("status") == "completed" else 0,
                "render_seconds": ep.get("render_seconds"),
                "can_resume": failed and (_ep_dir(series_id, ep_num) / "script.json").is_file()}
    # not running here and not finished: a production that was stopped when PeakCut closed
    saved = prog.read_file(_ep_dir(series_id, ep_num))
    if saved and saved.get("status") == "rendering":
        return {**saved, "status": "interrupted", "now": time.time(),
                "can_resume": (_ep_dir(series_id, ep_num) / "script.json").is_file(),
                "message": "Stopped when PeakCut was closed. Resume to carry on: finished scenes are kept."}
    return {"status": "not_found", "progress": 0}


def list_productions(series_id: str) -> list[dict]:
    """Episodes of this series being made right now, or stopped part-way (so the page can show them after a
    reload or a restart)."""
    out = []
    for key, st in list(_active_tasks.items()):
        sid, _, n = key.rpartition(":")
        if sid == series_id and st.get("status") == "rendering":
            out.append({**st, "ep_num": int(n), "now": time.time()})
    running = {o["ep_num"] for o in out}
    root = config.DATA_DIR / "series" / series_id / "episodes"
    if root.is_dir():
        for d in sorted(root.glob("ep_*")):
            try:
                n = int(d.name[3:])
            except ValueError:
                continue
            if n in running:
                continue
            st = get_production_status(series_id, n)
            if st.get("status") == "interrupted":
                out.append({**st, "ep_num": n})
    return out


def _design(character: dict, series: dict) -> None:
    """The AI designer gives a new character its 3D look; without an AI the word rules do it at render time."""
    try:
        from studio import concepts
        concepts.attach_designs([character], formats.resolve(series))
    except Exception as e:  # noqa: BLE001
        log.warning("character design failed: %s", e)


def _run_episode_pipeline(series_id: str, ep_num: int, script: dict):
    key = f"{series_id}:{ep_num}"
    started = time.time()
    _active_tasks[key] = {"status": "rendering", "progress": 0, "percent": 0, "message": "Getting the cast ready",
                          "started_at": started, "elapsed": 0, "ep_num": ep_num, "title": script.get("title", ""),
                          "scene_count": len(script.get("scenes", []) or []), "scenes_done": 0,
                          "step": {"label": "Getting the cast ready", "frac": 0, "since": started}}
    
    series = memory.get_series(series_id)
    if not series:
        _active_tasks[key] = {"status": "failed", "error": "Series not found"}
        return

    ep_dir = config.DATA_DIR / "series" / series_id / "episodes" / f"ep_{ep_num:03d}"
    ep_dir.mkdir(parents=True, exist_ok=True)
    scenes = script.get("scenes", [])
    if not scenes:
        _active_tasks[key] = {"status": "failed", "error": "No scenes in script"}
        return

    # Auto-discover and register any new characters introduced in this episode
    existing_char_names = {c.get("name", "").strip().lower() for c in series.get("characters", [])}
    series_style = series.get("visual_style", "high-gloss 3D Pixar toy CGI")

    # 1. Check pitch new_character
    pitch_or_idea = script.get("pitch") or {}
    if isinstance(pitch_or_idea, dict) and pitch_or_idea.get("new_character"):
        nc = pitch_or_idea["new_character"]
        nc_name = nc.get("name", "").strip().lower()
        if nc_name and nc_name not in existing_char_names:
            _design(nc, series)
            memory.add_character(series_id, nc)
            try:
                visuals.generate_character_avatar(series_id, nc, series_style)
            except Exception as ce:
                log.warning("Could not generate avatar for pitch character %s: %s", nc_name, ce)
            existing_char_names.add(nc_name)

    # 2. Check script new_characters
    for nc in script.get("new_characters", []):
        nc_name = nc.get("name", "").strip().lower()
        if nc_name and nc_name not in existing_char_names:
            _design(nc, series)
            memory.add_character(series_id, nc)
            try:
                visuals.generate_character_avatar(series_id, nc, series_style)
            except Exception as ce:
                log.warning("Could not generate avatar for script character %s: %s", nc_name, ce)
            existing_char_names.add(nc_name)

    # 3. Anyone who speaks or appears in a scene but is not in the vault yet gets a profile (look in the
    #    series' style, a voice in its language that differs from the voices already taken)
    fmt = formats.resolve(series)
    lang = (series.get("default_language") or "en").lower()
    from studio import tts
    taken = {c.get("voice_id") for c in series.get("characters", [])}
    for sc in scenes:
        names = ([sc.get("speaker", "")] + [ln.get("speaker", "") for ln in sc.get("lines", []) or []]
                 + list(sc.get("characters", []) or []))
        voice_hint = {ln.get("speaker", "").strip().lower(): ln.get("voice_id") for ln in sc.get("lines", []) or []}
        for name in names:
            name = (name or "").strip()
            if not name or name.lower() in ("narrator", "") or name.lower() in existing_char_names:
                continue
            used = [{"voice_id": c.get("voice_id"), "voice_rate": c.get("voice_rate", "+0%"),
                     "voice_pitch": c.get("voice_pitch", "+0Hz")} for c in (memory.get_series(series_id) or series).get("characters", [])]
            used.append({"voice_id": formats.narrator_voice(fmt, lang), "voice_rate": "+0%", "voice_pitch": "+0Hz"})
            cast = tts.cast_voice(lang, name, used)
            hint = voice_hint.get(name.lower())
            if hint and tts.usable_voice(hint) == hint:   # only a voice that exists (an AI may invent one)
                cast["voice_id"] = hint
            new_c = {
                "id": memory._slugify(name),
                "name": name,
                "species": "Character",
                "visual_anchor": f"{name}, distinctive consistent look, {fmt['visual']['style'][:80]}",
                **cast,
                "personality": "Introduced in this episode"
            }
            _design(new_c, series)
            memory.add_character(series_id, new_c)
            try:
                visuals.generate_character_avatar(series_id, new_c, series_style)
            except Exception as ce:
                log.warning("Could not generate avatar for %s: %s", name, ce)
            existing_char_names.add(name.lower())

    # Ensure all existing series characters have an avatar on disk
    series = memory.get_series(series_id) or series
    for c in series.get("characters", []):
        cid = c.get("id") or memory._slugify(c.get("name", "character"))
        c_avatar = config.DATA_DIR / "series" / series_id / "characters" / f"{cid}.jpg"
        if not c_avatar.is_file():
            try:
                visuals.generate_character_avatar(series_id, c, series_style)
            except Exception as ce:
                log.warning("Could not generate missing avatar for %s: %s", cid, ce)

    # Produce: voices, shots, motion, grade, captions, stitching, music, short (studio/production.py)
    series = memory.get_series(series_id) or series

    def on_status(st):
        if st.get("status") == "rendering":
            _active_tasks[key] = st

    try:
        res = production.build_episode(series, ep_num, script, ep_dir, on_status=on_status, started_at=started)
    except Exception as e:  # noqa: BLE001
        log.exception("Episode %s:%s production failed", series_id, ep_num)
        res = {"ok": False, "error": str(e)}
    ok = bool(res.get("ok"))
    master_video = res.get("master") or (ep_dir / f"episode_{ep_num:03d}_master.mp4")
    teaser_short = res.get("short") or (ep_dir / f"episode_{ep_num:03d}_short.mp4")
    saved_scenes = [{k: v for k, v in sc.items() if k != "cast"} for sc in (res.get("scenes") or scenes)]

    # Finalize Episode Record
    total_dur = float(res.get("duration") or 0.0)
    took = round(time.time() - started, 1)
    pr = res.get("progress") or {}
    ep_data = {
        "episode_num": ep_num,
        "title": script.get("title", f"Episode {ep_num}"),
        "summary": script.get("synopsis", ""),
        "unresolved_hook": script.get("unresolved_hook", ""),
        "narrative_walkthrough": script.get("narrative_walkthrough"),
        "featured_characters": sorted({ln.get("speaker") for sc in saved_scenes for ln in sc.get("lines", [])
                                       if ln.get("speaker") and ln.get("speaker").lower() != "narrator"}),
        "status": "completed" if ok else "failed",
        "script": saved_scenes,
        "format": res.get("format", series.get("format", "")),
        "duration": round(total_dur, 2),
        "video_file": str(master_video.relative_to(config.DATA_DIR)) if ok and master_video.is_file() else "",
        "short_file": str(teaser_short.relative_to(config.DATA_DIR)) if teaser_short.is_file() else "",
        # how long it took to make, in total and per step (shown on the episode and used to plan the next one)
        "render_seconds": took,
        "render_steps": {"scenes": [{"idx": x.get("idx"), "took": x.get("took"), "stage": x.get("stage")}
                                    for x in pr.get("scenes", [])],
                         "finish": [{"key": x.get("key"), "took": x.get("took")} for x in pr.get("finish", [])]},
    }
    memory.add_episode(series_id, ep_data)
    _active_tasks[key] = {
        "status": "completed" if ok else "failed",
        "progress": 100,
        "message": "Production complete!" if ok else (res.get("error") or "Production failed"),
        "error": "" if ok else (res.get("error") or "Production failed"),
        "ep_num": ep_num,
        "video_file": ep_data["video_file"],
        "short_file": ep_data["short_file"],
        "duration": ep_data["duration"],
        "render_seconds": took,
        **{k: pr[k] for k in ("scenes", "finish", "scene_count", "scenes_done", "started_at") if k in pr},
        "elapsed": took,
        "eta_sec": 0,
        "percent": 100 if ok else pr.get("percent", 0),
        "can_resume": (not ok) and (_ep_dir(series_id, ep_num) / "script.json").is_file(),
    }


def start_episode_production(series_id: str, ep_num: int, script: dict):
    """Launches episode rendering in an asynchronous worker thread."""
    key = f"{series_id}:{ep_num}"
    if _active_tasks.get(key, {}).get("status") == "rendering":
        return {"ok": True, "message": f"Episode {ep_num} is already being made"}
    # kept so a production stopped by a restart can be resumed without the script editor
    try:
        d = _ep_dir(series_id, ep_num)
        d.mkdir(parents=True, exist_ok=True)
        (d / "script.json").write_text(json.dumps(script, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    from studio import ctx
    uid = ctx.uid_or_none()

    def run():   # the AI calls it makes (designs for new characters) are counted for this user
        with ctx.as_user(uid):
            _run_episode_pipeline(series_id, ep_num, script)
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return {"ok": True, "message": f"Episode {ep_num} production started"}


def resume_episode_production(series_id: str, ep_num: int) -> dict:
    """Starts a stopped production again from its saved script; scenes already made are reused (scene cache)."""
    f = _ep_dir(series_id, ep_num) / "script.json"
    if not f.is_file():
        return {"ok": False, "message": "The script of this episode was not saved; approve it again"}
    script = json.loads(f.read_text(encoding="utf-8"))
    return start_episode_production(series_id, ep_num, script)
