# -*- coding: utf-8 -*-
"""
Motor de animación whiteboard para el vídeo educativo "LA LEY DE CHARLES".
Genera 7 escenas MP4 (1920x1080, 30 fps) con dibujo progresivo estilo pizarra.

Uso:
  python3 render.py escena 1      (renderiza la escena 1)
  python3 render.py todo          (renderiza las 7 escenas y las une)
  python3 render.py preview 1 12  (guarda PNGs de la escena 1 en t=12s para revisar)
"""
import math
import os
import random
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

W, H = 1920, 1080
SS = 2                    # supermuestreo x2 para trazos suaves
CW, CH = W * SS, H * SS
FPS = 30
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "videos")
FONT_AMATIC = "/home/appuser/.local/lib/python3.12/site-packages/font_amatic_sc/files/AmaticSC-Bold.ttf"
FONT_FREDOKA = "/home/appuser/.local/lib/python3.12/site-packages/font_fredoka_one/files/FredokaOne-Regular.ttf"

NEGRO = (38, 38, 44)
GRIS = (125, 125, 132)
AZUL = (43, 108, 205)
AZUL_CLARO = (208, 226, 250)
ROJO = (224, 72, 44)
NARANJA = (245, 148, 55)
ROJO_CLARO = (252, 216, 203)
NARANJA_CLARO = (253, 232, 208)
ORANGE = NARANJA

_fonts = {}


def font(fname, size):
    key = (fname, size)
    if key not in _fonts:
        _fonts[key] = ImageFont.truetype(fname, int(size))
    return _fonts[key]


# ---------------------------------------------------------------- geometría
def jitter(points, seed, amp=1.6, seg=16):
    """Convierte una polilínea perfecta en un trazo 'a mano'."""
    rnd = random.Random(seed)
    out = [(points[0][0], points[0][1])]
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        d = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(d / seg))
        ph = rnd.random() * 6.28
        f1 = 1.0 + 1.2 * rnd.random()
        f2 = 2.0 + 2.0 * rnd.random()
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy) or 1.0
        px, py = -dy / ln, dx / ln
        for i in range(1, n + 1):
            t = i / n
            s = min(1.0, t * 5.0, (1 - t) * 5.0)
            off = amp * s * math.sin(t * math.pi * f1 + ph) + 0.35 * amp * s * math.sin(t * math.pi * f2 * 2 + ph * 2)
            out.append((x1 + dx * t + px * off, y1 + dy * t + py * off))
    return out


def line(p1, p2, seed, **kw):
    return jitter([p1, p2], seed, **kw)


def polyline(pts, seed, close=False, **kw):
    p = list(pts)
    if close:
        p = p + [pts[0]]
    sub = []
    for a, b in zip(p, p[1:]):
        sub += line(a, b, seed + len(sub), **kw)
    return sub


def arc_pts(cx, cy, rx, ry, a0, a1, seed, steps=None, **kw):
    if steps is None:
        steps = max(8, int(abs(a1 - a0) * max(rx, ry) / 6))
    pts = [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
            cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / steps))) for i in range(steps + 1)]
    return jitter(pts, seed, **kw)


def circle_pts(cx, cy, r, seed, **kw):
    return arc_pts(cx, cy, r, r, -90, 270, seed, **kw)


def bezier(p0, p1, p2, p3, seed, steps=26, **kw):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return jitter(pts, seed, **kw)


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 2


# ---------------------------------------------------------------- formas
def balloon_path(cx, cy, s, seed):
    """Globo (cuerpo + nudo + cuerda) escalado por s."""
    p = bezier((cx - 150 * s, cy - 40 * s), (cx - 158 * s, cy - 168 * s),
               (cx + 158 * s, cy - 178 * s), (cx + 148 * s, cy - 30 * s), seed)[:0] or []
    body = bezier((cx, cy - 180 * s), (cx - 150 * s, cy - 180 * s),
                  (cx - 175 * s, cy - 60 * s), (cx - 55 * s, cy + 35 * s), seed) + \
           bezier((cx - 55 * s, cy + 35 * s), (cx - 5 * s, cy + 52 * s),
                  (cx + 5 * s, cy + 52 * s), (cx + 55 * s, cy + 35 * s), seed + 1) + \
           bezier((cx + 55 * s, cy + 35 * s), (cx + 175 * s, cy - 60 * s),
                  (cx + 150 * s, cy - 180 * s), (cx, cy - 180 * s), seed + 2)
    knot = polyline([(cx - 24 * s, cy + 42 * s), (cx, cy + 22 * s), (cx + 24 * s, cy + 42 * s)], seed + 3, close=True)
    string = bezier((cx, cy + 42 * s), (cx + 30 * s, cy + 120 * s),
                    (cx - 30 * s, cy + 165 * s), (cx + 12 * s, cy + 225 * s), seed + 4)
    return body + knot + string


def beaker_path(cx, bottom, w, h, seed, open_top=True):
    x0, x1 = cx - w / 2, cx + w / 2
    if open_top:
        p = polyline([(x0, bottom - h), (x0 - 10, bottom - h - 22)], seed)
        p += line((x0, bottom - h + 6), (x0, bottom - 12), seed + 1, seg=14)
        p += arc_pts(cx, bottom - 12, w / 2, 16, 180, 360, seed + 2)
        p += line((x1, bottom - 12), (x1, bottom - h + 6), seed + 3, seg=14)
        p += polyline([(x1, bottom - h), (x1 + 10, bottom - h - 22)], seed + 4)
    else:
        p = arc_pts(cx, bottom - h + 20, w / 2, 20, 180, 360, seed)
        p += line((x0, bottom - h + 20), (x0, bottom - 12), seed + 1, seg=14)
        p += arc_pts(cx, bottom - 12, w / 2, 16, 180, 360, seed + 2)
        p += line((x1, bottom - 12), (x1, bottom - h + 20), seed + 3, seg=14)
        p += arc_pts(cx, bottom - h + 20, w / 2, 20, 0, 180, seed + 4)
    return p


def bottle_path(cx, bottom, s, seed):
    """Botella de vidrio con cuello; s ~ 1 = 300 px de alto."""
    bw, bh, nw, nh = 190 * s, 210 * s, 64 * s, 90 * s
    top = bottom - bh - nh
    p = line((cx - bw / 2, bottom - 14), (cx - bw / 2 - 14, bottom - bh - 40), seed, seg=20)
    p += arc_pts(cx - bw / 4, bottom - 14, bw / 4, 14, 180, 360, seed + 1)
    p += line((cx + bw / 2, bottom - 14), (cx + bw / 2 + 14, bottom - bh - 40), seed + 2, seg=20)
    p += arc_pts(cx + bw / 2 + 14, bottom - bh - 40 - nh / 2, 14, nh / 2, 0, 180, seed + 3)
    p += line((cx + nw / 2, bottom - bh - nh - 40), (cx - nw / 2, bottom - bh - nh - 40), seed + 4)
    p += arc_pts(cx - nw / 2, bottom - bh - nh / 2 - 40, 14, nh / 2, 180, 360, seed + 5)
    return p


def thermometer_path(cx, cy, h, seed):
    """Termómetro; devuelve (path, bulb_center, tube_top, tube_bottom, tube_cx)."""
    w = 56
    r = 44
    top = cy - h / 2
    bot = cy + h / 2
    p = line((cx - w / 2, top), (cx - w / 2, bot - r + 6), seed, seg=18)
    p += arc_pts(cx, bot - r + 6, r, r, 180, 360, seed + 1)
    p += line((cx + w / 2, bot - r + 6), (cx + w / 2, top), seed + 2, seg=18)
    p += arc_pts(cx, top - 12, w / 2, 12, 0, 180, seed + 3)
    ticks = []
    for i in range(7):
        ty = top + 40 + i * (h - 120) / 6
        ticks.append(line((cx - w / 2 + 4, ty), (cx - w / 2 + 26, ty), seed + 10 + i, seg=9))
    p2 = list(p)
    for t in ticks:
        p2 += t
    return p2, (cx, bot - r + 6), top, bot - r + 6, cx


def arrow_pts(p1, p2, seed, head=26):
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    a1 = ang + math.radians(152)
    a2 = ang - math.radians(152)
    h1 = (p2[0] + head * math.cos(a1), p2[1] + head * math.sin(a1))
    h2 = (p2[0] + head * math.cos(a2), p2[1] + head * math.sin(a2))
    out = jitter([p1, p2], seed)
    out += line(p2, h1, seed + 1)
    out += line(p2, h2, seed + 2)
    return out


def snowflake_pts(cx, cy, r, seed):
    pts = []
    for k in range(3):
        a = math.radians(k * 60)
        dx, dy = r * math.cos(a), r * math.sin(a)
        pts += line((cx - dx, cy - dy), (cx + dx, cy + dy), seed + k, seg=10)
        pts += line((cx + dx * 0.55, cy + dy * 0.55),
                    (cx + dx * 0.55 + r * 0.3 * math.cos(a + 1.1), cy + dy * 0.55 + r * 0.3 * math.sin(a + 1.1)), seed + k + 3, seg=8)
        pts += line((cx + dx * 0.55, cy + dy * 0.55),
                    (cx + dx * 0.55 + r * 0.3 * math.cos(a - 1.1), cy + dy * 0.55 + r * 0.3 * math.sin(a - 1.1)), seed + k + 6, seg=8)
    return pts


def flame_pts(cx, top, w, h, seed):
    return bezier((cx - w, top + h), (cx - w * 1.3, top + h * 0.25),
                  (cx - w * 0.2, top - h * 0.1), (cx, top), seed) + \
           bezier((cx, top), (cx + w * 0.2, top - h * 0.1),
                  (cx + w * 1.3, top + h * 0.25), (cx + w, top + h), seed + 1)


# ---------------------------------------------------------------- tablero
class Board:
    def __init__(self, pencil=True):
        self.canvas = Image.new("RGB", (CW, CH), "white")
        self.draw = ImageDraw.Draw(self.canvas)
        self.strokes = []       # dict: path, color, w, t0, dur, prog
        self.texts = []         # dict: x,y,txt,font,color,t0,cps,drawn
        self.fills = []         # dict: poly, color, t0
        self.dyn = []           # fn(draw, t, frame)
        self.pencil_on = pencil
        self.pencil_pos = None
        self._g = 0

    def s(self, pt):
        return (pt[0] * SS, pt[1] * SS)

    def seed(self):
        self._g += 1
        return 137 + self._g * 7

    # --- elementos estáticos progresivos
    def stroke(self, path, color=NEGRO, w=4.5, t0=0.0, dur=1.0):
        sp = [self.s(p) for p in path]
        self.strokes.append({"path": sp, "color": color, "w": w * SS, "t0": t0,
                             "dur": max(0.05, dur), "prog": 0, "pts": len(sp)})

    def strokes_many(self, paths, color=NEGRO, w=4.5, t0=0.0, dur=1.0):
        n = len(paths)
        for i, p in enumerate(paths):
            self.stroke(p, color, w, t0 + dur * i, dur / n * 0.95)

    def text(self, x, y, txt, size=44, color=NEGRO, t0=0.0, fname=FONT_FREDOKA, cps=16, seed=None):
        f = font(fname, size)
        sx, sy = self.s((x, y))
        seed = seed if seed is not None else self.seed()
        rnd = random.Random(seed)
        jit = rnd.uniform(-0.4, 0.6)
        self.texts.append({"x": sx, "y": sy + jit * SS, "txt": txt, "font": f,
                           "color": color, "t0": t0, "cps": cps, "drawn": 0})

    def text_center(self, x, y, txt, size=44, color=NEGRO, t0=0.0, **kw):
        f = font(kw.get("fname", FONT_FREDOKA), size)
        tw = f.getlength(txt.split("\n")[0] if "\n" in txt else txt)
        lines = txt.split("\n")
        lh = int(size * kw.get("lh", 1.25))
        for i, ln in enumerate(lines):
            wl = f.getlength(ln)
            self.text(x - wl / 2 / SS, y + i * lh, ln, size=size, color=color, t0=t0,
                      seed=(kw.get("seed") or self.seed()) + i, **{k: v for k, v in kw.items() if k != "lh"})

    def fill(self, poly, color, t0):
        self.fills.append({"poly": [self.s(p) for p in poly], "color": color, "t0": t0})

    def dynamic(self, fn):
        self.dyn.append(fn)

    # --- render
    def frame(self, t):
        d = self.draw
        for f in self.fills:
            if not f.get("done") and t >= f["t0"]:
                d.polygon(f["poly"], fill=f["color"])
                f["done"] = True
        p_pos = None
        for st in self.strokes:
            if st["prog"] >= st["pts"]:
                continue
            if t < st["t0"]:
                break
            f = min(1.0, (t - st["t0"]) / st["dur"])
            idx = max(2, int(f * (st["pts"] - 1)) + 1)
            if idx > st["prog"]:
                pts = st["path"][max(0, st["prog"] - 1):idx]
                d.line(pts, fill=st["color"], width=int(st["w"]), joint="curve")
                st["prog"] = idx
                p_pos = st["path"][idx - 1]
        for tx in self.texts:
            if t < tx["t0"]:
                continue
            target = int((t - tx["t0"]) * tx["cps"] * 1.0) + 1 if (t - tx["t0"]) > 0 else 0
            n, i = len(tx["txt"]), tx["drawn"]
            if target > n:
                target = n
            if target > i:
                d.text((tx["x"], tx["y"]), tx["txt"][i:target], font=tx["font"], fill=tx["color"])
                tx["drawn"] = target
                p_pos = (tx["x"] + tx["font"].getlength(tx["txt"][max(0, i - 1):target]), tx["y"] + len(tx["txt"][i:target]))
        img = self.canvas.copy()
        dd = ImageDraw.Draw(img)
        for fn in self.dyn:
            fn(dd, t)
        if self.pencil_on and p_pos and (0 <= p_pos[0] < CW) and (0 <= p_pos[1] < CH):
            self._pencil(dd, p_pos)
        return img.resize((W, H), Image.LANCZOS)

    def _pencil(self, dd, pt):
        x, y = pt
        dxs = [(-14, -52), (-6, -54), (2, -50), (4, 47), (-4, 50), (-16, 46)]
        body = [(x + a * SS, y + b * SS) for a, b in dxs]
        dd.polygon(body[:-3], outline=NEGRO, width=2)
        dd.polygon(body[-3:], fill=NEGRO)


# ---------------------------------------------------------------- dinámicas
class Particles:
    def __init__(self, x, y, w, h, n, seed, colors, r=8, margin=14):
        rnd = random.Random(seed)
        self.rnd = rnd
        self.x0, self.y0, self.w, self.h, self.col = x, y, w, h, list(colors)
        self.r, self.m = r, margin
        self.ps = []
        for i in range(n):
            self.ps.append([self.x0 + margin + rnd.random() * (w - 2 * margin),
                            self.y0 + margin + rnd.random() * (h - 2 * margin),
                            (rnd.random() - 0.5) * 2, (rnd.random() - 0.5) * 2])
        self.last_t = None
        self.n_shown = n

    def draw(self, dd, t, speed=1.0, n=None, fcol=None):
        n = self.n_shown if n is None else n
        dt = 0 if self.last_t is None else min(0.1, t - self.last_t)
        self.last_t = t
        v = 60 * speed
        for i, p in enumerate(self.ps):
            if i >= n:
                continue
            p[0] += p[2] * v * dt
            p[1] += p[3] * v * dt
            m, r = self.m, self.r
            if p[0] < self.x0 + m + r:
                p[0] = self.x0 + m + r
                p[2] = abs(p[2])
            if p[0] > self.x0 + self.w - m - r:
                p[0] = self.x0 + self.w - m - r
                p[2] = -abs(p[2])
            if p[1] < self.y0 + m + r:
                p[1] = self.y0 + m + r
                p[3] = abs(p[3])
            if p[1] > self.y0 + self.h - m - r:
                p[1] = self.y0 + self.h - m - r
                p[3] = -abs(p[3])
            for k, (dx, dy) in enumerate([(0, 0)]):
                pass
            R = self.r
            dd.ellipse([p[0] * SS - R * SS, p[1] * SS - R * SS, p[0] * SS + R * SS, p[1] * SS + R * SS],
                       fill=fcol or (self.col[i % len(self.col)] if isinstance(self.col, list) else self.col))
            dd.line([(p[0] * SS, p[1] * SS), ((p[0] - p[2] * 0.35) * SS, (p[1] - p[3] * 0.35) * SS)],
                    fill=(fcol or (self.col[i % len(self.col)] if isinstance(self.col, list) else self.col)), width=2 * SS)


def heat_waves(board, cx, y0, t0, width=220, height=90, color=NARANJA, count=3):
    def fn(dd, t):
        if t < t0:
            return
        ph = (t - t0)
        for k in range(count):
            x = cx - width / 2 + k * (width / (count - 1))
            pts = [(x + 10 * math.sin(i * 0.55 + ph * 6 + k), y0 - i * height / 14) for i in range(15)]
            dd.line([board.s(p) for p in pts], fill=color, width=max(2, int(2.6 * SS)), joint="curve")
    board.dynamic(fn)


def snowfall(board, x, y, w, h, n, t0, seed=9):
    rnd = random.Random(seed)
    flakes = [(x + rnd.random() * w, y + rnd.random() * h, 0.5 + rnd.random(), rnd.random() * 6.3) for _ in range(n)]

    def fn(dd, t):
        if t < t0:
            return
        dt = 0.033
        for i, (fx, fy, s, a) in enumerate(flakes):
            ny = y + ((fy - y) + (t - t0) * 22 * s) % h
            nx = fx + 8 * math.sin((t - t0) * 1.5 + a)
            r = 4 + s * 3
            dd.ellipse([nx * SS - r * SS, ny * SS - r * SS, nx * SS + r * SS, ny * SS + r * SS], outline=AZUL, width=2 * SS)
            dd.line([(nx - r) * SS * 1, ny * SS, (nx + r) * SS, ny * SS], fill=AZUL, width=1 * SS)
            if i > (3 if (t - t0) > 2 else 1):
                pass
    board.dynamic(fn)


def grow_path(board, path, color, w, t0, dur, scale_fn):
    """Dibuja el path progresivamente; scale_fn(t) -> (s, cx, cy) escala en vivo."""
    sp = [board.s(p) for p in path]

    def fn(dd, t):
        if t < t0:
            return
        f = min(1.0, (t - t0) / dur)
        idx = max(2, int(f * (len(sp) - 1)) + 1)
        s, cx, cy = scale_fn(t)
        pts = [(cx * SS + (px - cx * SS) * s, cy * SS + (py - cy * SS) * s) for px, py in sp[:idx]]
        dd.line(pts, fill=color, width=int(w * SS), joint="curve")
    board.dynamic(fn)


def pulse_rhombus(board, cx, cy, r, color, t0):
    def fn(dd, t):
        if t < t0:
            return
        f = ((t - t0) * 1.6) % 1.0
        rr = r * (0.7 + 0.5 * f)
        a = int(120 * (1 - f))
        col = color if a > 90 else tuple(int(c * 0.6 + 255 * 0.4) for c in color)
        dd.polygon([board.s((cx, cy - rr)), board.s((cx + rr, cy)), board.s((cx, cy + rr)), board.s((cx - rr, cy))],
                   outline=col, width=3 * SS)
    board.dynamic(fn)


# ---------------------------------------------------------------- utilidades de escena
def write_paragraph(board, x, y, lines, size=40, color=NEGRO, t0=0.0, dt=1.2, cps=None, **kw):
    lh = size * kw.pop("lh", 1.35)
    for i, ln in enumerate(lines):
        c = cps if cps else max(9, len(ln) / (dt * 1.0) * 1.0)
        board.text(x, y + i * lh, ln, size=size, color=color, t0=t0 + i * dt * 0.9, cps=c, **kw)


# ================================================================ ESCENAS
def escena1(b):
    T = 40
    # globo
    b.fill([(330, 380), (300, 250), (480, 240), (510, 395), (420, 455), (365, 400)], AZUL_CLARO, t0=3.2)
    b.stroke(balloon_path(420, 400, 0.75, 400), t0=0.6, dur=3.4)
    b.text(330, 655, "un gas", size=36, color=GRIS, t0=4.2, cps=8)
    # recipiente
    b.stroke(beaker_path(960, 640, 260, 210, 401), t0=4.6, dur=2.6)
    b.fill([(850, 500), (850, 630), (1008, 630 + 8), (1078, 628), (1078, 505), (1078, 512)], None or (236, 240, 248), t0=7.0)
    parts = Particles(838, 440, 244, 196, 9, 77, [NEGRO], r=9)
    b.dynamic(lambda dd, t: parts.draw(dd, t, 0.55, fcol=NEGRO) if t > 6.5 else None)
    b.text(880, 690, "partículas de gas", size=34, color=GRIS, t0=8.0, cps=12)
    # título
    b.text_center(960, 150, "LA LEY DE CHARLES:", size=120, color=NEGRO, t0=12.0, fname=FONT_AMATIC, cps=7)
    b.text_center(960, 300, "¿Qué pasa cuando calentamos un gas?", size=46, color=AZUL, t0=18.0, cps=14)
    # termómetro
    tp, bulb, top, bot, tcx = thermometer_path(1520, 420, 330, 402)
    b.stroke(tp, t0=23.0, dur=3.6)
    b.dynamic(lambda dd, t: (dd.ellipse([bulb[0] * SS - 44 * SS, bulb[1] * SS - 44 * SS, bulb[0] * SS + 44 * SS, bulb[1] * SS + 44 * SS],
                                        fill=ROJO),) if t > 26.5 else None)
    def mercury(dd, t):
        if t < 25.0:
            return
        f = min(1.0, (t - 25.0) / 4.0)
        y1 = bot - 26 - (bot - top - 40) * f
        dd.line([(tcx - 14) * SS, y1 * SS, (tcx + 14) * SS, y1 * SS], fill=ROJO, width=2)
        dd.polygon([((tcx - 14) * SS, y1 * SS), ((tcx + 14) * SS, y1 * SS), ((tcx + 14) * SS, (bot - 30) * SS), ((tcx - 14) * SS, (bot - 30) * SS)], fill=ROJO)
    b.dynamic(mercury)
    b.text_center(960, 920, "La temperatura cambia el comportamiento de un gas", size=42, color=NEGRO, t0=31.0, cps=15)
    b.text(1780, 620, "T", size=52, color=ROJO, t0=27.6, cps=3, fname=FONT_AMATIC)
    return T


def escena2(b):
    T = 60
    cx = 960
    bottom = 690
    state = {"s": 0.55}
    path_full = beaker_path(cx, bottom, 460, 320, 500)
    b.fill([(cx - 220, bottom - 300), (cx + 220, bottom - 300), (cx + 218, bottom - 12), (cx - 218, bottom - 12)], AZUL_CLARO, t0=4.5)
    grow_path(b, path_full, NEGRO, 4.8, 0.4, 3.4, lambda t: (state["s"], cx, bottom))
    b.text(cx - 480, 330, "CANTIDAD, PRESIÓN Y TIPO DE GAS", size=38, color=NEGRO, t0=2.2, cps=13, fname=FONT_FREDOKA)
    b.text(cx - 480, 395, "SIEMPRE IGUALES", size=42, color=GRIS, t0=4.0, cps=13, fname=FONT_AMATIC)

    def sfn(t):
        if t < 17:
            return 0.55
        return 0.55 + min(1.0, (t - 17) / 11) * 0.45
    state["sf"] = sfn
    parts = Particles(cx - 253 * 0.55, bottom - 320 * 0.55, 460 * 0.55, 300 * 0.55, 10, 51, [NEGRO], r=8)
    def dyn(dd, t):
        if t < 3.8:
            return
        s = sfn(t)
        speed = 0.35 + sfn_norm(t)
        w = 460 * s
        h = 300 * s
        parts.w, parts.h = w, h
        parts.x0, parts.y0 = cx - w / 2, bottom - h - 6
        parts.draw(dd, t, speed, fcol=ROJO if t > 19 else (AZUL if t < 14 else NEGRO))
    def sfn_norm(t):
        return min(1.0, max(0.0, (t - 16) / 12)) * 1.15
    b.dynamic(dyn)
    grow_path(b, line((cx, bottom + 26), (cx, bottom + 70), 509), GRIS, 4, 14.4, 0.5, lambda t: (1, cx, 0))
    b.text(cx + 26, bottom - 8, "calor", size=34, color=ROJO, t0=15.4, cps=8)
    flames = flame_pts(cx + 120, bottom + 74, 34, 60, 510) + flame_pts(cx - 120, bottom + 74, 34, 60, 511)
    b.strokes_many([flame_pts(cx + 120, bottom + 78, 34, 62, 512), flame_pts(cx - 120, bottom + 78, 34, 62, 513)], color=ROJO, w=4, t0=14.0, dur=1.6)
    heat_waves(b, cx, bottom - 40, 14.5, width=380, height=110)
    b.text_center(960, 130, "Mayor temperatura  =  mayor volumen", size=64, color=ROJO, t0=30.5, cps=11, fname=FONT_AMATIC)
    b.text_center(960, 220, "Menor temperatura  =  menor volumen", size=64, color=AZUL, t0=37.0, cps=11, fname=FONT_AMATIC)
    b.fill([(120, 760), (1800, 760), (1800, 970), (120, 970)], (246, 246, 250), t0=45.5)
    b.stroke(jitter_poly_box(120, 760, 1680, 210, 520), t0=44.6, dur=1.2)
    b.text_center(960, 790, "La Ley de Charles: el volumen de una cantidad fija de gas", size=44, t0=45.8, cps=17)
    b.text_center(960, 850, "es directamente proporcional a su temperatura absoluta,", size=44, t0=48.6, cps=17)
    b.text_center(960, 910, "siempre que la presión se mantenga constante.", size=44, color=AZUL, t0=51.4, cps=17)
    return T


def jitter_poly_box(x, y, w, h, seed):
    return polyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], seed, close=True, seg=30)


def escena3(b):
    T = 60
    b.strokes_many([line((960, 140), (960, 950), 600)][:1] + [line((960 + i * 26, 140), (960 + i * 26, 150 + (i % 3) * 40), 600 + i) for i in range(32)], w=3.5, t0=0.2, dur=1.6)
    b.text_center(480, 80, "FRÍO", size=72, color=AZUL, t0=1.6, fname=FONT_AMATIC, cps=4)
    b.text_center(1440, 80, "CALIENTE", size=72, color=ROJO, t0=2.2, fname=FONT_AMATIC, cps=5)
    # izquierda: recipiente pequeño
    b.fill([(215, 620), (665, 620), (663, 830), (217, 830)], AZUL_CLARO, t0=5.0)
    b.stroke(beaker_path(440, 838, 450, 220, 601), t0=4.0, dur=2.4)
    parts1 = Particles(230, 630, 420, 196, 8, 61, [AZUL], r=8)
    b.dynamic(lambda dd, t: parts1.draw(dd, t, 0.35, fcol=AZUL) if t > 6.2 else None)
    tp1, bulb1, top1, bot1, tc1 = thermometer_path(480, 470, 200, 602)
    b.stroke(tp1, t0=7.0, dur=2.2)
    def merc1(dd, t):
        if t < 9.0:
            return
        f = 0.22
        y1 = bot1 - 18 - (bot1 - top1 - 60) * f
        dd.polygon([((tc1 - 12) * SS, y1 * SS), ((tc1 + 12) * SS, y1 * SS), ((tc1 + 12) * SS, (bot1 - 24) * SS), ((tc1 - 12) * SS, (bot1 - 24) * SS)], fill=AZUL)
        dd.ellipse([bulb1[0] * SS - 38 * SS, bulb1[1] * SS - 38 * SS, bulb1[0] * SS + 38 * SS, bulb1[1] * SS + 38 * SS], fill=AZUL)
    b.dynamic(merc1)
    b.text_center(440, 880, "Baja temperatura", size=40, color=AZUL, t0=10.2, cps=12)
    b.text_center(440, 945, "Volumen pequeño", size=40, color=NEGRO, t0=12.0, cps=12)
    # derecha: recipiente grande
    b.fill([(1180, 470), (1690, 470), (1688, 830), (1182, 830)], ROJO_CLARO, t0=14.0)
    b.stroke(beaker_path(1435, 838, 510, 370, 603), t0=13.0, dur=2.8)
    parts2 = Particles(1200, 480, 470, 344, 8, 63, [ROJO], r=9)
    b.dynamic(lambda dd, t: parts2.draw(dd, t, 2.2, fcol=ROJO) if t > 15.5 else None)
    tp2, bulb2, top2, bot2, tc2 = thermometer_path(1420, 300, 200, 604)
    b.stroke(tp2, t0=16.0, dur=2.2)
    def merc2(dd, t):
        if t < 18.0:
            return
        f = 0.92
        y1 = bot2 - 18 - (bot2 - top2 - 60) * f
        dd.polygon([((tc2 - 12) * SS, y1 * SS), ((tc2 + 12) * SS, y1 * SS), ((tc2 + 12) * SS, (bot2 - 24) * SS), ((tc2 - 12) * SS, (bot2 - 24) * SS)], fill=ROJO)
        dd.ellipse([bulb2[0] * SS - 38 * SS, bulb2[1] * SS - 38 * SS, bulb2[0] * SS + 38 * SS, bulb2[1] * SS + 38 * SS], fill=ROJO)
    b.dynamic(merc2)
    b.text_center(1435, 880, "Alta temperatura", size=40, color=ROJO, t0=19.2, cps=12)
    b.text_center(1435, 945, "Volumen grande", size=40, color=NEGRO, t0=21.0, cps=12)
    # movimiento lento vs rápido
    b.text_center(440, 550, "partículas lentas", size=30, color=GRIS, t0=24.6, cps=12)
    b.text_center(1435, 420, "partículas rápidas", size=30, color=GRIS, t0=25.4, cps=12)
    # flecha
    b.stroke(arrow_pts((120, 1010), (1800, 1010), 605, head=34), color=NARANJA, w=6, t0=27.5, dur=2.6)
    b.text_center(960, 1032, "aumenta la temperatura   →   aumenta el volumen", size=38, color=NARANJA, t0=30.0, cps=18)
    pulse_rhombus(b, 960, 550, 60, NARANJA, 33.0)
    b.fill([(300, 600), (1620, 600), (1620, 700), (300, 700)], (247, 247, 250), t0=42.0)
    b.stroke(jitter_poly_box(300, 600, 1320, 100, 606), t0=41.0, dur=1.0)
    b.text_center(960, 622, "Comparación con presión constante", size=38, t0=42.5, cps=14)
    b.text_center(960, 662, "y con la misma cantidad de gas", size=38, t0=45.0, cps=14)
    return T


def escena4(b):
    T = 50
    b.text_center(960, 140, "LA FÓRMULA", size=76, t0=0.3, fname=FONT_AMATIC, cps=5)
    # V1/T1 = V2/T2 grande con fracciones dibujadas
    ybar = 430
    b.stroke(line((700, ybar), (860, ybar), 700), w=7, t0=2.2, dur=0.8)
    b.stroke(line((1120, ybar), (1280, ybar), 701), w=7, t0=3.0, dur=0.8)
    b.text(736, 250, "V1", size=104, color=AZUL, t0=3.6, cps=2.2, fname=FONT_FREDOKA)
    b.text(748, 452, "T1", size=104, color=ROJO, t0=4.4, cps=2.2, fname=FONT_FREDOKA)
    b.text(1152, 250, "V2", size=104, color=AZUL, t0=5.2, cps=2.2, fname=FONT_FREDOKA)
    b.text(1164, 452, "T2", size=104, color=ROJO, t0=6.0, cps=2.2, fname=FONT_FREDOKA)
    b.text(936, 330, "=", size=104, t0=4.9, cps=2.5, fname=FONT_FREDOKA)
    b.text(1330, 330, "· temperatura", size=30, color=GRIS, t0=7.0, cps=10)
    # etiquetas con flechas
    b.stroke(arrow_pts((770, 240), (560, 180), 702), color=AZUL, w=4, t0=8.5, dur=1.0)
    b.text(160, 140, "V1 = volumen inicial", size=42, color=AZUL, t0=9.2, cps=12)
    b.stroke(arrow_pts((790, 560), (560, 630), 703), color=ROJO, w=4, t0=10.8, dur=1.0)
    b.text(140, 640, "T1 = temperatura inicial", size=42, color=ROJO, t0=11.5, cps=12)
    b.stroke(arrow_pts((1190, 240), (1400, 180), 704), color=AZUL, w=4, t0=13.2, dur=1.0)
    b.text(1420, 140, "V2 = volumen final", size=42, color=AZUL, t0=13.9, cps=12)
    b.stroke(arrow_pts((1210, 560), (1400, 630), 705), color=ROJO, w=4, t0=14.8, dur=1.0)
    b.text(1420, 640, "T2 = temperatura final", size=42, color=ROJO, t0=15.5, cps=12)
    # termómetro y Kelvin
    tp, bulb, top, bot, tcx = thermometer_path(300, 890, 250, 706)
    b.stroke(tp, t0=18.5, dur=2.4)
    def merc(dd, t):
        if t < 20.5:
            return
        dd.ellipse([bulb[0] * SS - 38 * SS, bulb[1] * SS - 38 * SS, bulb[0] * SS + 38 * SS, bulb[1] * SS + 38 * SS], fill=ROJO)
        f = min(1.0, (t - 20.5) / 3)
        y1 = bot - 20 - (bot - top - 50) * f
        dd.polygon([((tcx - 11) * SS, y1 * SS), ((tcx + 11) * SS, y1 * SS), ((tcx + 11) * SS, (bot - 22) * SS), ((tcx - 11) * SS, (bot - 22) * SS)], fill=ROJO)
    b.dynamic(merc)
    b.text(400, 780, "La temperatura se escribe", size=40, t0=21.5, cps=13)
    b.text(400, 845, "siempre en KELVIN", size=46, color=ROJO, t0=24.0, cps=11)
    b.fill([(760, 770), (1660, 770), (1660, 940), (760, 940)], (253, 240, 228), t0=28.2)
    b.stroke(jitter_poly_box(760, 770, 900, 170, 707), t0=27.0, dur=1.2)
    b.text_center(1210, 800, "Conversión", size=48, t0=28.6, fname=FONT_AMATIC, cps=6)
    b.text_center(1210, 880, "K = °C + 273,15", size=64, color=ORANGE, t0=30.4, cps=7)
    return T


def escena5(b):
    T = 45
    b.text_center(960, 110, "EJEMPLO PRÁCTICO", size=80, t0=0.3, fname=FONT_AMATIC, cps=5)
    # datos
    b.stroke(jitter_poly_box(110, 220, 560, 250, 800), t0=1.2, dur=1.6)
    b.text(150, 250, "V1 = 2 litros", size=48, color=AZUL, t0=2.6, cps=10)
    b.text(150, 330, "T1 = 300 K", size=48, color=ROJO, t0=4.2, cps=10)
    b.text(150, 410, "T2 = 450 K", size=48, color=ROJO, t0=5.8, cps=10)
    # desarrollo
    b.text(760, 260, "V2 = (V1 × T2) / T1", size=52, t0=8.0, cps=9, fname=FONT_FREDOKA)
    b.text(760, 350, "V2 = (2 × 450) / 300", size=52, t0=11.5, cps=9, fname=FONT_FREDOKA)
    b.text(760, 440, "V2 = 900 / 300", size=52, t0=15.0, cps=9, fname=FONT_FREDOKA)
    b.stroke(jitter_poly_box(748, 530, 470, 92, 801), t0=18.0, dur=1.0)
    b.text(775, 548, "V2 = 3 litros", size=56, color=ROJO, t0=18.6, cps=8, fname=FONT_FREDOKA)
    # ilustración: 2 L vs 3 L
    s1, s2 = 0.42, 0.60
    bx1, bx2 = 420, 1420
    by = 870
    b.stroke(beaker_path(bx1, by, 340 * s1 / 0.42, 300 * s1 / 0.42, 802), t0=20.5, dur=2.0)
    p1 = Particles(bx1 - 170 * 1, by - 300 - 6, 340, 296, 5, 82, [NEGRO], r=8)
    b.dynamic(lambda dd, t: p1.draw(dd, t, 1.0, fcol=NEGRO) if t > 22.4 else None)
    b.stroke(beaker_path(bx2, by, 340 * s2 / 0.42, 300 * s2 / 0.42, 803), t0=23.0, dur=2.4)
    p2 = Particles(bx2 - 243 * 1, by - 428 - 6, 486, 424, 5, 83, [NEGRO], r=8)
    b.dynamic(lambda dd, t: p2.draw(dd, t, 1.0, fcol=NEGRO) if t > 25.2 else None)
    b.stroke(arrow_pts((bx1 + 220, by - 160), (bx2 - 290, by - 220), 804), color=NARANJA, w=6, t0=26.0, dur=1.6)
    b.text_center(bx1, 900, "2 L", size=44, t0=27.0, cps=6)
    b.text_center(bx2, 910, "3 L", size=48, color=ROJO, t0=28.0, cps=4)
    b.text_center(960, 1000, "Misma cantidad de gas y misma presión", size=36, color=GRIS, t0=30.5, cps=14)
    return T


def escena6(b):
    T = 70
    b.text_center(960, 100, "EXPERIMENTO", size=84, t0=0.3, fname=FONT_AMATIC, cps=5)
    b.strokes_many([line((960, 190), (960, 980), 900 + i) for i in range(0)], w=3.5, t0=0, dur=0.1)
    # panel izquierdo (caliente) y derecho (frío)
    b.stroke(jitter_poly_box(0 + 40, 180, 920, 830, 901), t0=1.2, dur=2.2)
    b.stroke(jitter_poly_box(960, 180, 920, 830, 902), t0=1.6, dur=2.2)
    b.text_center(480, 210, "AGUA CALIENTE", size=48, color=ROJO, t0=3.6, fname=FONT_AMATIC, cps=6)
    b.text_center(1440, 210, "AGUA CON HIELO", size=48, color=AZUL, t0=5.2, fname=FONT_AMATIC, cps=6)
    # botella izquierda
    def scale_L(t):
        f = min(1.0, max(0.0, (t - 12) / 13))
        return 0.28 + 0.72 * ease_out(f)
    balloon_L = balloon_path(480, 355, 1.0, 903)
    grow_path(b, balloon_L, ROJO, 4.5, 7.8, 2.4, lambda t: (scale_L(t), 480, 355 + (1 - scale_L(t)) * 10))
    b.fill([(390, 300), (570, 300), (566, 380), (386, 380)], ROJO_CLARO, t0=13.0)
    b.stroke(bottle_path(480, 820, 0.95, 904), t0=6.2, dur=2.6)
    b.stroke(jitter_poly_box(300, 812, 360, 140, 905), t0=9.0, dur=1.6)
    def hot_water(dd, t):
        if t < 10.6:
            return
        dd.polygon([(310 * SS, 826 * SS), (650 * SS, 826 * SS), (652 * SS, 838 * SS), (308 * SS, 838 * SS)], fill=(186, 226, 245))
    b.dynamic(hot_water)
    b.stroke(flame_pts(400, 1000, 30, 60, 906), color=ROJO, t0=10.4, dur=1.0)
    b.stroke(flame_pts(560, 1000, 30, 60, 907), color=ROJO, t0=10.7, dur=1.0)
    heat_waves(b, 480, 700, 11.0, width=300, height=120)
    b.text_center(480, 1030, "El aire se calienta y ocupa más volumen", size=32, color=ROJO, t0=24.0, cps=14)
    # botella derecha
    balloon_R = balloon_path(1440, 355, 1.0, 908)
    grow_path(b, balloon_R, AZUL, 4.5, 33.0, 2.4, lambda t: (0.24, 1440, 355 + 10))
    b.stroke(bottle_path(1440, 820, 0.95, 909), t0=30.0, dur=2.6)
    b.stroke(jitter_poly_box(1260, 812, 360, 140, 910), t0=32.5, dur=1.6)
    def cold_water(dd, t):
        if t < 33.8:
            return
        dd.polygon([(1270 * SS, 826 * SS), (1610 * SS, 826 * SS), (1612 * SS, 838 * SS), (1268 * SS, 838 * SS)], fill=(196, 220, 252))
    b.dynamic(cold_water)
    snowfall(b, 1230, 780, 420, 220, 9, 34.0)
    def defl_note(dd, t):
        pass
    b.text_center(1440, 1030, "El aire se enfría y ocupa menos volumen", size=32, color=AZUL, t0=42.0, cps=14)
    b.stroke(arrow_pts((990, 560), (1090, 560), 911), color=GRIS, w=4, t0=46.0, dur=1.0)
    b.stroke(arrow_pts((930, 560), (830, 560), 912), color=GRIS, w=4, t0=46.3, dur=1.0)
    # aclaración
    b.fill([(240, 1000), (1680, 1000), (1680, 1070), (240, 1070)], (246, 246, 250), t0=52.0)
    b.text_center(960, 1006, "El aire cambia de volumen al calentarse y enfriarse. Experimento", size=34, t0=52.6, cps=16)
    b.text_center(960, 1048, "demostrativo: también intervienen cambios de presión.", size=34, color=GRIS, t0=56.0, cps=16)
    return T


def escena7(b):
    T = 35
    # recap dibujado
    tp, bulb, top, bot, tcx = thermometer_path(260, 240, 260, 1100)
    b.stroke(tp, t0=0.4, dur=2.2)
    def merc(dd, t):
        if t < 2.4:
            return
        dd.ellipse([bulb[0] * SS - 38 * SS, bulb[1] * SS - 38 * SS, bulb[0] * SS + 38 * SS, bulb[1] * SS + 38 * SS], fill=ROJO)
        f = min(1.0, (t - 2.4) / 2.5)
        y1 = bot - 18 - (bot - top - 46) * f
        dd.polygon([((tcx - 11) * SS, y1 * SS), ((tcx + 11) * SS, y1 * SS), ((tcx + 11) * SS, (bot - 22) * SS), ((tcx - 11) * SS, (bot - 22) * SS)], fill=ROJO)
    b.dynamic(merc)
    b.stroke(beaker_path(700, 360, 280, 220, 1101), t0=2.4, dur=2.2)
    pr = Particles(574, 152, 252, 202, 6, 111, [NEGRO], r=7)
    b.dynamic(lambda dd, t: pr.draw(dd, t, 1.2, fcol=NEGRO) if t > 5.0 else None)
    b.text(940, 150, "T ↑  →  V ↑", size=58, color=ORANGE, t0=5.5, cps=6, fname=FONT_FREDOKA)
    b.text(940, 250, "(presión y cantidad de gas constantes)", size=30, color=GRIS, t0=8.0, cps=13)
    # frase central
    b.fill([(110, 380), (1810, 380), (1810, 660), (110, 660)], (250, 250, 253), t0=10.4)
    b.stroke(jitter_poly_box(110, 380, 1700, 280, 1102), t0=9.4, dur=1.4)
    b.text_center(960, 402, "LA TEMPERATURA Y EL VOLUMEN DE UN GAS", size=56, t0=11.0, cps=10, fname=FONT_AMATIC, lh=1.2)
    b.text_center(960, 470, "SON DIRECTAMENTE PROPORCIONALES", size=56, t0=13.6, cps=10, fname=FONT_AMATIC)
    b.text_center(960, 538, "CUANDO LA PRESIÓN Y LA CANTIDAD DE GAS", size=48, color=AZUL, t0=16.2, cps=11, fname=FONT_AMATIC)
    b.text_center(960, 596, "SE MANTIENEN CONSTANTES", size=48, color=AZUL, t0=18.4, cps=11, fname=FONT_AMATIC)
    # globo final
    b.stroke(balloon_path(880, 880, 0.7, 1103), t0=20.0, dur=2.6)
    def smile(dd, t):
        if t < 22.4:
            return
        dd.arc([830 * SS, 812 * SS, 930 * SS, 872 * SS], 20, 160, fill=NEGRO, width=4 * SS)
    b.dynamic(smile)
    sparkles(b, 1240, 850, 1230, 1030, 140, 8, 22.6)
    b.text(1140, 900, "¡AHORA YA CONOCEMOS", size=64, t0=25.0, cps=8, fname=FONT_AMATIC)
    b.text(1140, 975, "LA LEY DE CHARLES!", size=64, color=ORANGE, t0=28.0, cps=8, fname=FONT_AMATIC)
    return T


def sparkles(board, x0, x1, y0, y1, n, r, t0, seed=99):
    rnd = random.Random(seed)
    stars = [(rnd.uniform(x0, x1), rnd.uniform(y0, y1), rnd.uniform(6, 12), rnd.random() * 6.3) for _ in range(n)]

    def fn(dd, t):
        if t < t0:
            return
        for i, (sx, sy, s, a) in enumerate(stars):
            if i / n > min(1.0, (t - t0) / 4.0):
                continue
            k = 0.75 + 0.25 * math.sin((t - t0) * 3 + a)
            rr = s * k
            for ang in range(0, 360, 72):
                ar = math.radians(ang)
                dd.line([sx * SS, sy * SS, (sx + rr * math.cos(ar)) * SS, (sy + rr * math.sin(ar)) * SS],
                        fill=NARANJA, width=2 * SS)
    board.dynamic(fn)


# ---------------------------------------------------------------- renderizador
SCENES = [escena1, escena2, escena3, escena4, escena5, escena6, escena7]


def ffmpeg_pipe(path):
    exe = imageio_ffmpeg.get_ffmpeg_exe()
    return subprocess.Popen(
        [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", path],
        stdin=subprocess.PIPE)


def render_scene(idx, only_frames=None, out=None):
    name = f"escena{idx + 1}"
    path = out or os.path.join(OUT_DIR, name + ".mp4")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    b = Board(pencil=True)
    T = SCENES[idx](b)
    dur = only_frames is None and T or 0
    frames = only_frames if only_frames is not None else range(int(T * FPS))
    if only_frames is None:
        proc = ffmpeg_pipe(path)
        t0 = time.time()
        for f in frames:
            t = f / FPS
            img = b.frame(t)
            if t < 0.5:
                img = Image.blend(Image.new("RGB", (W, H), "white"), img, ease_out(t / 0.5))
            if T - t < 0.6:
                img = Image.blend(img, Image.new("RGB", (W, H), "white"), 1 - ease_out((T - t) / 0.6))
            proc.stdin.write(img.tobytes())
        proc.stdin.close()
        proc.wait()
        print(f"{name}: {T:.0f}s -> {path} ({time.time() - t0:.0f}s)")
    else:
        for f in only_frames:
            img = b.frame(f / FPS)
            png = f"/tmp/prev_{name}_{f}.png"
            img.save(png)
            print(png)
    return path


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if mode == "escena":
        render_scene(int(sys.argv[2]) - 1)
    elif mode == "preview":
        render_scene(int(sys.argv[2]) - 1, only_frames=[int(x) for x in sys.argv[3:]])
    elif mode == "todo":
        for i in range(7):
            render_scene(i)
        print("OK")
