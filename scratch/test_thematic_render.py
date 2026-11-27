import math
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

def _draw_sphere(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int,
                 base_col: tuple[int, int, int], light_col: tuple[int, int, int], steps: int = 16):
    for i in range(steps):
        frac = i / max(1, steps - 1)
        cur_r = int(r * (1.0 - 0.72 * frac))
        shift_x = int(cx - (r * 0.32) * frac)
        shift_y = int(cy - (r * 0.32) * frac)
        c = tuple(int(base_col[k] + (light_col[k] - base_col[k]) * frac) for k in range(3))
        draw.ellipse([shift_x - cur_r, shift_y - cur_r, shift_x + cur_r, shift_y + cur_r], fill=c)

def draw_thematic_background(setting: str, visual_style: str, w: int, h: int) -> tuple[Image.Image, Image.Image]:
    text = f"{setting} {visual_style}".lower()
    sky_w, sky_h = w + 400, h + 200
    mid_w, mid_h = w + 500, h + 200

    if any(k in text for k in ["space", "nebula", "cosmic", "asteroid", "star", "planet", "galaxy", "sci-fi"]):
        sky = Image.new("RGBA", (sky_w, sky_h), (12, 10, 26, 255))
        sdraw = ImageDraw.Draw(sky)
        for y in range(sky_h):
            frac = y / sky_h
            c = (int(10 + 20 * frac), int(8 + 14 * frac), int(26 + 45 * frac), 255)
            sdraw.line([(0, y), (sky_w, y)], fill=c)

        # Nebula layer with Gaussian blur
        nebula = Image.new("RGBA", (sky_w, sky_h), (0, 0, 0, 0))
        ndraw = ImageDraw.Draw(nebula)
        for nx, ny, nr, ncol in [
            (int(sky_w * 0.35), int(sky_h * 0.30), 280, (140, 45, 185)),
            (int(sky_w * 0.68), int(sky_h * 0.22), 240, (35, 160, 215)),
            (int(sky_w * 0.50), int(sky_h * 0.42), 220, (210, 60, 140)),
            (int(sky_w * 0.85), int(sky_h * 0.40), 200, (90, 40, 170))
        ]:
            for r in range(nr, 0, -22):
                alpha = int(45 * (1.0 - r / nr))
                ndraw.ellipse([nx - r, ny - int(r * 0.6), nx + r, ny + int(r * 0.6)], fill=(*ncol, alpha))
        nebula = nebula.filter(ImageFilter.GaussianBlur(35))
        sky.alpha_composite(nebula)
        sdraw = ImageDraw.Draw(sky)

        # Twinkling Stars
        rng = random.Random(42)
        for _ in range(180):
            sx = rng.randint(0, sky_w)
            sy = rng.randint(0, int(sky_h * 0.85))
            sr = rng.choice([1, 1, 2, 2, 3])
            brightness = rng.randint(180, 255)
            star_col = rng.choice([
                (brightness, brightness, brightness, 255),
                (brightness, int(brightness * 0.9), int(brightness * 0.7), 255),
                (int(brightness * 0.8), int(brightness * 0.95), brightness, 255)
            ])
            sdraw.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=star_col)
            if sr >= 3:
                sdraw.line([(sx - 7, sy), (sx + 7, sy)], fill=(brightness, brightness, 255, 230), width=2)
                sdraw.line([(sx, sy - 7), (sx, sy + 7)], fill=(brightness, brightness, 255, 230), width=2)

        # Midground
        mid = Image.new("RGBA", (mid_w, mid_h), (0, 0, 0, 0))
        mdraw = ImageDraw.Draw(mid)
        px, py, pr = int(mid_w * 0.76), int(mid_h * 0.30), 105
        _draw_sphere(mdraw, px, py, pr, (165, 80, 135), (255, 195, 220), steps=16)
        mdraw.ellipse([px - 180, py - 38, px + 180, py + 38], outline=(235, 185, 245, 170), width=16)
        mdraw.ellipse([px - 155, py - 26, px + 155, py + 26], outline=(180, 240, 255, 150), width=8)

        _draw_sphere(mdraw, int(mid_w * 0.22), int(mid_h * 0.28), 45, (95, 85, 125), (175, 165, 205), steps=10)

        # Asteroid Terrain
        surf_y = int(mid_h * 0.58)
        mdraw.ellipse([-120, surf_y, mid_w + 240, mid_h + 380], fill=(42, 32, 68, 255))
        mdraw.ellipse([int(mid_w * 0.25), surf_y + 40, mid_w + 350, mid_h + 400], fill=(58, 44, 92, 255))
        for cx_a, cy_a, crx, cry in [
            (int(mid_w * 0.32), surf_y + 70, 75, 28),
            (int(mid_w * 0.65), surf_y + 95, 110, 36),
            (int(mid_w * 0.84), surf_y + 60, 55, 22)
        ]:
            mdraw.ellipse([cx_a - crx, cy_a - cry, cx_a + crx, cy_a + cry], fill=(32, 22, 54, 255), outline=(130, 85, 195, 220), width=4)
            mdraw.ellipse([cx_a - int(crx * 0.5), cy_a - int(cry * 0.4), cx_a + int(crx * 0.5), cy_a + int(cry * 0.4)], fill=(20, 14, 38, 255))

        for kx, ky in [(int(mid_w * 0.18), surf_y + 35), (int(mid_w * 0.52), surf_y + 55), (int(mid_w * 0.78), surf_y + 45)]:
            mdraw.polygon([(kx, ky - 36), (kx - 14, ky + 12), (kx + 14, ky + 12)], fill=(80, 240, 245, 240))
            mdraw.polygon([(kx + 10, ky - 26), (kx, ky + 12), (kx + 20, ky + 12)], fill=(220, 120, 255, 220))
    else:
        sky = Image.new("RGBA", (sky_w, sky_h), (135, 206, 235, 255))
        mid = Image.new("RGBA", (mid_w, mid_h), (0, 0, 0, 0))

    return sky.convert("RGB"), mid

sky, mid = draw_thematic_background("neon nebula field", "Sci-Fi Kids 3D", 1920, 1080)
canvas = sky.crop((0, 0, 1920, 1080)).convert("RGBA")
canvas.alpha_composite(mid.crop((0, 0, 1920, 1080)))

out_dir = Path(__file__).resolve().parent
canvas.convert("RGB").save(out_dir / "test_soft_nebula.jpg", quality=92)
print("SUCCESS: Soft nebula saved")
