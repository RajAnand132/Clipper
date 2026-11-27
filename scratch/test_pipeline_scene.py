import sys
from pathlib import Path

clipper_dir = Path("E:/YouTube/Automation/Clipper")
sys.path.insert(0, str(clipper_dir))

from studio import visuals, render

out_dir = clipper_dir / "scratch"
test_mp4 = out_dir / "test_space_scene_raw.mp4"
final_mp4 = out_dir / "test_space_scene_final.mp4"
fonts_dir = clipper_dir / "studio" / "fonts"

words = [
    {"w": "Look", "s": 0.2, "e": 0.6},
    {"w": "at", "s": 0.6, "e": 0.9},
    {"w": "this", "s": 0.9, "e": 1.2},
    {"w": "asteroid,", "s": 1.2, "e": 1.8},
    {"w": "Orbit!", "s": 1.8, "e": 2.5}
]

# Use clean proportional size for 16:9 dialogue
look = dict(render.STYLES["bounce"], size=84)
w_h = (1920, 1080)
cap_y = 960
ass_content = render.build_ass(
    words, 0.0, 3.0,
    "",
    look,
    [],
    0,
    cap_y,
    show_hook=False,
    play_res=w_h
)
ass_file = out_dir / "test_space_scene.ass"
ass_file.write_text(ass_content, encoding="utf-8")

# Escape path for ffmpeg filter on Windows: forward slashes and colon escaped
f_dir_str = str(fonts_dir).replace("\\", "/").replace(":", "\\:")
ass_file_str = str(ass_file.name)

sub_cmd = [
    "ffmpeg", "-y", "-v", "error",
    "-i", str(test_mp4),
    "-vf", f"ass={ass_file_str}:fontsdir='{f_dir_str}'",
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
    "-c:a", "copy",
    str(final_mp4)
]
p = render.subprocess.run(sub_cmd, cwd=out_dir, capture_output=True, text=True,
                          creationflags=render.NO_WINDOW, timeout=60)
print(f"Subtitled render: code={p.returncode}")

# Extract frame at 1.5s
render.subprocess.run([
    "ffmpeg", "-y", "-ss", "00:00:01.500", "-i", str(final_mp4),
    "-vframes", "1", str(out_dir / "test_frame_subtitles_v2.jpg")
], capture_output=True)
print("Extracted test_frame_subtitles_v2.jpg")
