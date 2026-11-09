"""Render the illustrative scene images used on the home page.

These are *generated example images* (simple numpy ray tracer + procedural textures).
They stand in until real photos are available and are labelled as such on the site.
Not part of the site build; requires numpy and Pillow.

Usage: python3 tools/render_scenes.py src/assets/img/scenes
Writes <name>-<width>.webp for each scene plus scenes.json with annotation positions (%).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

EPS = 1e-4
INF = np.float32(1e9)
rng = np.random.default_rng(11)


# ----------------------------------------------------------------------------- math helpers
def norm(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-9)


def camera_rays(w, h, eye, target, fov_deg):
    eye, target = np.array(eye, np.float32), np.array(target, np.float32)
    fwd = norm(target - eye)
    right = norm(np.cross(fwd, [0, 1, 0]))
    up = np.cross(right, fwd)
    aspect = w / h
    half = np.tan(np.radians(fov_deg) / 2)
    xs = (np.arange(w, dtype=np.float32) + 0.5) / w * 2 - 1
    ys = 1 - (np.arange(h, dtype=np.float32) + 0.5) / h * 2
    px, py = np.meshgrid(xs * half * aspect, ys * half)
    d = norm(fwd + px[..., None] * right + py[..., None] * up)
    o = np.broadcast_to(eye, d.shape).copy()
    cam = dict(eye=eye, fwd=fwd, right=right, up=up, half=half, aspect=aspect)
    return o.reshape(-1, 3), d.reshape(-1, 3), cam


def project(cam, p):
    """3D point → (x%, y%) on the image."""
    v = np.array(p, np.float32) - cam["eye"]
    z = v @ cam["fwd"]
    x = (v @ cam["right"]) / (z * cam["half"] * cam["aspect"])
    y = (v @ cam["up"]) / (z * cam["half"])
    return round(float((x + 1) / 2 * 100), 1), round(float((1 - y) / 2 * 100), 1)


# ----------------------------------------------------------------------------- primitives
class Cylinder:
    def __init__(self, center, radius, half_len, axis, mat, emissive_ring=None):
        self.c = np.array(center, np.float32)
        self.r, self.h, self.a, self.mat = radius, half_len, axis, mat
        self.u, self.v = [i for i in range(3) if i != axis]
        self.ring = emissive_ring            # (inner r, outer r) on the -axis cap → emissive

    def hit(self, o, d):
        oc = o - self.c
        a_, u, v = self.a, self.u, self.v
        A = d[:, u] ** 2 + d[:, v] ** 2
        B = 2 * (oc[:, u] * d[:, u] + oc[:, v] * d[:, v])
        C = oc[:, u] ** 2 + oc[:, v] ** 2 - self.r ** 2
        disc = B * B - 4 * A * C
        ok = (disc > 0) & (A > 1e-9)
        sq = np.sqrt(np.where(ok, disc, 0))
        t = np.full(len(o), INF, np.float32)
        n = np.zeros_like(o)
        kind = np.zeros(len(o), np.int8)
        for tc in ((-B - sq) / (2 * A + 1e-12), (-B + sq) / (2 * A + 1e-12)):
            axial = oc[:, a_] + tc * d[:, a_]
            m = ok & (tc > EPS) & (np.abs(axial) <= self.h) & (tc < t)
            t = np.where(m, tc, t)
            kind = np.where(m, 1, kind)
        for s in (-1, 1):
            with np.errstate(divide="ignore", invalid="ignore"):
                tc = (s * self.h - oc[:, a_]) / d[:, a_]
            pu, pv = oc[:, u] + tc * d[:, u], oc[:, v] + tc * d[:, v]
            m = np.isfinite(tc) & (tc > EPS) & (pu ** 2 + pv ** 2 <= self.r ** 2) & (tc < t)
            t = np.where(m, tc, t)
            kind = np.where(m, 2 if s < 0 else 3, kind)
        p = o + t[:, None] * d
        side = p - self.c
        side[:, a_] = 0
        n = norm(side)
        cap = kind >= 2
        n[cap] = 0
        n[cap, a_] = np.where(kind[cap] == 2, -1, 1)
        local = (p - self.c)[:, a_]
        bev = 0.08 * min(self.r, self.h)
        rr = np.sqrt(side[:, u] ** 2 + side[:, v] ** 2)
        radial = norm(side)
        w_cap = np.clip(1 - (self.r - rr) / bev, 0, 1) ** 2 * cap          # cap near rim → tilt outward
        w_side = np.clip(1 - (self.h - np.abs(local)) / bev, 0, 1) ** 2 * (~cap)   # side near cap → tilt along axis
        n = n + radial * w_cap[:, None] * 1.2
        n[:, a_] += np.sign(local) * w_side * 1.2
        n = norm(n)
        emis = np.zeros(len(o), bool)
        if self.ring:
            rr = np.sqrt(side[:, u] ** 2 + side[:, v] ** 2)
            emis = (kind == 2) & (rr >= self.ring[0]) & (rr <= self.ring[1])
        return t, n, local, emis


class Box:
    def __init__(self, mn, mx, mat, emissive_top=False):
        self.mn, self.mx = np.array(mn, np.float32), np.array(mx, np.float32)
        self.mat, self.emissive_top = mat, emissive_top

    def hit(self, o, d):
        with np.errstate(divide="ignore", invalid="ignore"):
            inv = 1 / np.where(np.abs(d) < 1e-9, 1e-9, d)
        t1, t2 = (self.mn - o) * inv, (self.mx - o) * inv
        tmin3, tmax3 = np.minimum(t1, t2), np.maximum(t1, t2)
        tmin, tmax = tmin3.max(1), tmax3.min(1)
        m = (tmax >= np.maximum(tmin, EPS))
        t = np.where(m, np.where(tmin > EPS, tmin, tmax), INF).astype(np.float32)
        ax = tmin3.argmax(1)
        n = np.zeros_like(o)
        n[np.arange(len(o)), ax] = -np.sign(d[np.arange(len(o)), ax])
        p = o + t[:, None] * d
        bev = 0.06 * float(np.min(self.mx - self.mn))       # rounded-edge look: tilt normals near edges
        for k in range(3):
            lo, hi = p[:, k] - self.mn[k], self.mx[k] - p[:, k]
            dist = np.minimum(lo, hi)
            wgt = np.clip(1 - dist / max(bev, 1e-6), 0, 1) ** 2 * (ax != k)
            n[:, k] += np.where(lo < hi, -1, 1) * wgt * 1.2
        n = norm(n)
        emis = np.zeros(len(o), bool)
        if self.emissive_top:
            emis = (ax == 1) & (n[:, 1] > 0)
        return t, n, p[:, 0], emis


class Floor:
    def __init__(self, y, mat):
        self.y, self.mat = y, mat

    def hit(self, o, d):
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (self.y - o[:, 1]) / d[:, 1]
        t = np.where(np.isfinite(t) & (t > EPS), t, INF).astype(np.float32)
        n = np.zeros_like(o)
        n[:, 1] = 1
        p = o + t[:, None] * d
        return t, n, p[:, 0], np.zeros(len(o), bool)


class Film:
    """Transparent quad: p0 + s*e1 + t*e2, s,t in [0,1]."""

    def __init__(self, p0, e1, e2):
        self.p0, self.e1, self.e2 = (np.array(v, np.float32) for v in (p0, e1, e2))
        self.n = norm(np.cross(self.e1, self.e2))

    def hit(self, o, d):
        den = d @ self.n
        with np.errstate(divide="ignore", invalid="ignore"):
            t = ((self.p0 - o) @ self.n) / den
        p = o + t[:, None] * d - self.p0
        s = p @ self.e1 / (self.e1 @ self.e1)
        q = p @ self.e2 / (self.e2 @ self.e2)
        m = np.isfinite(t) & (t > EPS) & (s >= 0) & (s <= 1) & (q >= 0) & (q <= 1)
        return np.where(m, t, INF).astype(np.float32), s


# ----------------------------------------------------------------------------- shading
def env(dirs, strips=(0.35, 0.85, 1.25), warm=0.0):
    """Studio/factory environment: soft sky + overhead strip lights."""
    y = np.clip(dirs[:, 1], -1, 1)
    base = 0.18 + 0.62 * np.clip(y * 0.5 + 0.5, 0, 1) ** 1.6
    ang = np.arctan2(dirs[:, 2], np.maximum(dirs[:, 1], 1e-3))
    light = sum(np.exp(-((ang - a) / 0.07) ** 2) for a in strips) * np.clip(y, 0, 1) * 1.6
    col = (base + light)[:, None] * np.array([0.93, 0.96, 1.0], np.float32)
    col += warm * np.clip(-y, 0, 1)[:, None] * np.array([0.05, 0.04, 0.03])
    return col


MATS = {
    # albedo, kind
    "steel": ((0.80, 0.82, 0.85), "metal"),
    "iron": ((0.16, 0.19, 0.24), "paint"),
    "frame": ((0.80, 0.81, 0.82), "paint"),
    "rail": ((0.30, 0.32, 0.35), "paint"),
    "dark": ((0.10, 0.11, 0.12), "paint"),
    "white": ((0.86, 0.87, 0.88), "plastic"),
    "black": ((0.03, 0.03, 0.035), "plastic"),
    "brass": ((0.78, 0.62, 0.30), "metal"),
    "floor": ((0.55, 0.57, 0.60), "paint"),
    "alu": ((0.70, 0.72, 0.75), "metal"),
    "anod": ((0.07, 0.075, 0.08), "plastic"),
}


def render(w, h, eye, target, fov, prims, films=(), light_dir=(-0.4, 1.0, 0.55),
           bg=None, film_wrap=None, focus=None, strips=(0.35, 0.85, 1.25), emissive=(0.95, 0.98, 1.0), ao_dist=0.35):
    o, d, cam = camera_rays(w, h, eye, target, fov)
    N = len(o)
    t = np.full(N, INF, np.float32)
    n = np.zeros((N, 3), np.float32)
    local = np.zeros(N, np.float32)
    mat = np.full(N, -1, np.int16)
    emis = np.zeros(N, bool)
    for i, pr in enumerate(prims):
        ti, ni, li, ei = pr.hit(o, d)
        m = ti < t
        t, n[m], local, mat, emis = np.where(m, ti, t), ni[m], np.where(m, li, local), np.where(m, i, mat), np.where(m, ei, emis)

    hit = t < INF
    p = o + np.where(hit, t, 0)[:, None] * d
    L = norm(np.array(light_dir, np.float32))[None, :]

    # soft shadows: jittered light directions
    so = (p + n * 2e-3)[hit]
    occl = np.zeros(len(so), np.float32)
    jit = rng.normal(0, 0.06, (5, 3)).astype(np.float32)
    for j in jit:
        lj = norm(L[0] + j)
        blocked = np.zeros(len(so), bool)
        for pr in prims:
            if isinstance(pr, Floor):
                continue
            blocked |= pr.hit(so, np.broadcast_to(lj, so.shape))[0] < INF
        occl += blocked
    shadow = np.ones(N, np.float32)
    shadow[hit] = 1 - 0.62 * occl / len(jit)

    # ambient occlusion: short hemisphere rays around the normal
    ao = np.ones(N, np.float32)
    nh = n[hit]
    tang = norm(np.cross(nh, np.where(np.abs(nh[:, 1:2]) < 0.9, [[0, 1, 0]], [[1, 0, 0]])))
    bit = np.cross(nh, tang)
    acc = np.zeros(len(so), np.float32)
    K = 6
    for k in range(K):
        phi, r2 = 2 * np.pi * (k + 0.5) / K, (k % 3 + 0.5) / 3
        dirv = norm(tang * np.cos(phi) * np.sqrt(r2) + bit * np.sin(phi) * np.sqrt(r2) + nh * np.sqrt(1 - r2))
        near = np.zeros(len(so), bool)
        for pr in prims:
            near |= pr.hit(so, dirv)[0] < ao_dist
        acc += near
    ao[hit] = 1 - 0.75 * acc / K

    col = np.zeros((N, 3), np.float32)
    refl = norm(d - 2 * np.sum(d * n, 1, keepdims=True) * n)
    ndl = np.clip(np.sum(n * L, 1), 0, 1)
    spec = np.clip(np.sum(refl * L, 1), 0, 1)
    sky = np.clip(n[:, 1] * 0.5 + 0.5, 0, 1)
    brush = np.interp(local * 220, np.arange(4096), rng.normal(0, 1, 4096)) * 0.5 + \
        np.interp(local * 37, np.arange(4096), rng.normal(0, 1, 4096))
    for i, pr in enumerate(prims):
        m = hit & (mat == i)
        if not m.any():
            continue
        alb, kind = MATS[pr.mat]
        alb = np.array(alb, np.float32)
        cosv = np.clip(-np.sum(d[m] * n[m], 1), 0, 1)
        fres = (0.04 + 0.96 * (1 - cosv) ** 5)[:, None]
        occ = ao[m, None]
        if kind == "metal":
            c = env(refl[m], strips) * alb * (0.93 + 0.03 * brush[m])[:, None]
            c *= (0.6 + 0.4 * shadow[m])[:, None] * (0.45 + 0.55 * occ)
            c += alb * 0.08 * ndl[m, None]
        elif kind == "plastic":
            c = alb * (0.34 * sky[m, None] * occ + 0.78 * (ndl[m] * shadow[m])[:, None])
            c += (0.30 * spec[m] ** 50 * shadow[m])[:, None] + (0.03 + 0.25 * fres) * env(refl[m], strips) * occ
        else:
            c = alb * (0.36 * sky[m, None] * occ + 0.70 * (ndl[m] * shadow[m])[:, None])
            c += (0.08 * spec[m] ** 24 * shadow[m])[:, None] + (0.02 + 0.2 * fres) * env(refl[m], strips) * occ
            if isinstance(pr, Floor):
                c += 0.08 * env(refl[m], strips) * occ
        col[m] = c
    col[hit & emis] = np.array(emissive, np.float32) * 1.6

    # film wrapped on a cylinder (shell) and film quads
    if film_wrap:
        cyl, xr, (a0, a1) = film_wrap
        m = hit & (mat == prims.index(cyl))
        rel = p - cyl.c
        ang = np.degrees(np.arctan2(rel[:, 2], rel[:, 1]))
        mw = m & (p[:, 0] >= xr[0]) & (p[:, 0] <= xr[1]) & (ang >= a0) & (ang <= a1)
        col[mw] = col[mw] * 0.86 + env(refl[mw], strips) * 0.10 + np.array([0.01, 0.02, 0.03])
    depth = np.where(hit, t, 60.0)
    for f in films:
        tf, s = f.hit(o, d)
        m = tf < depth
        if not m.any():
            continue
        cosi = np.abs(np.sum(d[m] * f.n, 1))
        fres = 0.04 + 0.96 * (1 - cosi) ** 5
        fr = norm(d[m] - 2 * np.sum(d[m] * f.n, 1, keepdims=True) * f.n)
        behind = np.where(hit[m, None], col[m], 0)
        edge = np.exp(-((np.minimum(s[m], 1 - s[m])) / 0.004) ** 2)[:, None] * 0.45
        col[m] = behind * (0.84 - 0.3 * fres[:, None]) + env(fr, strips) * (0.10 + fres[:, None] * 1.1) + edge \
            + np.array([0.012, 0.03, 0.055])
        depth = np.where(m, tf, depth)

    img = col.reshape(h, w, 3)
    bgm = (~hit).reshape(h, w)
    if bg is not None:
        img[bgm] = bg[bgm]
    return img, depth.reshape(h, w), cam


# ----------------------------------------------------------------------------- post
def bokeh_background(w, h, base_top, base_bottom, lights=60, seed=3, warm=0.0):
    r = np.random.default_rng(seed)
    yy = np.linspace(0, 1, h)[:, None, None]
    img = np.array(base_top) * (1 - yy) + np.array(base_bottom) * yy
    img = np.broadcast_to(img, (h, w, 3)).astype(np.float32).copy()
    layer = Image.new("L", (w, h), 0)
    from PIL import ImageDraw
    dr = ImageDraw.Draw(layer)
    for _ in range(lights):
        x, y, rad = r.uniform(0, w), r.uniform(0, h * 0.6), r.uniform(w * 0.004, w * 0.016)
        dr.ellipse((x - rad, y - rad, x + rad, y + rad), fill=int(r.uniform(40, 140)))
    for _ in range(8):                                     # long overhead light bars
        x, y = r.uniform(0, w), r.uniform(0, h * 0.25)
        dr.rectangle((x, y, x + w * r.uniform(0.05, 0.14), y + h * 0.008), fill=200)
    lay = np.asarray(layer.filter(ImageFilter.GaussianBlur(w * 0.004)), np.float32)[..., None] / 255
    img += lay * np.array([0.95, 0.97, 1.0]) * 0.6
    return img


def finish(img, depth, focus, max_blur, vignette=0.25, exposure=1.0):
    img = np.clip(img * exposure, 0, None)
    srgb = np.clip(img, 0, 1) ** (1 / 2.2)
    im8 = Image.fromarray((srgb * 255).astype(np.uint8))
    if focus is not None:                                  # depth of field by layered blur
        out = np.asarray(im8, np.float32)
        coc = np.clip(np.abs(depth - focus[0]) / focus[1], 0, 1)
        acc, prev = out.copy(), out
        for k, r in enumerate((0.33, 0.66, 1.0)):
            b = np.asarray(im8.filter(ImageFilter.GaussianBlur(max_blur * r)), np.float32)
            wgt = np.clip((coc - k / 3) * 3, 0, 1)[..., None]
            acc = acc * (1 - wgt) + b * wgt
        im8 = Image.fromarray(np.clip(acc, 0, 255).astype(np.uint8))
    a = np.asarray(im8, np.float32) / 255
    bright = Image.fromarray((np.clip(a - 0.82, 0, 1) / 0.18 * 255).astype(np.uint8))
    a = a + np.asarray(bright.filter(ImageFilter.GaussianBlur(a.shape[1] * 0.01)), np.float32)[..., None] / 255 * 0.35 \
        if bright.mode == "L" else a + np.asarray(bright.filter(ImageFilter.GaussianBlur(a.shape[1] * 0.01)), np.float32) / 255 * 0.35
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    v = 1 - vignette * (((xx / w - 0.5) * 1.2) ** 2 + ((yy / h - 0.5) * 1.2) ** 2)
    a = a * v[..., None] + rng.normal(0, 1.0 / 255, a.shape)
    return Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8))


def save(img: Image.Image, out: Path, name: str, widths):
    for wdt in widths:
        hgt = round(img.height * wdt / img.width)
        img.resize((wdt, hgt), Image.LANCZOS).save(out / f"{name}-{wdt}.webp", quality=84, method=6)


# ----------------------------------------------------------------------------- scenes
def scene_line(W, H):
    """Roll-to-roll line: film running over steel guide rolls, machine frame on the left."""
    rollA = Cylinder((1.6, 1.0, 0.0), 0.55, 3.4, 0, "steel")
    rollB = Cylinder((1.6, 1.62, -3.4), 0.40, 3.4, 0, "steel")
    rollC = Cylinder((1.6, 1.15, -6.4), 0.34, 3.4, 0, "steel")
    prims = [
        Floor(0.0, "floor"), rollA, rollB, rollC,
        Cylinder((-1.95, 1.0, 0.0), 0.13, 0.18, 0, "steel"),                # shafts into the frame
        Cylinder((-1.95, 1.62, -3.4), 0.11, 0.18, 0, "steel"),
        Box((-2.45, 0.0, -8.0), (-2.2, 2.75, 1.4), "frame"),                # side frame plate
        Box((-2.2, 0.66, -0.36), (-1.9, 1.34, 0.36), "iron"),               # bearing housings
        Box((-2.2, 1.36, -3.66), (-1.9, 1.88, -3.14), "iron"),
        Box((-2.2, 0.92, -6.62), (-1.9, 1.38, -6.18), "iron"),
        Box((-2.2, 0.0, -1.2), (5.4, 0.32, 1.2), "rail"),                   # base rail
        Box((5.6, 0.0, -9.5), (8.0, 2.4, -7.0), "frame"),                   # cabinet far right
    ]
    for (y, z) in ((0.76, 0.24), (1.24, 0.24), (0.76, -0.24), (1.24, -0.24)):
        prims.append(Cylinder((-1.88, y, z), 0.038, 0.02, 0, "steel"))      # housing bolts
    films = [
        Film((-1.75, 1.49, -6.4), (6.9, 0, 0), (0, 0.53, 3.0)),            # C → B
        Film((-1.75, 2.02, -3.4), (6.9, 0, 0), (0, -0.47, 3.4)),           # B → A (top of A)
        Film((-1.75, 1.0, 0.56), (6.9, 0, 0), (0, -1.4, 0.5)),             # leaving A downwards
    ]
    eye, target = (2.4, 2.05, 2.7), (-0.8, 1.2, -1.8)
    bg = bokeh_background(W, H, (0.58, 0.61, 0.65), (0.46, 0.48, 0.51), seed=5)
    img, depth, cam = render(W, H, eye, target, 52, prims, films, bg=bg, light_dir=(-0.3, 1.0, 0.45),
                             film_wrap=(rollA, (-1.75, 5.2), (-90, 2)), ao_dist=0.5)
    pil = finish(img, depth, focus=(3.6, 7.0), max_blur=W * 0.005, vignette=0.22, exposure=0.92)
    notes = {"inspect": project(cam, (0.9, 1.80, -1.7)), "measure": project(cam, (-1.9, 1.0, 0.0))}
    return pil, notes


def scene_install(W, H):
    """Guide roll end: bearing housing on the frame, RMS-ON Edge mounted on the housing."""
    roll = Cylinder((2.5, 1.0, 0.0), 0.42, 2.5, 0, "steel")
    prims = [
        Floor(0.0, "floor"), roll,
        Cylinder((-0.27, 1.0, 0.0), 0.085, 0.27, 0, "steel"),               # shaft
        Box((-0.5, 0.58, -0.30), (-0.18, 1.20, 0.30), "iron"),              # housing body
        Cylinder((-0.34, 1.0, 0.0), 0.235, 0.165, 0, "iron"),               # housing boss
        Box((-0.60, 0.46, -0.50), (-0.08, 0.58, 0.50), "iron"),             # base flange
        Box((-0.85, 0.0, -0.75), (0.08, 0.46, 0.75), "frame"),              # machine frame
        Box((-0.47, 0.645, 0.30), (-0.21, 0.815, 0.445), "white"),          # RMS-ON Edge (100×65×55 mm)
        Cylinder((-0.235, 0.84, 0.40), 0.016, 0.026, 1, "brass"),           # antenna base
        Cylinder((-0.235, 1.02, 0.40), 0.013, 0.16, 1, "black"),            # antenna
        Cylinder((-0.42, 0.69, 0.457), 0.019, 0.013, 2, "alu"),             # M12 connectors
        Cylinder((-0.35, 0.69, 0.457), 0.019, 0.013, 2, "alu"),
    ]
    for (x, z) in ((-0.53, 0.40), (-0.15, 0.40), (-0.53, -0.40), (-0.15, -0.40)):
        prims.append(Cylinder((x, 0.60, z), 0.032, 0.022, 1, "steel"))     # anchor bolts
    eye, target = (0.72, 1.30, 1.42), (-0.18, 0.86, 0.05)
    bg = bokeh_background(W, H, (0.86, 0.88, 0.90), (0.72, 0.74, 0.77), seed=9)
    img, depth, cam = render(W, H, eye, target, 42, prims, bg=bg, light_dir=(0.45, 1.0, 0.75),
                             film_wrap=(roll, (0.15, 5.0), (-100, 30)), ao_dist=0.18)
    pil = finish(img, depth, focus=(1.75, 2.6), max_blur=W * 0.005, vignette=0.14, exposure=1.08)
    notes = {"vibration": project(cam, (-0.34, 0.73, 0.445)), "rotation": project(cam, (-0.54, 1.0, 0.0))}
    return pil, notes


def scene_testbed(W, H):
    """Optical test bench seen from low: ring light glowing above a backlit sample stage."""
    prims = [
        Floor(-0.9, "dark"),
        Box((-1.3, -0.9, -1.0), (1.3, 0.0, 1.0), "anod"),                   # table
        Box((-0.9, 0.0, -0.7), (0.9, 0.06, 0.7), "alu"),                    # breadboard
        Box((-0.30, 0.06, -0.30), (0.30, 0.16, 0.30), "anod", emissive_top=True),   # backlight stage
        Box((-0.05, 0.06, -0.62), (0.05, 1.75, -0.52), "alu"),              # post
        Box((-0.05, 1.42, -0.62), (0.05, 1.52, 0.05), "alu"),               # arm
        Box((-0.11, 1.12, -0.11), (0.11, 1.42, 0.11), "anod"),              # camera body
        Cylinder((0.0, 0.98, 0.0), 0.075, 0.14, 1, "anod"),                 # lens
        Cylinder((0.0, 0.70, 0.0), 0.22, 0.03, 1, "anod", emissive_ring=(0.12, 0.205)),   # ring light
        Box((-0.03, 0.72, -0.62), (0.03, 0.77, -0.2), "alu"),               # ring light holder
    ]
    eye, target = (1.35, 0.42, 1.65), (0.0, 0.66, 0.0)
    bg = bokeh_background(W, H, (0.10, 0.11, 0.13), (0.05, 0.055, 0.06), lights=40, seed=21)
    img, depth, cam = render(W, H, eye, target, 44, prims, bg=bg, light_dir=(-0.6, 1.0, 0.5),
                             strips=(0.5, 1.1), emissive=(0.92, 0.97, 1.0), ao_dist=0.25)
    pil = finish(img, depth, focus=(2.1, 3.0), max_blur=W * 0.006, vignette=0.3, exposure=1.15)
    return pil, {}


def scene_surface(W, H):
    """Dark-field macro of a brushed metallic film surface with a scratch and a white spot."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    u, v = xx / W, yy / H
    streak = np.interp(v * 3000, np.arange(6000), rng.normal(0, 1, 6000)) * 0.035 + \
        np.interp(v * 400, np.arange(1000), rng.normal(0, 1, 1000)) * 0.05
    curve = 0.025 + 0.30 * np.exp(-((v - 0.36) / 0.16) ** 2) + 0.07 * np.exp(-((v - 0.80) / 0.10) ** 2)
    base = curve * (1 + 1.6 * streak) * (0.75 + 0.25 * u)
    noise = Image.fromarray((rng.normal(128, 30, (H // 2, W // 2))).clip(0, 255).astype(np.uint8)).resize((W, H))
    base += (np.asarray(noise, np.float32) / 255 - 0.5) * 0.04
    img = np.stack([base * 0.92, base * 0.96, base * 1.04], -1)
    # scratch: thin bright slightly curved line
    sx0, sy0, sx1, sy1 = 0.585, 0.36, 0.615, 0.62
    tt = np.clip(((u - sx0) * (sx1 - sx0) + (v - sy0) * (sy1 - sy0)) / ((sx1 - sx0) ** 2 + (sy1 - sy0) ** 2), 0, 1)
    px, py = sx0 + tt * (sx1 - sx0) + 0.004 * np.sin(tt * 3.1), sy0 + tt * (sy1 - sy0)
    dist = np.hypot((u - px) * W, (v - py) * H)
    breaks = np.clip(0.75 + 0.45 * np.sin(tt * 7 + 1.0), 0.3, 1)
    scratch = np.exp(-(dist / 1.25) ** 2) * (0.5 + 0.5 * np.sin(tt * 40) ** 2) * np.clip(np.sin(tt * np.pi), 0, 1) ** 0.6 * breaks
    img += scratch[..., None] * np.array([0.55, 0.6, 0.68])
    # white spot
    d2 = np.hypot((u - 0.30) * W, (v - 0.70) * H)
    img += (np.exp(-(d2 / 4.0) ** 2) * 0.35)[..., None]
    pil = Image.fromarray((np.clip(img, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))
    notes = {"scratch": [sx0 * 100 - 1.5, sy0 * 100 - 2, (sx1 - sx0) * 100 + 4, (sy1 - sy0) * 100 + 4],
             "spot": [28.6, 67.6, 2.8, 4.8]}
    return pil, notes


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    notes = {}
    for name, fn, size, widths in (
        ("line", scene_line, (2000, 1000), (1000, 1600, 2000)),
        ("install", scene_install, (1800, 1125), (900, 1400, 1800)),
        ("testbed", scene_testbed, (1400, 1050), (800, 1400)),
        ("surface", scene_surface, (3200, 2000), (1200, 2000, 3200)),
    ):
        ss = 1.0 if name == "surface" else 1.4
        img, n = fn(round(size[0] * ss), round(size[1] * ss))
        save(img, out, name, widths)
        notes[name] = n
        print(name, "done", n)
    (out / "scenes.json").write_text(json.dumps(notes, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
