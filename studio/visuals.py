"""3D Visual Generation & Dynamic Parallax Camera Engine for PeakCut/Clipper.
Generates 3D character/environment scene keyframes and transforms them into
cinematic animated scenes using multi-plane camera motion (dolly-in, pan, depth-zoom).
Features a high-gloss 3D procedural cartoon avatar and environment rendering engine.
"""
from __future__ import annotations

import io
import logging
import math
import random
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

log = logging.getLogger("peakcut.visuals")

NO_WINDOW = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def _draw_sphere(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int,
                 base_col: tuple[int, int, int], light_col: tuple[int, int, int], steps: int = 18):
    """Draws a smooth 3D shaded sphere using concentric offset gradient discs."""
    for i in range(steps):
        frac = i / max(1, steps - 1)
        cur_r = int(r * (1.0 - 0.72 * frac))
        shift_x = int(cx - (r * 0.32) * frac)
        shift_y = int(cy - (r * 0.32) * frac)
        c = tuple(int(base_col[k] + (light_col[k] - base_col[k]) * frac) for k in range(3))
        draw.ellipse([shift_x - cur_r, shift_y - cur_r, shift_x + cur_r, shift_y + cur_r], fill=c)


def draw_3d_cartoon_avatar(name: str, species: str, visual_anchor: str, out_path: Path, width: int = 1024, height: int = 768) -> bool:
    """Renders a stylized high-gloss 3D Pixar/toy cartoon avatar with volumetric lighting,

    glossy catchlight eyes, expressive facial features, accessories, and studio vignette.
    Guarantees rich 3D character visual output with zero blank or solid green boxes.
    """
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (width, height), (22, 24, 38))
        draw = ImageDraw.Draw(img)

        # 1. Warm volumetric studio background with radial gradient lighting
        cx, cy = width // 2, int(height * 0.44)
        diag = int(math.hypot(width, height))
        for r in range(diag, 0, -18):
            frac = r / diag
            # Soft dark indigo-slate to glowing warm amber-violet core
            bg_c = (
                int(42 + 25 * (1.0 - frac)),
                int(38 + 22 * (1.0 - frac)),
                int(68 + 40 * (1.0 - frac))
            )
            draw.ellipse([cx - r, cy - int(r * 0.75), cx + r, cy + int(r * 0.75)], fill=bg_c)

        # Subtle floor gradient / drop plane
        floor_y = int(height * 0.78)
        for y in range(floor_y, height):
            frac = (y - floor_y) / (height - floor_y)
            f_col = (int(25 * (1 - frac)), int(22 * (1 - frac)), int(38 * (1 - frac)))
            draw.line([(0, y), (width, y)], fill=f_col)

        # Soft character ground shadow
        draw.ellipse([cx - 220, floor_y - 20, cx + 220, floor_y + 45], fill=(12, 10, 20))
        img = img.filter(ImageFilter.GaussianBlur(12))
        draw = ImageDraw.Draw(img)

        # 2. Determine species palette & traits
        text_full = f"{name} {species} {visual_anchor}".lower()
        if any(w in text_full for w in ["fox", "nova"]):
            base_col = (230, 105, 25)
            light_col = (255, 175, 75)
            muzzle_col = (255, 250, 245)
            nose_col = (30, 20, 18)
            ear_shape = "pointed"
            scarf_col = (35, 195, 225)  # Cyan cyber spacesuit collar
            eye_iris = (40, 135, 225)
        elif any(w in text_full for w in ["puff", "alien", "orbit", "blob", "fuzzy"]):
            base_col = (38, 195, 185)
            light_col = (180, 255, 250)
            muzzle_col = (210, 255, 250)
            nose_col = (25, 45, 65)
            ear_shape = "antenna"
            scarf_col = (145, 95, 225)  # Lavender cosmic aura band
            eye_iris = (24, 75, 140)
        elif any(w in text_full for w in ["bear", "bhalu", "cub"]):
            base_col = (135, 78, 40)
            light_col = (205, 142, 95)
            muzzle_col = (225, 185, 150)
            nose_col = (35, 22, 18)
            ear_shape = "round"
            scarf_col = (245, 185, 30)  # Sunny warm yellow scarf
            eye_iris = (45, 130, 215)
        elif any(w in text_full for w in ["roo", "bunny", "rabbit", "hare", "pippin", "chhotu"]):
            base_col = (210, 195, 185)
            light_col = (252, 246, 242)
            muzzle_col = (255, 250, 246)
            nose_col = (235, 130, 155)
            ear_shape = "long"
            scarf_col = (65, 175, 240)  # Sky blue cozy bow/scarf
            eye_iris = (60, 170, 240)
        elif any(w in text_full for w in ["dog", "puppy", "barnaby", "hound"]):
            base_col = (195, 135, 60)
            light_col = (245, 190, 120)
            muzzle_col = (245, 220, 190)
            nose_col = (30, 25, 25)
            ear_shape = "floppy"
            scarf_col = (220, 65, 65)  # Crimson collar/bandana
            eye_iris = (40, 140, 90)
        elif any(w in text_full for w in ["lion", "bheem", "tiger"]):
            base_col = (220, 145, 45)
            light_col = (255, 195, 105)
            muzzle_col = (248, 225, 185)
            nose_col = (45, 25, 20)
            ear_shape = "mane"
            scarf_col = (235, 95, 40)
            eye_iris = (220, 150, 30)
        elif any(w in text_full for w in ["monkey", "ape", "rooroo"]):
            base_col = (155, 95, 55)
            light_col = (210, 155, 105)
            muzzle_col = (240, 195, 165)
            nose_col = (50, 30, 25)
            ear_shape = "side_round"
            scarf_col = (60, 190, 120)
            eye_iris = (70, 140, 220)
        else:
            base_col = (165, 110, 75)
            light_col = (225, 168, 128)
            muzzle_col = (240, 205, 175)
            nose_col = (40, 28, 25)
            ear_shape = "round"
            scarf_col = (240, 160, 45)
            eye_iris = (40, 140, 220)

        # 3. Draw Body / Torso with 3D volume
        body_cy = int(height * 0.70)
        _draw_sphere(draw, cx, body_cy, 185, base_col, light_col, steps=16)

        # Soft chest patch
        chest_col = tuple(min(255, int(c * 1.15)) for c in muzzle_col)
        draw.ellipse([cx - 85, body_cy - 75, cx + 85, body_cy + 95], fill=chest_col)

        # 4. Cozy 3D Knitted Scarf / Collar
        scarf_y = int(height * 0.54)
        for s_off in range(-25, 26, 6):
            s_frac = (s_off + 25) / 50.0
            s_c = tuple(int(scarf_col[k] * (0.75 + 0.35 * s_frac)) for k in range(3))
            draw.rounded_rectangle([cx - 150, scarf_y + s_off, cx + 150, scarf_y + s_off + 24], radius=16, fill=s_c)
        # Scarf tail hanging down
        draw.rounded_rectangle([cx + 50, scarf_y + 15, cx + 105, scarf_y + 115], radius=14, fill=scarf_col)

        # 5. Lion Mane / Ears
        head_cy = int(height * 0.38)
        head_r = 150

        if ear_shape == "mane":
            for m_ang in range(0, 360, 20):
                rad = math.radians(m_ang)
                mx = int(cx + (head_r + 20) * math.cos(rad))
                my = int(head_cy + (head_r + 15) * math.sin(rad))
                draw.ellipse([mx - 38, my - 38, mx + 38, my + 38], fill=(195, 105, 30))

        if ear_shape in ("round", "side_round", "mane"):
            # Left ear
            ear_lx, ear_ly = cx - int(head_r * 0.82), head_cy - int(head_r * 0.78)
            _draw_sphere(draw, ear_lx, ear_ly, 46, base_col, light_col, steps=10)
            draw.ellipse([ear_lx - 20, ear_ly - 20, ear_lx + 20, ear_ly + 20], fill=(235, 160, 165))
            # Right ear
            ear_rx, ear_ry = cx + int(head_r * 0.82), head_cy - int(head_r * 0.78)
            _draw_sphere(draw, ear_rx, ear_ry, 46, base_col, light_col, steps=10)
            draw.ellipse([ear_rx - 20, ear_ry - 20, ear_rx + 20, ear_ry + 20], fill=(235, 160, 165))
        elif ear_shape == "long":  # Bunny ears
            # Left bunny ear
            draw.rounded_rectangle([cx - 95, head_cy - 270, cx - 45, head_cy - 70], radius=26, fill=light_col)
            draw.rounded_rectangle([cx - 85, head_cy - 250, cx - 55, head_cy - 90], radius=16, fill=(245, 175, 185))
            # Right bunny ear
            draw.rounded_rectangle([cx + 45, head_cy - 270, cx + 95, head_cy - 70], radius=26, fill=light_col)
            draw.rounded_rectangle([cx + 55, head_cy - 250, cx + 85, head_cy - 90], radius=16, fill=(245, 175, 185))
        elif ear_shape == "floppy":  # Dog ears
            draw.rounded_rectangle([cx - 180, head_cy - 70, cx - 110, head_cy + 85], radius=32, fill=base_col)
            draw.rounded_rectangle([cx + 110, head_cy - 70, cx + 180, head_cy + 85], radius=32, fill=base_col)
        elif ear_shape == "pointed":  # Fox ears
            draw.polygon([(cx - 130, head_cy - 40), (cx - 75, head_cy - 220), (cx - 20, head_cy - 40)], fill=base_col)
            draw.polygon([(cx - 110, head_cy - 45), (cx - 75, head_cy - 195), (cx - 35, head_cy - 45)], fill=(255, 175, 185))
            draw.polygon([(cx + 20, head_cy - 40), (cx + 75, head_cy - 220), (cx + 130, head_cy - 40)], fill=base_col)
            draw.polygon([(cx + 35, head_cy - 45), (cx + 75, head_cy - 195), (cx + 110, head_cy - 45)], fill=(255, 175, 185))
        elif ear_shape == "antenna":  # Alien puff / Orbit antenna
            draw.line([(cx, head_cy - 90), (cx, head_cy - 210)], fill=(30, 175, 165), width=8)
            draw.ellipse([cx - 26, head_cy - 236, cx + 26, head_cy - 184], fill=(255, 235, 75))
            draw.ellipse([cx - 36, head_cy - 246, cx + 36, head_cy - 174], outline=(255, 255, 190, 160), width=4)

        # 6. Main 3D Spherical Head
        _draw_sphere(draw, cx, head_cy, head_r, base_col, light_col, steps=22)

        # Directional forehead specular shine
        draw.ellipse([cx - 95, head_cy - 105, cx - 25, head_cy - 55], fill=(255, 255, 255, 80))

        # 7. Blushing Cheeks (cute glowing pink pads)
        blush_col = (255, 140, 155)
        draw.ellipse([cx - 108, head_cy + 22, cx - 55, head_cy + 52], fill=blush_col)
        draw.ellipse([cx + 55, head_cy + 22, cx + 108, head_cy + 52], fill=blush_col)

        # 8. Big Glossy Pixar Eyes
        eye_y = head_cy - 12
        eye_spacing = 58
        eye_w, eye_h = 36, 46

        for ex in (cx - eye_spacing, cx + eye_spacing):
            # Eye white (sclera)
            draw.ellipse([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h], fill=(255, 255, 255))
            # Colored iris
            draw.ellipse([ex - eye_w + 7, eye_y - eye_h + 8, ex + eye_w - 7, eye_y + eye_h - 4], fill=eye_iris)
            # Inner iris glow
            iris_glow = tuple(min(255, int(c * 1.35)) for c in eye_iris)
            draw.ellipse([ex - eye_w + 12, eye_y - eye_h + 16, ex + eye_w - 12, eye_y + eye_h - 10], fill=iris_glow)
            # Deep pupil
            draw.ellipse([ex - 15, eye_y - 14, ex + 15, eye_y + 18], fill=(12, 14, 20))
            # Primary specular catchlight (bright white top-left)
            draw.ellipse([ex - 18, eye_y - 24, ex - 6, eye_y - 12], fill=(255, 255, 255))
            # Secondary catchlight (small bottom-right sparkle)
            draw.ellipse([ex + 4, eye_y + 2, ex + 11, eye_y + 9], fill=(255, 255, 255))

        # Expressive cute eyebrows
        brow_y = eye_y - eye_h - 8
        draw.rounded_rectangle([cx - eye_spacing - 30, brow_y - 4, cx - eye_spacing + 24, brow_y + 4], radius=4, fill=base_col)
        draw.rounded_rectangle([cx + eye_spacing - 24, brow_y - 4, cx + eye_spacing + 30, brow_y + 4], radius=4, fill=base_col)

        # 9. 3D Rounded Snout / Muzzle
        snout_cy = head_cy + 42
        _draw_sphere(draw, cx, snout_cy, 62, muzzle_col, (255, 250, 245), steps=12)

        # Glossy Button Nose
        nose_y = snout_cy - 18
        draw.ellipse([cx - 24, nose_y - 14, cx + 24, nose_y + 14], fill=nose_col)
        # Nose specular catchlight
        draw.ellipse([cx - 10, nose_y - 10, cx - 2, nose_y - 4], fill=(255, 255, 255))

        # Cheerful Smile & Open Mouth
        mouth_y = snout_cy + 12
        draw.arc([cx - 30, mouth_y - 10, cx + 30, mouth_y + 24], start=15, end=165, fill=nose_col, width=5)
        # Small cute tongue
        draw.ellipse([cx - 14, mouth_y + 12, cx + 14, mouth_y + 26], fill=(245, 110, 130))

        # 10. Frosted Glass Character Name Banner
        banner_w, banner_h = 420, 48
        banner_x0 = cx - banner_w // 2
        banner_y0 = height - 76
        # Translucent dark pill badge
        draw.rounded_rectangle([banner_x0, banner_y0, banner_x0 + banner_w, banner_y0 + banner_h], radius=24, fill=(18, 20, 32))
        draw.rounded_rectangle([banner_x0 + 1, banner_y0 + 1, banner_x0 + banner_w - 1, banner_y0 + banner_h - 1], radius=24, outline=(100, 115, 150), width=1)

        # Crisp badge text
        label = f"★ {name}  ·  {species or 'Character'} ★"
        draw.text((cx, banner_y0 + banner_h // 2), label, fill=(245, 245, 250), anchor="mm")

        # Save high quality JPEG
        img.save(out_path, "JPEG", quality=92, optimize=True)
        log.info("Rendered procedural 3D cartoon avatar for '%s' to %s", name, out_path)
        return True
    except Exception as e:
        log.error("Failed to render 3D cartoon avatar: %s", e)
        return False


def draw_thematic_background(setting: str, visual_style: str, w: int, h: int) -> tuple[Image.Image, Image.Image]:
    """Generates rich, high-gloss 3D Pixar/toy cartoon environment layers (Sky and Midground).
    Automatically adapts to Space/Cosmic, Enchanted Forest, Farm/Meadow, Cozy Indoor, or Ocean themes.
    """
    text = f"{setting} {visual_style}".lower()
    sky_w, sky_h = w + 450, h + 220
    mid_w, mid_h = w + 550, h + 220

    if any(k in text for k in ["space", "nebula", "cosmic", "asteroid", "star", "planet", "galaxy", "sci-fi", "orbit"]):
        # 1. Cosmic Deep Space Sky
        sky = Image.new("RGBA", (sky_w, sky_h), (12, 10, 26, 255))
        sdraw = ImageDraw.Draw(sky)
        for y in range(sky_h):
            frac = y / sky_h
            c = (int(10 + 20 * frac), int(8 + 14 * frac), int(26 + 45 * frac), 255)
            sdraw.line([(0, y), (sky_w, y)], fill=c)

        # Soft glowing nebula clouds
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

        # Twinkling 3D Stars
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

        # 2. Midground: Floating 3D Saturn Ringed Planet & Asteroid Terrain
        mid = Image.new("RGBA", (mid_w, mid_h), (0, 0, 0, 0))
        mdraw = ImageDraw.Draw(mid)
        px, py, pr = int(mid_w * 0.76), int(mid_h * 0.30), 105
        _draw_sphere(mdraw, px, py, pr, (165, 80, 135), (255, 195, 220), steps=16)
        mdraw.ellipse([px - 180, py - 38, px + 180, py + 38], outline=(235, 185, 245, 170), width=16)
        mdraw.ellipse([px - 155, py - 26, px + 155, py + 26], outline=(180, 240, 255, 150), width=8)

        _draw_sphere(mdraw, int(mid_w * 0.22), int(mid_h * 0.28), 45, (95, 85, 125), (175, 165, 205), steps=10)

        # Cratered Asteroid Surface
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

    elif any(k in text for k in ["forest", "jungle", "tree", "river", "garden", "panchatantra", "woods"]):
        # Enchanted Forest
        sky = Image.new("RGBA", (sky_w, sky_h), (115, 190, 225, 255))
        sdraw = ImageDraw.Draw(sky)
        for y in range(sky_h):
            frac = y / sky_h
            c = (int(105 + 130 * frac), int(175 + 65 * frac), int(225 - 55 * frac), 255)
            sdraw.line([(0, y), (sky_w, y)], fill=c)
        # Volumetric Sunbeams / Godrays
        for gx in range(int(sky_w * 0.1), int(sky_w * 0.8), 120):
            sdraw.polygon([(gx, 0), (gx + 70, 0), (gx + 280, sky_h), (gx + 170, sky_h)], fill=(255, 255, 210, 40))

        mid = Image.new("RGBA", (mid_w, mid_h), (0, 0, 0, 0))
        mdraw = ImageDraw.Draw(mid)
        # Layered mossy knolls
        mdraw.ellipse([-100, int(mid_h * 0.46), mid_w + 200, mid_h + 380], fill=(42, 118, 52, 255))
        mdraw.ellipse([int(mid_w * 0.30), int(mid_h * 0.52), mid_w + 350, mid_h + 400], fill=(30, 92, 40, 255))

        # Giant fairytale mushrooms (Pixar style)
        for mx, my, mrad in [(int(mid_w * 0.22), int(mid_h * 0.52), 65), (int(mid_w * 0.82), int(mid_h * 0.48), 85)]:
            mdraw.rounded_rectangle([mx - 18, my - 10, mx + 18, my + 95], radius=12, fill=(245, 240, 225, 255))
            mdraw.ellipse([mx - mrad, my - int(mrad * 0.85), mx + mrad, my + 15], fill=(225, 42, 48, 255))
            for dx_p, dy_p in [(-35, -25), (0, -35), (35, -20), (-15, -8), (20, -5)]:
                mdraw.ellipse([mx + dx_p - 10, my + dy_p - 10, mx + dx_p + 10, my + dy_p + 10], fill=(255, 255, 255, 255))

        # Winding azure river
        mdraw.polygon([
            (int(mid_w * 0.42), int(mid_h * 0.65)),
            (int(mid_w * 0.56), int(mid_h * 0.65)),
            (int(mid_w * 0.68), mid_h),
            (int(mid_w * 0.40), mid_h)
        ], fill=(65, 175, 225, 240))

    elif any(k in text for k in ["room", "bedroom", "indoor", "nursery", "house", "bed", "sleep", "night"]):
        # Cozy Bedroom / Nursery
        sky = Image.new("RGBA", (sky_w, sky_h), (25, 22, 45, 255))
        sdraw = ImageDraw.Draw(sky)
        # Pastel wall stripes
        for x in range(0, sky_w, 60):
            c = (38, 34, 62, 255) if (x // 60) % 2 == 0 else (46, 42, 74, 255)
            sdraw.rectangle([x, 0, x + 60, sky_h], fill=c)

        # Arched window showing starry night & glowing crescent moon
        wx, wy, ww, wh = int(sky_w * 0.50), int(sky_h * 0.15), 180, 260
        sdraw.rounded_rectangle([wx - ww // 2, wy, wx + ww // 2, wy + wh], radius=80, fill=(16, 18, 38, 255), outline=(180, 160, 210, 255), width=8)
        # Moon in window
        sdraw.ellipse([wx - 25, wy + 40, wx + 45, wy + 110], fill=(255, 245, 180, 255))
        sdraw.ellipse([wx - 10, wy + 35, wx + 55, wy + 105], fill=(16, 18, 38, 255))

        mid = Image.new("RGBA", (mid_w, mid_h), (0, 0, 0, 0))
        mdraw = ImageDraw.Draw(mid)
        # Wooden floorboards
        floor_y = int(mid_h * 0.68)
        mdraw.rectangle([0, floor_y, mid_w, mid_h], fill=(130, 80, 45, 255))
        for fy in range(floor_y, mid_h, 30):
            mdraw.line([(0, fy), (mid_w, fy)], fill=(105, 62, 35, 255), width=2)
        # Soft cozy rug
        mdraw.ellipse([int(mid_w * 0.20), floor_y + 10, int(mid_w * 0.80), mid_h + 40], fill=(235, 145, 170, 220))
        # Warm bedside lamp glow
        lx, ly = int(mid_w * 0.84), floor_y - 80
        mdraw.rectangle([lx - 12, ly, lx + 12, floor_y], fill=(160, 140, 110, 255))
        mdraw.polygon([(lx - 45, ly), (lx + 45, ly), (lx + 25, ly - 60), (lx - 25, ly - 60)], fill=(255, 215, 100, 255))

    elif any(k in text for k in ["ocean", "sea", "underwater", "water", "reef"]):
        # Ocean Underwater
        sky = Image.new("RGBA", (sky_w, sky_h), (10, 50, 95, 255))
        sdraw = ImageDraw.Draw(sky)
        for y in range(sky_h):
            frac = y / sky_h
            c = (int(15 + 10 * frac), int(85 - 35 * frac), int(155 - 60 * frac), 255)
            sdraw.line([(0, y), (sky_w, y)], fill=c)

        mid = Image.new("RGBA", (mid_w, mid_h), (0, 0, 0, 0))
        mdraw = ImageDraw.Draw(mid)
        mdraw.ellipse([-100, int(mid_h * 0.62), mid_w + 200, mid_h + 380], fill=(215, 185, 130, 255))
        # Coral formations
        for cx_c, cy_c, col in [(int(mid_w * 0.20), int(mid_h * 0.60), (235, 95, 120)), (int(mid_w * 0.80), int(mid_h * 0.58), (245, 150, 45))]:
            mdraw.ellipse([cx_c - 55, cy_c - 55, cx_c + 55, cy_c + 55], fill=(*col, 255))
            mdraw.ellipse([cx_c - 35, cy_c - 85, cx_c + 35, cy_c - 20], fill=(*col, 255))

    else:
        # Farm / Country / Meadow
        sky = Image.new("RGBA", (sky_w, sky_h), (135, 206, 235, 255))
        sdraw = ImageDraw.Draw(sky)
        for y in range(sky_h):
            frac = y / sky_h
            c = (int(95 + 140 * frac), int(175 + 65 * frac), int(245 - 25 * frac), 255)
            sdraw.line([(0, y), (sky_w, y)], fill=c)
        sdraw.ellipse([int(sky_w * 0.2), int(sky_h * 0.12), int(sky_w * 0.2) + 130, int(sky_h * 0.12) + 130], fill=(255, 248, 190, 255))
        for cx_c, cy_c in [(int(sky_w * 0.55), int(sky_h * 0.18)), (int(sky_w * 0.8), int(sky_h * 0.25))]:
            sdraw.ellipse([cx_c - 70, cy_c - 30, cx_c + 70, cy_c + 30], fill=(255, 255, 255, 230))
            sdraw.ellipse([cx_c - 30, cy_c - 55, cx_c + 40, cy_c + 15], fill=(255, 255, 255, 240))

        mid = Image.new("RGBA", (mid_w, mid_h), (0, 0, 0, 0))
        mdraw = ImageDraw.Draw(mid)
        mdraw.ellipse([-120, int(mid_h * 0.44), mid_w + 300, mid_h + 380], fill=(70, 155, 78, 255))
        mdraw.ellipse([int(mid_w * 0.28), int(mid_h * 0.52), mid_w + 350, mid_h + 400], fill=(48, 132, 56, 255))
        bx, by = int(mid_w * 0.68), int(mid_h * 0.40)
        mdraw.rounded_rectangle([bx, by, bx + 180, by + 125], radius=10, fill=(195, 45, 45, 255))
        mdraw.polygon([(bx - 12, by), (bx + 90, by - 52), (bx + 192, by)], fill=(245, 245, 250, 255))
        mdraw.rectangle([bx + 60, by + 45, bx + 120, by + 125], fill=(240, 240, 240, 255))
        for fx in range(30, mid_w, 75):
            fy = int(mid_h * 0.62)
            mdraw.rounded_rectangle([fx, fy - 35, fx + 12, fy + 35], radius=3, fill=(225, 205, 175, 255))
        mdraw.rectangle([20, int(mid_h * 0.62) - 18, mid_w - 20, int(mid_h * 0.62) - 10], fill=(215, 195, 165, 255))

    return sky.convert("RGB"), mid


def draw_3d_character_sprite(
    char: dict,
    mouth_open: int = 0,
    is_blinking: bool = False,
    facing: str = "right",
    is_speaking: bool = False,
    t: float = 0.0,
    size: int = 560
) -> Image.Image:
    """Renders a fully animated 3D character sprite with species-specific rig, visemes, and facing direction."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = size // 2
    cy = int(size * 0.58)
    dx = 14 if facing == "right" else (-14 if facing == "left" else 0)

    name = char.get("name", "")
    species = char.get("species", "")
    anchor = char.get("visual_anchor", "")
    traits = f"{name} {species} {anchor}".lower()

    if any(k in traits for k in ["puff", "alien", "orbit", "sparkle", "blob"]):
        # ALIEN PUFF (Orbit)
        for r in range(150, 105, -9):
            glow_a = int(38 * (1.0 - (r - 105) / 45.0))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(80, 240, 230, glow_a))

        body_r = 105
        _draw_sphere(draw, cx, cy, body_r, (38, 195, 185), (180, 255, 250), steps=16)

        # Little Antenna with Golden Star
        ant_cx = cx + dx
        ant_top_x = ant_cx + dx * 2
        ant_top_y = cy - body_r - 40
        draw.line([(ant_cx, cy - body_r + 15), (ant_top_x, ant_top_y)], fill=(30, 175, 165), width=6)
        star_r = 18
        draw.ellipse([ant_top_x - star_r, ant_top_y - star_r, ant_top_x + star_r, ant_top_y + star_r], fill=(255, 235, 75))
        draw.ellipse([ant_top_x - star_r - 6, ant_top_y - star_r - 6, ant_top_x + star_r + 6, ant_top_y + star_r + 6], outline=(255, 255, 180, 160), width=4)

        # Cheerful Rosy Cheeks
        draw.ellipse([cx + dx - 65, cy + 18, cx + dx - 25, cy + 45], fill=(255, 135, 165, 190))
        draw.ellipse([cx + dx + 25, cy + 18, cx + dx + 65, cy + 45], fill=(255, 135, 165, 190))

        # Catchlight Eyes
        eye_y = cy - 10
        eye_spacing = 38
        for ex in (cx + dx - eye_spacing, cx + dx + eye_spacing):
            if is_blinking:
                draw.arc([ex - 18, eye_y - 6, ex + 18, eye_y + 12], start=195, end=345, fill=(18, 32, 45), width=4)
            else:
                draw.ellipse([ex - 22, eye_y - 25, ex + 22, eye_y + 25], fill=(16, 28, 48))
                draw.ellipse([ex - 18, eye_y - 20, ex + 18, eye_y + 20], fill=(24, 75, 140))
                draw.ellipse([ex - 14, eye_y - 18, ex - 4, eye_y - 8], fill=(255, 255, 255))
                draw.ellipse([ex + 4, eye_y + 4, ex + 10, eye_y + 10], fill=(255, 255, 255))

        # Mouth Viseme
        mouth_y = cy + 24
        if mouth_open > 2:
            draw.ellipse([cx + dx - 16, mouth_y - 2, cx + dx + 16, mouth_y + mouth_open + 8], fill=(25, 15, 28))
            draw.ellipse([cx + dx - 10, mouth_y + mouth_open - 2, cx + dx + 10, mouth_y + mouth_open + 6], fill=(245, 110, 140))
        else:
            draw.arc([cx + dx - 18, mouth_y - 8, cx + dx + 18, mouth_y + 10], start=20, end=160, fill=(20, 32, 42), width=4)

    elif any(k in traits for k in ["fox", "nova"]):
        # FOX (Nova - Space Fox)
        head_cy = cy - 75
        tail_side = -1 if facing == "right" else 1
        tx, ty = cx + tail_side * 95, cy + 45
        draw.ellipse([tx - 65, ty - 85, tx + 65, ty + 85], fill=(230, 105, 25))
        draw.ellipse([tx + tail_side * 20 - 35, ty - 75, tx + tail_side * 20 + 35, ty - 25], fill=(255, 250, 245))

        # Torso with NASA Astronaut Spacesuit
        _draw_sphere(draw, cx, cy + 70, 115, (220, 225, 238), (255, 255, 255), steps=14)
        draw.rounded_rectangle([cx - 75, cy + 15, cx + 75, cy + 45], radius=12, fill=(35, 195, 225))
        draw.ellipse([cx - 16, cy + 20, cx + 16, cy + 40], fill=(255, 215, 60))

        # Pointed Fox Ears
        for ear_x, ear_tilt in [(cx + dx - 75, -1), (cx + dx + 75, 1)]:
            draw.polygon([(ear_x - 32, head_cy - 40), (ear_x + ear_tilt * 15, head_cy - 165), (ear_x + 32, head_cy - 30)], fill=(225, 95, 20))
            draw.polygon([(ear_x - 18, head_cy - 45), (ear_x + ear_tilt * 10, head_cy - 145), (ear_x + 18, head_cy - 35)], fill=(255, 175, 185))

        # Fox Head
        _draw_sphere(draw, cx + dx, head_cy, 110, (230, 105, 25), (255, 175, 75), steps=14)
        draw.polygon([(cx + dx - 105, head_cy + 10), (cx + dx - 145, head_cy + 35), (cx + dx - 85, head_cy + 55)], fill=(255, 250, 245))
        draw.polygon([(cx + dx + 105, head_cy + 10), (cx + dx + 145, head_cy + 35), (cx + dx + 85, head_cy + 55)], fill=(255, 250, 245))

        # Eyes
        eye_y = head_cy - 12
        eye_spacing = 42
        for ex in (cx + dx - eye_spacing, cx + dx + eye_spacing):
            if is_blinking:
                draw.arc([ex - 20, eye_y - 6, ex + 20, eye_y + 12], start=195, end=345, fill=(35, 20, 15), width=4)
            else:
                draw.ellipse([ex - 22, eye_y - 26, ex + 22, eye_y + 26], fill=(255, 255, 255))
                draw.ellipse([ex - 16, eye_y - 20, ex + 16, eye_y + 20], fill=(40, 135, 225))
                draw.ellipse([ex - 9, eye_y - 12, ex + 9, eye_y + 12], fill=(12, 14, 22))
                draw.ellipse([ex - 12, eye_y - 18, ex - 4, eye_y - 10], fill=(255, 255, 255))

        # Snout & Nose
        snout_y = head_cy + 35
        _draw_sphere(draw, cx + dx, snout_y, 44, (245, 240, 235), (255, 255, 255), steps=10)
        draw.ellipse([cx + dx - 16, snout_y - 20, cx + dx + 16, snout_y - 6], fill=(30, 20, 18))
        draw.ellipse([cx + dx - 8, snout_y - 18, cx + dx - 2, snout_y - 12], fill=(255, 255, 255))

        # Mouth Viseme
        mouth_y = snout_y + 8
        if mouth_open > 2:
            draw.ellipse([cx + dx - 18, mouth_y - 2, cx + dx + 18, mouth_y + mouth_open], fill=(35, 18, 15))
            draw.ellipse([cx + dx - 9, mouth_y + mouth_open - 4, cx + dx + 9, mouth_y + mouth_open + 2], fill=(245, 110, 130))
        else:
            draw.arc([cx + dx - 20, mouth_y - 6, cx + dx + 20, mouth_y + 12], start=20, end=160, fill=(35, 20, 15), width=4)

    elif any(k in traits for k in ["bunny", "rabbit", "pippin", "chhotu", "hare"]):
        # BUNNY (Pippin / Chhotu)
        head_cy = cy - 75
        # Torso with Cozy Blue Overalls
        _draw_sphere(draw, cx, cy + 70, 115, (230, 225, 220), (252, 248, 245), steps=14)
        draw.rounded_rectangle([cx - 75, cy + 25, cx + 75, cy + 85], radius=16, fill=(65, 175, 240))

        # Long Bunny Ears
        for ear_x in (cx + dx - 55, cx + dx + 55):
            draw.rounded_rectangle([ear_x - 22, head_cy - 190, ear_x + 22, head_cy - 35], radius=22, fill=(245, 240, 235))
            draw.rounded_rectangle([ear_x - 12, head_cy - 170, ear_x + 12, head_cy - 50], radius=12, fill=(245, 175, 185))

        # Bunny Head
        _draw_sphere(draw, cx + dx, head_cy, 110, (235, 230, 225), (255, 252, 250), steps=14)
        draw.ellipse([cx + dx - 75, head_cy + 15, cx + dx - 35, head_cy + 45], fill=(255, 140, 160, 180))
        draw.ellipse([cx + dx + 35, head_cy + 15, cx + dx + 75, head_cy + 45], fill=(255, 140, 160, 180))

        # Eyes
        eye_y = head_cy - 12
        eye_spacing = 42
        for ex in (cx + dx - eye_spacing, cx + dx + eye_spacing):
            if is_blinking:
                draw.arc([ex - 20, eye_y - 6, ex + 20, eye_y + 12], start=195, end=345, fill=(35, 20, 25), width=4)
            else:
                draw.ellipse([ex - 20, eye_y - 24, ex + 20, eye_y + 24], fill=(255, 255, 255))
                draw.ellipse([ex - 15, eye_y - 18, ex + 15, eye_y + 18], fill=(60, 165, 240))
                draw.ellipse([ex - 8, eye_y - 10, ex + 8, eye_y + 10], fill=(15, 15, 25))
                draw.ellipse([ex - 11, eye_y - 15, ex - 4, eye_y - 8], fill=(255, 255, 255))

        # Pink Heart Nose & Whiskers
        snout_y = head_cy + 35
        _draw_sphere(draw, cx + dx, snout_y, 40, (250, 245, 240), (255, 255, 255), steps=10)
        draw.polygon([(cx + dx - 14, snout_y - 16), (cx + dx + 14, snout_y - 16), (cx + dx, snout_y - 4)], fill=(240, 125, 150))
        # Whiskers
        for wy in (-4, 4):
            draw.line([(cx + dx - 35, snout_y + wy), (cx + dx - 75, snout_y + wy * 2)], fill=(120, 110, 110), width=2)
            draw.line([(cx + dx + 35, snout_y + wy), (cx + dx + 75, snout_y + wy * 2)], fill=(120, 110, 110), width=2)

        mouth_y = snout_y + 8
        if mouth_open > 2:
            draw.ellipse([cx + dx - 16, mouth_y - 2, cx + dx + 16, mouth_y + mouth_open], fill=(35, 20, 25))
            draw.ellipse([cx + dx - 8, mouth_y + mouth_open - 4, cx + dx + 8, mouth_y + mouth_open + 2], fill=(245, 110, 130))
        else:
            draw.arc([cx + dx - 18, mouth_y - 6, cx + dx + 18, mouth_y + 10], start=20, end=160, fill=(35, 20, 25), width=4)

    elif any(k in traits for k in ["bear", "bhalu"]):
        # BEAR (Bhalu Bhai)
        head_cy = cy - 75
        _draw_sphere(draw, cx, cy + 70, 125, (135, 78, 40), (195, 135, 90), steps=14)
        draw.rounded_rectangle([cx - 85, cy + 20, cx + 85, cy + 60], radius=16, fill=(245, 185, 30))

        # Round Bear Ears
        for ear_x in (cx + dx - 80, cx + dx + 80):
            _draw_sphere(draw, ear_x, head_cy - 70, 42, (135, 78, 40), (195, 135, 90), steps=10)
            draw.ellipse([ear_x - 18, head_cy - 88, ear_x + 18, head_cy - 52], fill=(225, 175, 140))

        _draw_sphere(draw, cx + dx, head_cy, 115, (145, 85, 45), (205, 142, 95), steps=14)
        snout_y = head_cy + 36
        _draw_sphere(draw, cx + dx, snout_y, 48, (225, 185, 150), (255, 235, 215), steps=10)
        draw.ellipse([cx + dx - 18, snout_y - 20, cx + dx + 18, snout_y - 4], fill=(35, 22, 18))

        eye_y = head_cy - 12
        eye_spacing = 46
        for ex in (cx + dx - eye_spacing, cx + dx + eye_spacing):
            if is_blinking:
                draw.arc([ex - 20, eye_y - 6, ex + 20, eye_y + 12], start=195, end=345, fill=(35, 22, 18), width=4)
            else:
                draw.ellipse([ex - 20, eye_y - 24, ex + 20, eye_y + 24], fill=(255, 255, 255))
                draw.ellipse([ex - 15, eye_y - 18, ex + 15, eye_y + 18], fill=(45, 125, 215))
                draw.ellipse([ex - 8, eye_y - 10, ex + 8, eye_y + 10], fill=(12, 14, 20))
                draw.ellipse([ex - 11, eye_y - 15, ex - 4, eye_y - 8], fill=(255, 255, 255))

        mouth_y = snout_y + 8
        if mouth_open > 2:
            draw.ellipse([cx + dx - 18, mouth_y - 2, cx + dx + 18, mouth_y + mouth_open], fill=(35, 18, 15))
            draw.ellipse([cx + dx - 9, mouth_y + mouth_open - 4, cx + dx + 9, mouth_y + mouth_open + 2], fill=(245, 110, 130))
        else:
            draw.arc([cx + dx - 20, mouth_y - 6, cx + dx + 20, mouth_y + 12], start=20, end=160, fill=(35, 22, 18), width=4)

    elif any(k in traits for k in ["dog", "puppy", "barnaby", "hound"]):
        # DOG (Barnaby)
        head_cy = cy - 75
        _draw_sphere(draw, cx, cy + 70, 115, (195, 135, 60), (245, 190, 120), steps=14)
        draw.rounded_rectangle([cx - 80, cy + 22, cx + 80, cy + 58], radius=14, fill=(220, 65, 65))

        # Floppy Dog Ears
        draw.rounded_rectangle([cx + dx - 130, head_cy - 45, cx + dx - 75, head_cy + 85], radius=26, fill=(155, 95, 45))
        draw.rounded_rectangle([cx + dx + 75, head_cy - 45, cx + dx + 130, head_cy + 85], radius=26, fill=(155, 95, 45))

        _draw_sphere(draw, cx + dx, head_cy, 110, (205, 142, 68), (250, 195, 128), steps=14)
        snout_y = head_cy + 36
        _draw_sphere(draw, cx + dx, snout_y, 48, (245, 220, 190), (255, 245, 235), steps=10)
        draw.ellipse([cx + dx - 18, snout_y - 20, cx + dx + 18, snout_y - 4], fill=(30, 25, 25))

        eye_y = head_cy - 12
        eye_spacing = 44
        for ex in (cx + dx - eye_spacing, cx + dx + eye_spacing):
            if is_blinking:
                draw.arc([ex - 20, eye_y - 6, ex + 20, eye_y + 12], start=195, end=345, fill=(30, 25, 25), width=4)
            else:
                draw.ellipse([ex - 20, eye_y - 24, ex + 20, eye_y + 24], fill=(255, 255, 255))
                draw.ellipse([ex - 15, eye_y - 18, ex + 15, eye_y + 18], fill=(40, 140, 90))
                draw.ellipse([ex - 8, eye_y - 10, ex + 8, eye_y + 10], fill=(12, 14, 20))
                draw.ellipse([ex - 11, eye_y - 15, ex - 4, eye_y - 8], fill=(255, 255, 255))

        mouth_y = snout_y + 8
        if mouth_open > 2:
            draw.ellipse([cx + dx - 18, mouth_y - 2, cx + dx + 18, mouth_y + mouth_open], fill=(35, 18, 15))
            draw.ellipse([cx + dx - 9, mouth_y + mouth_open - 4, cx + dx + 9, mouth_y + mouth_open + 2], fill=(245, 110, 130))
        else:
            draw.arc([cx + dx - 20, mouth_y - 6, cx + dx + 20, mouth_y + 12], start=20, end=160, fill=(30, 25, 25), width=4)

    elif any(k in traits for k in ["monkey", "ape", "rooroo"]):
        # MONKEY (RooRoo Nursery style)
        head_cy = cy - 75
        # Torso with Red Dungarees
        _draw_sphere(draw, cx, cy + 70, 115, (155, 95, 55), (210, 155, 105), steps=14)
        draw.rounded_rectangle([cx - 75, cy + 25, cx + 75, cy + 85], radius=16, fill=(225, 55, 65))

        # Monkey Ears on sides
        for ear_x in (cx + dx - 95, cx + dx + 95):
            _draw_sphere(draw, ear_x, head_cy, 36, (155, 95, 55), (210, 155, 105), steps=10)
            draw.ellipse([ear_x - 16, head_cy - 16, ear_x + 16, head_cy + 16], fill=(240, 195, 165))

        _draw_sphere(draw, cx + dx, head_cy, 105, (155, 95, 55), (210, 155, 105), steps=14)
        # Peach Face Mask
        draw.ellipse([cx + dx - 65, head_cy - 40, cx + dx + 65, head_cy + 45], fill=(240, 195, 165))
        snout_y = head_cy + 25
        draw.ellipse([cx + dx - 14, snout_y - 14, cx + dx + 14, snout_y + 2], fill=(50, 30, 25))

        eye_y = head_cy - 12
        eye_spacing = 38
        for ex in (cx + dx - eye_spacing, cx + dx + eye_spacing):
            if is_blinking:
                draw.arc([ex - 18, eye_y - 6, ex + 18, eye_y + 12], start=195, end=345, fill=(35, 20, 15), width=4)
            else:
                draw.ellipse([ex - 20, eye_y - 24, ex + 20, eye_y + 24], fill=(255, 255, 255))
                draw.ellipse([ex - 15, eye_y - 18, ex + 15, eye_y + 18], fill=(70, 140, 220))
                draw.ellipse([ex - 8, eye_y - 10, ex + 8, eye_y + 10], fill=(12, 14, 20))
                draw.ellipse([ex - 11, eye_y - 15, ex - 4, eye_y - 8], fill=(255, 255, 255))

        mouth_y = snout_y + 14
        if mouth_open > 2:
            draw.ellipse([cx + dx - 16, mouth_y - 2, cx + dx + 16, mouth_y + mouth_open], fill=(35, 18, 15))
            draw.ellipse([cx + dx - 8, mouth_y + mouth_open - 4, cx + dx + 8, mouth_y + mouth_open + 2], fill=(245, 110, 130))
        else:
            draw.arc([cx + dx - 18, mouth_y - 6, cx + dx + 18, mouth_y + 10], start=20, end=160, fill=(35, 20, 15), width=4)

    else:
        # Generic Friendly 3D Cartoon Animal
        head_cy = cy - 75
        _draw_sphere(draw, cx, cy + 70, 115, (165, 110, 75), (225, 168, 128), steps=14)
        draw.rounded_rectangle([cx - 80, cy + 25, cx + 80, cy + 65], radius=16, fill=(240, 160, 45))
        for ear_x in (cx + dx - 75, cx + dx + 75):
            _draw_sphere(draw, ear_x, head_cy - 70, 38, (165, 110, 75), (225, 168, 128), steps=10)
        _draw_sphere(draw, cx + dx, head_cy, 108, (165, 110, 75), (225, 168, 128), steps=14)
        snout_y = head_cy + 34
        _draw_sphere(draw, cx + dx, snout_y, 44, (240, 205, 175), (255, 245, 235), steps=10)
        draw.ellipse([cx + dx - 16, snout_y - 18, cx + dx + 16, snout_y - 4], fill=(40, 28, 25))

        eye_y = head_cy - 12
        eye_spacing = 42
        for ex in (cx + dx - eye_spacing, cx + dx + eye_spacing):
            if is_blinking:
                draw.arc([ex - 20, eye_y - 6, ex + 20, eye_y + 12], start=195, end=345, fill=(30, 20, 15), width=4)
            else:
                draw.ellipse([ex - 20, eye_y - 24, ex + 20, eye_y + 24], fill=(255, 255, 255))
                draw.ellipse([ex - 15, eye_y - 18, ex + 15, eye_y + 18], fill=(40, 140, 220))
                draw.ellipse([ex - 8, eye_y - 10, ex + 8, eye_y + 10], fill=(12, 14, 20))
                draw.ellipse([ex - 11, eye_y - 15, ex - 4, eye_y - 8], fill=(255, 255, 255))

        mouth_y = snout_y + 8
        if mouth_open > 2:
            draw.ellipse([cx + dx - 16, mouth_y - 2, cx + dx + 16, mouth_y + mouth_open], fill=(35, 18, 15))
            draw.ellipse([cx + dx - 8, mouth_y + mouth_open - 4, cx + dx + 8, mouth_y + mouth_open + 2], fill=(245, 110, 130))
        else:
            draw.arc([cx + dx - 18, mouth_y - 6, cx + dx + 18, mouth_y + 10], start=20, end=160, fill=(35, 20, 15), width=4)

    return img


def draw_3d_scene_fallback(prompt: str, out_path: Path, aspect_ratio: str = "16:9") -> bool:
    """Renders a multi-plane 3D cartoon environment fallback scene matching the prompt's theme."""
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        w, h = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)
        sky, mid = draw_thematic_background(prompt, "", w, h)
        canvas = sky.crop((0, 0, w, h)).convert("RGBA")
        canvas.alpha_composite(mid.crop((0, 0, w, h)))
        canvas.convert("RGB").save(out_path, "JPEG", quality=90)
        return True
    except Exception as e:
        log.error("Failed to render 3D scene fallback: %s", e)
        return False


def generate_scene_frame(prompt: str, out_path: Path, aspect_ratio: str = "16:9", seed: int | None = None,
                         negative: str = "") -> bool:
    """Generates one picture through the provider chain (studio/providers.py: free cloud, your own ComfyUI or
    image API, then the local procedural painter), cropped to the exact size for the aspect ratio."""
    from studio import providers
    return providers.generate_image(" ".join(prompt.split()), out_path, aspect_ratio,
                                    negative=negative, seed=seed) is not None


def generate_character_avatar(series_id: str, character: dict, visual_style: str = "high-gloss 3D Pixar toy CGI") -> Path | None:
    """Generates a high-quality 3D character portrait in the series character vault (supports humans, animals, sci-fi)."""
    from studio import config
    sid = series_id
    cid = character.get("id") or character.get("name", "character").lower().replace(" ", "-")
    out_dir = config.DATA_DIR / "series" / sid / "characters"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{cid}.jpg"

    char_name = character.get("name", "Character")
    species = character.get("species", "Character")
    visual = character.get("visual_anchor") or f"3D character {char_name}, expressive eyes, detailed attire"

    # 1. Try real AI image generation for true 3D character design portrait
    from studio import providers
    prompt = f"Character portrait of {char_name}, {species}, {visual}. {visual_style}. Character design sheet, centered close-up portrait, plain background"
    # real image services only: when none answers, the drawn cartoon avatar below beats a drawn landscape
    chain = [n for n in providers.image_chain() if n != "procedural"]
    ok = bool(chain) and providers.generate_image(prompt, out_file, "1:1", seed=providers.stable_seed(sid, cid),
                                                  chain=chain) is not None
    if ok and out_file.is_file() and out_file.stat().st_size > 5000:
        return out_file

    # 2. Try procedural 3D cartoon avatar as secondary fallback
    success = draw_3d_cartoon_avatar(
        name=char_name,
        species=species,
        visual_anchor=visual,
        out_path=out_file,
        width=1024,
        height=768
    )
    if success:
        return out_file

    # 3. Tertiary fallback
    if draw_3d_scene_fallback(f"3D character {char_name}", out_file):
        return out_file
    return None


def render_parallax_motion(
    image_path: Path,
    audio_path: Path | None,
    out_mp4: Path,
    duration: float,
    motion: str = "dolly_in",
    aspect_ratio: str = "16:9"
) -> bool:
    """Renders a static 3D keyframe with dynamic camera motion into a video clip with audio."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    w, h = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)
    fps = 30
    total_frames = max(30, int(round(duration * fps)))

    if motion == "pan_left":
        vf = f"scale=4000:-1,zoompan=z=1.12:x='max(0,iw*0.10*(1-on/{total_frames}))':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}"
    elif motion == "pan_right":
        vf = f"scale=4000:-1,zoompan=z=1.12:x='min(iw*0.10,iw*0.10*(on/{total_frames}))':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}"
    elif motion == "depth_zoom":
        vf = f"scale=4000:-1,zoompan=z='min(zoom+0.0020,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}"
    else:  # dolly_in
        vf = f"scale=4000:-1,zoompan=z='min(zoom+0.0010,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps={fps}"

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-loop", "1", "-i", str(image_path)
    ]

    if audio_path and audio_path.is_file():
        cmd += ["-i", str(audio_path)]
        cmd += [
            "-filter_complex", f"[0:v]{vf},format=yuv420p[v];[1:a]apad=whole_dur={duration:.2f}[aout]",
            "-map", "[v]", "-map", "[aout]"
        ]
    else:
        cmd += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration:.2f}"]
        cmd += [
            "-filter_complex", f"[0:v]{vf},format=yuv420p[v]",
            "-map", "[v]", "-map", "1:a:0"
        ]

    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-t", f"{duration:.2f}",
        str(out_mp4)
    ]

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW, timeout=120)
        return p.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000
    except Exception as e:
        log.error("FFmpeg parallax motion render error: %s", e)
        return False


def render_3d_animated_scene(
    characters: list[dict] | None = None,
    speaker_name: str = "Character",
    setting: str = "3D Animated World",
    visual_style: str = "3D Pixar CGI",
    audio_path: Path | None = None,
    out_mp4: Path = Path("scene.mp4"),
    duration: float = 5.0,
    motion: str = "dolly_in",
    aspect_ratio: str = "16:9",
    character_name: str = "",
    character_species: str = "",
    visual_anchor: str = ""
) -> bool:
    """Renders a true 3D animated scene with multi-character two-shot conversation staging,
    thematic 3D environments (Space, Forest, Farm, Indoor), multi-plane depth parallax,
    audio-synchronized mouth visemes, and species-specific 3D rigs (Fox, Alien Puff, Bunny, Bear, Dog, Monkey).
    """
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    w, h = (1920, 1080) if aspect_ratio == "16:9" else (1080, 1920)
    fps = 24
    total_frames = max(24, int(round(duration * fps)))

    # 1. Prepare character rigs
    if not characters:
        characters = [{
            "name": character_name or speaker_name,
            "species": character_species or "Character",
            "visual_anchor": visual_anchor
        }]

    char_left = characters[0]
    char_right = characters[1] if len(characters) >= 2 else None

    # Determine speaker side
    sp_clean = (speaker_name or "").strip().lower()
    left_name = char_left.get("name", "").strip().lower()
    right_name = char_right.get("name", "").strip().lower() if char_right else ""

    if char_right:
        if sp_clean == left_name:
            speaker_side = "left"
        elif sp_clean == right_name:
            speaker_side = "right"
        else:
            speaker_side = "narrator"
    else:
        speaker_side = "left" if sp_clean == left_name else "narrator"

    # 2. Generate Thematic 3D Background Layers
    sky, mid = draw_thematic_background(setting, visual_style, w, h)

    # 3. Setup Character Staging & Sizing
    sprite_sz = 560 if aspect_ratio == "16:9" else 480
    is_orbit_left = any(k in f"{char_left.get('name','')} {char_left.get('species','')}".lower() for k in ["puff", "orbit", "alien"])
    is_orbit_right = any(k in f"{char_right.get('name','')} {char_right.get('species','')}".lower() for k in ["puff", "orbit", "alien"]) if char_right else False

    if aspect_ratio == "16:9":
        if char_right:
            base_x_left = int(w * 0.28) - sprite_sz // 2
            base_y_left = int(h * 0.72) - sprite_sz // 2
            base_x_right = int(w * 0.72) - sprite_sz // 2
            base_y_right = (int(h * 0.54) if is_orbit_right else int(h * 0.72)) - sprite_sz // 2
        else:
            base_x_left = int(w * 0.50) - sprite_sz // 2
            base_y_left = int(h * 0.70) - sprite_sz // 2
            base_x_right, base_y_right = 0, 0
    else:  # 9:16 vertical
        if char_right:
            base_x_left = int(w * 0.32) - sprite_sz // 2
            base_y_left = int(h * 0.64) - sprite_sz // 2
            base_x_right = int(w * 0.68) - sprite_sz // 2
            base_y_right = (int(h * 0.52) if is_orbit_right else int(h * 0.64)) - sprite_sz // 2
        else:
            base_x_left = int(w * 0.50) - sprite_sz // 2
            base_y_left = int(h * 0.64) - sprite_sz // 2
            base_x_right, base_y_right = 0, 0

    # 4. Setup FFmpeg video writer
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
        "-i", "-"
    ]
    if audio_path and audio_path.is_file():
        cmd += [
            "-i", str(audio_path),
            "-filter_complex", f"[1:a]apad=whole_dur={duration:.2f}[aout]",
            "-map", "0:v", "-map", "[aout]"
        ]
    else:
        cmd += [
            "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration:.2f}",
            "-map", "0:v", "-map", "1:a:0"
        ]

    cmd += [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
        "-pix_fmt", "yuv420p",
        "-shortest",
        str(out_mp4)
    ]

    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, creationflags=NO_WINDOW)
    except Exception as e:
        log.error("Failed to spawn FFmpeg 3D animator: %s", e)
        return False

    actor_desc = f"{char_left.get('name')} & {char_right.get('name')}" if char_right else char_left.get("name")
    log.info("Rendering %d 3D animated frames for '%s' (speaker: %s, %s, %.1fs)...",
             total_frames, actor_desc, speaker_name, motion, duration)

    # 5. Generate Animated Frames
    try:
        for f_idx in range(total_frames):
            t = f_idx / fps
            prog = f_idx / max(1, total_frames - 1)

            # Camera 3D Multi-plane Parallax
            if motion == "pan_left":
                bg_shift = int(35 * (1.0 - prog))
                mg_shift = int(85 * (1.0 - prog))
            elif motion == "pan_right":
                bg_shift = int(35 * prog)
                mg_shift = int(85 * prog)
            else:  # dolly_in / depth_zoom
                bg_shift = int(20 * prog)
                mg_shift = int(55 * prog)

            # Speech Visemes
            is_speaking_time = (t < duration - 0.35)
            viseme_amp = max(0, int(15 * abs(math.sin(t * 13.0)) * math.cos(t * 2.8))) if is_speaking_time else 0

            # Independent Eye Blinks
            blink_left = (0.0 <= (t % 2.7) <= 0.12)
            blink_right = (0.0 <= ((t + 1.2) % 2.9) <= 0.12)

            # Bounces & Sway
            if speaker_side == "left":
                bounce_left = int(6.0 * abs(math.sin(t * 11.0)))
                mouth_left = viseme_amp
                spk_left = True
            else:
                bounce_left = int(4.0 * math.sin(t * 2.8))
                mouth_left = 0
                spk_left = False

            if speaker_side == "right":
                bounce_right = int(6.0 * abs(math.sin(t * 11.0)))
                mouth_right = viseme_amp
                spk_right = True
            else:
                bounce_right = int(4.0 * math.sin(t * 2.8 + 1.2))
                mouth_right = 0
                spk_right = False

            orbit_float = int(14.0 * math.sin(t * 3.4))

            # Render Character Sprites
            left_facing = "right" if char_right else "front"
            left_sprite = draw_3d_character_sprite(
                char_left,
                mouth_open=mouth_left,
                is_blinking=blink_left,
                facing=left_facing,
                is_speaking=spk_left,
                t=t,
                size=sprite_sz
            )

            right_sprite = None
            if char_right:
                right_sprite = draw_3d_character_sprite(
                    char_right,
                    mouth_open=mouth_right,
                    is_blinking=blink_right,
                    facing="left",
                    is_speaking=spk_right,
                    t=t,
                    size=sprite_sz
                )

            # Composite Layers:
            # 1. Sky with Parallax
            cur_sky = sky.crop((bg_shift, 0, bg_shift + w, h)).convert("RGBA")

            # 2. Midground Parallax
            cur_mid = mid.crop((mg_shift, 0, mg_shift + w, h))
            cur_sky.alpha_composite(cur_mid, (0, 0))

            # 3. Foreground Characters
            l_y = base_y_left + bounce_left + (orbit_float if is_orbit_left else 0)
            cur_sky.alpha_composite(left_sprite, (base_x_left, l_y))

            if char_right and right_sprite:
                r_y = base_y_right + bounce_right + (orbit_float if is_orbit_right else 0)
                cur_sky.alpha_composite(right_sprite, (base_x_right, r_y))

            # Send frame to FFmpeg
            raw_rgb = cur_sky.convert("RGB").tobytes()
            try:
                proc.stdin.write(raw_rgb)
            except (BrokenPipeError, OSError):
                break

        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait(timeout=120)
        ok = (proc.returncode == 0 and out_mp4.is_file() and out_mp4.stat().st_size > 1000)
        if ok:
            log.info("3D animated scene render complete: %s (%d bytes)", out_mp4, out_mp4.stat().st_size)
        return ok
    except Exception as e:
        log.error("Failed during 3D animated scene render: %s", e)
        if proc and proc.stdin:
            try: proc.stdin.close()
            except: pass
        return False
