"""Render the hero background: luminous ribbons of light flowing across a dark field.

Original artwork generated procedurally (numpy + Pillow), so there are no licensing concerns.
Not part of the site build; requires numpy and Pillow. Re-run only to change the artwork.
Usage: python3 tools/render_hero.py src/assets/img
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 2560, 1440
SS = 2                      # supersampling for anti-aliased lines
rng = np.random.default_rng(7)


def ribbon(n, base, amp, width, phase, k, twist, x0=-0.1, x1=1.1, intensity=1.0, line=1):
    """Accumulate a twisting ribbon made of ``n`` thin curves. Coordinates are normalized."""
    acc = np.zeros((H, W), np.float32)
    xs = np.linspace(x0, x1, 900)
    centre = base + amp * np.sin(k * xs * np.pi + phase) + 0.35 * amp * np.sin(2.3 * k * xs * np.pi + phase * 1.7)
    half_w = width * (0.25 + 0.75 * np.abs(np.sin(twist * xs * np.pi + phase * 0.6)))
    for i in range(n):
        t = i / (n - 1) - 0.5
        ys = centre + half_w * t * 2 + 0.004 * np.sin(9 * xs + i)
        layer = Image.new("L", (W * SS, H * SS), 0)
        draw = ImageDraw.Draw(layer)
        pts = list(zip((xs * W * SS).tolist(), (ys * H * SS).tolist()))
        edge = 1 - abs(t) * 1.6                     # brighter in the middle of the ribbon
        draw.line(pts, fill=int(255 * max(edge, 0.15)), width=line * SS, joint="curve")
        acc += np.asarray(layer.resize((W, H), Image.LANCZOS), np.float32) / 255.0
    return acc * intensity / n * 9, (xs, centre, half_w)


def blur(a, r):
    img = Image.fromarray(np.clip(a / max(a.max(), 1e-6) * 255, 0, 255).astype(np.uint8))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(r)), np.float32) / 255.0 * a.max()


main, geo = ribbon(80, base=0.68, amp=0.13, width=0.12, phase=0.4, k=1.15, twist=1.3, intensity=4.0)
second, _ = ribbon(50, base=0.78, amp=0.10, width=0.07, phase=2.2, k=0.9, twist=1.8, intensity=2.0)
upper, _ = ribbon(30, base=0.24, amp=0.06, width=0.04, phase=4.0, k=0.8, twist=1.1, intensity=0.45)
lines = main + second + upper

glow = 0.9 * blur(lines, 6) + 0.8 * blur(lines, 24) + 0.6 * blur(lines, 80)
light = lines * 0.85 + glow

# Colour: deep blue on the left drifting to cyan on the right, white where light is strongest
x = np.linspace(0, 1, W)[None, :]
c_low = np.stack([0.10 + 0.05 * x, 0.32 + 0.30 * x, 0.95 + 0.0 * x], -1)    # blue → azure
c_high = np.array([0.80, 0.93, 1.0])
mix = np.clip(light / 1.6, 0, 1)[..., None]
rgb = light[..., None] * (c_low * (1 - mix) + c_high * mix)

# Background: near-black with a faint navy glow behind the ribbons
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
g = np.exp(-(((xx / W - 0.6) / 0.55) ** 2 + ((yy / H - 0.75) / 0.35) ** 2))
bg = np.stack([0.012 + 0.03 * g, 0.020 + 0.06 * g, 0.045 + 0.14 * g], -1)

# Sparkles along the main ribbon
spark = np.zeros((H, W), np.float32)
gx, gc, gw = geo
for _ in range(22):
    j = rng.integers(60, len(gx) - 60)
    sx = gx[j]; sy = gc[j] + gw[j] * rng.uniform(-0.8, 0.8)
    if 0 < sx < 1 and 0 < sy < 1:
        spark[int(sy * H), int(sx * W)] = rng.uniform(4, 14)
spark = blur(spark, 1.5) * 3 + blur(spark, 7)
rgb += spark[..., None] * np.array([0.75, 0.9, 1.0]) * (lines.mean() > 0)

img = 1 - np.exp(-(bg + rgb) * 1.6)                 # soft tone mapping keeps highlights smooth
# Vignette + darker top-centre band so the headline stays readable
vign = 1 - 0.55 * (((xx / W - 0.5) * 1.3) ** 2 + ((yy / H - 0.55) * 1.1) ** 2)
text_band = 1 - 0.45 * np.exp(-(((xx / W - 0.5) / 0.38) ** 2 + ((yy / H - 0.38) / 0.18) ** 2))
img *= (vign * text_band)[..., None]
img += rng.normal(0, 1.2 / 255, img.shape)            # grain to avoid banding

out = Image.fromarray(np.clip(img * 255, 0, 255).astype(np.uint8))
dst = Path(sys.argv[1])
out.save(dst / "hero-bg.webp", quality=86, method=6)
# Portrait crop for phones (keeps the bright right-centre of the ribbons)
crop = out.crop((int(W * 0.30), 0, int(W * 0.30) + 1080, H)).resize((810, 1080), Image.LANCZOS)
crop.save(dst / "hero-bg-portrait.webp", quality=84, method=6)
print("done", [(p.name, p.stat().st_size // 1024) for p in sorted(dst.glob("hero-bg*.webp"))])
