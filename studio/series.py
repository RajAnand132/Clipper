"""Series Production Orchestrator for PeakCut/Clipper.
Coordinates background rendering of approved episodic scripts:
synthesizes character audio, renders 3D parallax visuals, applies subtitles,
and stitches complete 16:9 Long Videos and 9:16 Shorts.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from studio import config, concat, memory, render, storyteller, templates, tts, visuals

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

    scene_videos = []
    total_scenes = len(scenes)
    aspect_ratio = series.get("aspect_ratio", "16:9")

    # Add any newly introduced characters to character vault
    for nc in script.get("new_characters", []):
        memory.add_character(series_id, nc)

    look = next((t["look"] for t in templates.BUILTIN if t["id"] == "b-hormozi"), templates.legacy())

    for i, sc in enumerate(scenes):
        idx = i + 1
        _active_tasks[key] = {
            "status": "rendering",
            "progress": int(10 + (idx / total_scenes) * 75),
            "message": f"Rendering Scene {idx}/{total_scenes}: {sc.get('setting', '')[:30]}..."
        }

        # 1. Synthesize Audio
        audio_file = ep_dir / f"scene_{idx:02d}.mp3"
        dialogue = sc.get("dialogue", "").strip()
        voice_id = sc.get("voice_id", "en-US-ChristopherNeural")
        words = tts.synthesize_scene_voice(dialogue, voice_id, audio_file)

        # 2. Determine Duration
        audio_dur = concat._get_duration(audio_file)
        target_scene_dur = float(sc.get("duration_sec") or 55.0)
        dur = max(4.0, audio_dur + 0.8, target_scene_dur)

        # 3. Generate 3D Visual Keyframe
        img_file = ep_dir / f"scene_{idx:02d}.jpg"
        v_prompt = sc.get("visual_prompt", f"{sc.get('setting')}, 3d pixar animation style")
        visuals.generate_scene_frame(v_prompt, img_file, aspect_ratio=aspect_ratio)

        # 4. Render Dynamic 3D Animated Scene with Multi-character Staging & Parallax
        raw_video = ep_dir / f"scene_{idx:02d}_raw.mp4"
        motion = sc.get("camera_motion", "dolly_in")
        speaker_name = sc.get("speaker", "Character")

        # Determine characters present in the scene
        series_chars = series.get("characters", [])
        scene_char_names = sc.get("characters", [])
        if not scene_char_names and speaker_name.lower() != "narrator":
            scene_char_names = [speaker_name]

        scene_chars = []
        for cn in scene_char_names:
            c_obj = next((c for c in series_chars if c.get("name", "").lower() == cn.lower()), None)
            if c_obj:
                scene_chars.append(c_obj)
            else:
                scene_chars.append({"name": cn, "species": "Character", "visual_anchor": ""})

        # If only 1 character is present, bring companion if series has 2+ characters
        # so scenes feature lively two-shot conversation and interaction
        if len(scene_chars) == 1 and len(series_chars) >= 2:
            companion = next((c for c in series_chars if c.get("name", "").lower() != scene_chars[0].get("name", "").lower()), None)
            if companion:
                scene_chars.append(companion)
        elif len(scene_chars) == 0 and len(series_chars) >= 2:
            scene_chars = series_chars[:2]
        elif len(scene_chars) == 0 and len(series_chars) == 1:
            scene_chars = series_chars[:1]

        speaker_char = next((c for c in series_chars if c.get("name", "").lower() == speaker_name.lower()), None)
        sp_species = speaker_char.get("species", "Character") if speaker_char else "Animal"
        sp_anchor = speaker_char.get("visual_anchor", "") if speaker_char else series.get("visual_style", "")

        ok_3d = visuals.render_3d_animated_scene(
            characters=scene_chars,
            speaker_name=speaker_name,
            character_name=speaker_name,
            character_species=sp_species,
            visual_anchor=sp_anchor,
            setting=sc.get("setting", series.get("title", "3D Animated World")),
            visual_style=series.get("visual_style", "whimsical 3D cartoon"),
            audio_path=audio_file,
            out_mp4=raw_video,
            duration=dur,
            motion=motion,
            aspect_ratio=aspect_ratio
        )
        if not ok_3d or not raw_video.is_file():
            visuals.render_parallax_motion(img_file, audio_file, raw_video, dur, motion=motion, aspect_ratio=aspect_ratio)

        # 5. Apply Subtitles cleanly at the bottom
        final_video = ep_dir / f"scene_{idx:02d}_final.mp4"
        if words and raw_video.is_file():
            try:
                # Align words to start of scene audio
                w_h = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)
                # Bottom placement: 89% height (960 in 1080p, 1650 in 1920 vertical)
                cap_y = 960 if aspect_ratio == "16:9" else 1650
                cap_style = dict(look.get("cap", look), size=84 if aspect_ratio == "16:9" else 112)
                ass_content = render.build_ass(
                    words, 0.0, dur,
                    "",  # No hook headline on episode scenes
                    cap_style,
                    [],
                    0,
                    cap_y,
                    show_hook=False,
                    hook_look=look.get("hook"),
                    play_res=w_h
                )
                ass_file = ep_dir / f"scene_{idx:02d}.ass"
                ass_file.write_text(ass_content, encoding="utf-8")
                
                # Apply ASS filter via FFmpeg with fontsdir
                fonts_dir = Path(__file__).resolve().parent / "fonts"
                f_dir_str = str(fonts_dir).replace("\\", "/").replace(":", "\\:")
                sub_cmd = [
                    "ffmpeg", "-y", "-v", "error",
                    "-i", str(raw_video),
                    "-vf", f"ass={ass_file.name}:fontsdir='{f_dir_str}'",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-c:a", "copy",
                    str(final_video)
                ]
                p = render.subprocess.run(sub_cmd, cwd=ep_dir, capture_output=True, text=True,
                                          creationflags=render.NO_WINDOW, timeout=60)
                if p.returncode != 0 or not final_video.is_file():
                    final_video = raw_video
            except Exception as e:
                log.warning("Subtitle burn failed on scene %s: %s", idx, e)
                final_video = raw_video
        else:
            final_video = raw_video

        if final_video.is_file():
            scene_videos.append(final_video)

    # 6. Stitch all scenes into Master Long Video
    _active_tasks[key] = {"status": "rendering", "progress": 90, "message": "Stitching scenes into Master Video..."}
    master_video = ep_dir / f"episode_{ep_num:03d}_master.mp4"
    ok = concat.stitch_scenes(scene_videos, master_video, transition_dur=0.5)

    # 7. Generate 9:16 Teaser Short
    teaser_short = ep_dir / f"episode_{ep_num:03d}_short.mp4"
    if ok and aspect_ratio == "16:9":
        concat.cut_teaser_short(master_video, teaser_short, max_dur=45.0)

    # 8. Finalize Episode Record
    total_dur = concat._get_duration(master_video) if master_video.is_file() else 0.0
    ep_data = {
        "episode_num": ep_num,
        "title": script.get("title", f"Episode {ep_num}"),
        "summary": script.get("synopsis", ""),
        "unresolved_hook": script.get("unresolved_hook", ""),
        "featured_characters": list({sc.get("speaker") for sc in scenes if sc.get("speaker")}),
        "status": "completed" if ok else "failed",
        "script": scenes,
        "duration": round(total_dur, 2),
        "video_file": str(master_video.relative_to(config.DATA_DIR)) if master_video.is_file() else "",
        "short_file": str(teaser_short.relative_to(config.DATA_DIR)) if teaser_short.is_file() else ""
    }
    memory.add_episode(series_id, ep_data)
    _active_tasks[key] = {
        "status": "completed" if ok else "failed",
        "progress": 100,
        "message": "Production complete!",
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
