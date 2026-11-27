"""Series Production Orchestrator for PeakCut/Clipper.
Coordinates background rendering of approved episodic scripts:
synthesizes character audio, renders 3D parallax visuals, applies subtitles,
and stitches complete 16:9 Long Videos and 9:16 Shorts.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from studio import config, formats, memory, production, visuals

log = logging.getLogger("peakcut.series")

_active_tasks: dict[str, dict] = {}  # f"{sid}:{ep_num}" -> {"status", "progress", "error"}


def get_production_status(series_id: str, ep_num: int) -> dict:
    key = f"{series_id}:{ep_num}"
    if key in _active_tasks:
        return _active_tasks[key]
    ep = memory.get_episode(series_id, ep_num)
    if ep:
        return {"status": ep.get("status", "draft"), "progress": 100 if ep.get("status") == "completed" else 0}
    return {"status": "not_found", "progress": 0}


def _run_episode_pipeline(series_id: str, ep_num: int, script: dict):
    key = f"{series_id}:{ep_num}"
    _active_tasks[key] = {"status": "rendering", "progress": 5, "message": "Starting production pipeline..."}
    
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
            voice = voice_hint.get(name.lower()) or tts.pick_voice(lang, f"{name} {sc.get('setting', '')}", taken | {
                formats.narrator_voice(fmt, lang)})
            taken.add(voice)
            new_c = {
                "id": memory._slugify(name),
                "name": name,
                "species": "Character",
                "visual_anchor": f"{name}, distinctive consistent look, {fmt['visual']['style'][:80]}",
                "voice_id": voice,
                "personality": "Introduced in this episode"
            }
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

    def progress(pct, msg):
        _active_tasks[key] = {"status": "rendering", "progress": int(pct), "message": msg}

    try:
        res = production.build_episode(series, ep_num, script, ep_dir, progress=progress)
    except Exception as e:  # noqa: BLE001
        log.exception("Episode %s:%s production failed", series_id, ep_num)
        res = {"ok": False, "error": str(e)}
    ok = bool(res.get("ok"))
    master_video = res.get("master") or (ep_dir / f"episode_{ep_num:03d}_master.mp4")
    teaser_short = res.get("short") or (ep_dir / f"episode_{ep_num:03d}_short.mp4")
    saved_scenes = [{k: v for k, v in sc.items() if k != "cast"} for sc in (res.get("scenes") or scenes)]

    # Finalize Episode Record
    total_dur = float(res.get("duration") or 0.0)
    ep_data = {
        "episode_num": ep_num,
        "title": script.get("title", f"Episode {ep_num}"),
        "summary": script.get("synopsis", ""),
        "unresolved_hook": script.get("unresolved_hook", ""),
        "featured_characters": sorted({ln.get("speaker") for sc in saved_scenes for ln in sc.get("lines", [])
                                       if ln.get("speaker") and ln.get("speaker").lower() != "narrator"}),
        "status": "completed" if ok else "failed",
        "script": saved_scenes,
        "format": res.get("format", series.get("format", "")),
        "duration": round(total_dur, 2),
        "video_file": str(master_video.relative_to(config.DATA_DIR)) if ok and master_video.is_file() else "",
        "short_file": str(teaser_short.relative_to(config.DATA_DIR)) if teaser_short.is_file() else ""
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
        "duration": ep_data["duration"]
    }


def start_episode_production(series_id: str, ep_num: int, script: dict):
    """Launches episode rendering in an asynchronous worker thread."""
    t = threading.Thread(target=_run_episode_pipeline, args=(series_id, ep_num, script), daemon=True)
    t.start()
    return {"ok": True, "message": f"Episode {ep_num} production started"}
