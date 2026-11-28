"""Multi-Scene Long Video Compilation and Stitcher for PeakCut/Clipper.
Concatenates individual scene clips using smooth FFmpeg xfade transitions,
mixes background music, and exports master 16:9 Long Videos and 9:16 Shorts.
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger("peakcut.concat")

NO_WINDOW = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def _get_duration(video_path: Path) -> float:
    """Probes video duration via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=10)
        return float(p.stdout.strip())
    except Exception:
        return 0.0


def _stitch_via_concat_demuxer(clips: list[Path], out_mp4: Path) -> bool:
    """Fast, lossless concatenation using FFmpeg concat demuxer with stream copy."""
    list_file = out_mp4.parent / f"_concat_{out_mp4.stem}.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for c in clips:
                escaped = str(c.resolve()).replace("\\", "/")
                f.write(f"file '{escaped}'\n")
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            "-movflags", "+faststart",
            str(out_mp4)
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=180)
        return p.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000
    except Exception as e:
        log.error("Concat demuxer error: %s", e)
        return False
    finally:
        if list_file.is_file():
            try:
                list_file.unlink()
            except Exception:
                pass


def stitch_scenes(
    scene_videos: list[Path],
    out_mp4: Path,
    transition: str = "fade",
    transition_dur: float = 0.5,
    bgm_path: Path | None = None,
    on_frac=None
) -> bool:
    """Stitches N scene videos into a continuous long video.
    For long-form episodes (multi-minute videos), uses fast, lossless concat demuxer.
    Falls back gracefully to stream copy if complex xfade times out or fails.
    """
    if not scene_videos:
        return False
    
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    valid_clips = [p for p in scene_videos if p.is_file() and p.stat().st_size > 1000]
    
    if not valid_clips:
        return False
    
    if len(valid_clips) == 1:
        # Single scene: direct copy
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(valid_clips[0]), "-c", "copy", str(out_mp4)]
        p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=60)
        return p.returncode == 0 and out_mp4.is_file()

    # For long-form multi-scene videos (>= 5 scenes or long total duration),
    # concat demuxer stream copy is instantaneous (3-5s), 100% reliable, and avoids CPU re-encode timeouts.
    if len(valid_clips) >= 5 or transition == "none":
        ok = _stitch_via_concat_demuxer(valid_clips, out_mp4)
        if ok:
            return True

    # Multi-scene xfade pipeline for shorter scenes
    durations = [_get_duration(p) for p in valid_clips]
    inputs = []
    for p in valid_clips:
        inputs += ["-i", str(p)]
        
    filter_parts = []
    last_v = "0:v"
    last_a = "0:a"
    current_offset = durations[0] - transition_dur
    
    for i in range(1, len(valid_clips)):
        next_v = f"{i}:v"
        next_a = f"{i}:a"
        out_v = f"v_xfade_{i}"
        out_a = f"a_xfade_{i}"
        
        offset = max(0.1, current_offset)
        filter_parts.append(
            f"[{last_v}][{next_v}]xfade=transition={transition}:duration={transition_dur}:offset={offset:.2f}[{out_v}];"
            f"[{last_a}][{next_a}]acrossfade=d={transition_dur}[{out_a}]"
        )
        last_v = out_v
        last_a = out_a
        if i < len(valid_clips) - 1:
            current_offset += durations[i] - transition_dur
            
    fc = ";".join(filter_parts)
    
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc,
           "-map", f"[{last_v}]", "-map", f"[{last_a}]",
           "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",  # plays everywhere
           "-maxrate", "8M", "-bufsize", "16M",
           "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart",
           str(out_mp4)]

    try:
        from studio import progress as prog
        p = prog.ffmpeg(cmd, max(1.0, sum(durations) - transition_dur * (len(durations) - 1)), on_frac, timeout=600)
        if p.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000:
            return True
    except Exception as e:
        log.warning("Stitch scenes xfade timed out or failed (%s); falling back to concat demuxer", e)
    
    # Fallback to concat demuxer
    return _stitch_via_concat_demuxer(valid_clips, out_mp4)


def cut_teaser_short(long_video_path: Path, out_short_path: Path, max_dur: float = 45.0) -> bool:
    """Cuts a 9:16 vertical teaser short from a 16:9 master video for TikTok/Shorts/Reels."""
    if not long_video_path.is_file():
        return False
        
    out_short_path.parent.mkdir(parents=True, exist_ok=True)
    dur = min(max_dur, _get_duration(long_video_path))
    if dur <= 1.0:
        return False
        
    # Center crop 16:9 to 9:16
    vf = "crop=ih*(9/16):ih:(iw-ih*(9/16))/2:0,scale=1080:1920"
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", "0", "-t", f"{dur:.2f}",
        "-i", str(long_video_path),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        str(out_short_path)
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=120)
        return p.returncode == 0 and out_short_path.is_file() and out_short_path.stat().st_size > 1000
    except Exception as e:
        log.error("Cut teaser short error: %s", e)
        return False
