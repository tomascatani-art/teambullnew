"""Efectos animados para el video elegante de Estilo Vinos.

Genera secuencias PNG con transparencia (1080x1920, 30 fps):
  intro_corks/  corchos cayendo en cámara lenta (intro)
  cork_rain/    lluvia de corchos (transición)
  wine_a/, wine_b/  ola de vino que cubre y descubre la pantalla (transición)

Uso: python3 fx.py <carpeta-salida> [preview]
"""
import math
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
SERIF = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"


def smooth_noise(w, h, cells, rng):
    small = rng.random((max(2, h // cells), max(2, w // cells))).astype(np.float32)
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(img, np.float32) / 255.0


# ---------------------------------------------------------------- corcho
def make_cork(seed, length=330, diam=128, ss=2):
    rng = np.random.default_rng(seed)
    w, h = diam * ss, length * ss
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx + 0.5) / w * 2 - 1           # -1..1 a lo ancho
    v = (yy + 0.5) / h                   # 0..1 a lo largo

    # silueta: rectángulo con bordes redondeados (SDF), antialias por supersampling
    r = 0.16 * w
    qx = np.abs(xx - w / 2) - (w / 2 - r)
    qy = np.abs(yy - h / 2) - (h / 2 - r)
    sdf = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    alpha = np.clip(-sdf, 0, 1)

    # color base del corcho con variación natural
    base = np.array([0.80, 0.63, 0.44], np.float32)
    n = 0.55 * smooth_noise(w, h, 6 * ss, rng) + 0.45 * smooth_noise(w, h, 22 * ss, rng)
    col = base[None, None, :] * (0.80 + 0.35 * n)[..., None]

    # poros (lenticelas): manchitas oscuras alargadas
    pores = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(pores)
    for _ in range(int(170 * ss)):
        px, py = rng.uniform(0, w), rng.uniform(0, h)
        pw, ph = rng.uniform(0.6, 2.6) * ss, rng.uniform(1.2, 6.5) * ss
        d.ellipse([px - pw, py - ph, px + pw, py + ph], fill=int(rng.uniform(90, 230)))
    pores = np.asarray(pores.filter(ImageFilter.GaussianBlur(0.7 * ss)), np.float32) / 255
    col *= (1 - 0.45 * pores)[..., None]

    # marca impresa
    txt = Image.new("L", (h, w), 0)
    td = ImageDraw.Draw(txt)
    font = ImageFont.truetype(SERIF, int(26 * ss))
    label = "ESTILO  VINOS"
    tw = td.textlength(label, font=font)
    td.text(((h - tw) / 2 + 0.07 * h, w / 2 - 15 * ss), label, font=font, fill=255)
    txt = np.asarray(txt.rotate(90, expand=True), np.float32) / 255
    ink = np.array([0.30, 0.16, 0.08], np.float32)
    k = 0.62 * txt * (0.75 + 0.25 * n)
    col = col * (1 - k[..., None]) + ink * k[..., None]

    # mancha de vino en un extremo, con borde irregular
    edge = 0.80 + 0.05 * (smooth_noise(w, h, 9 * ss, rng) - 0.5) * 2
    stain = np.clip((v - edge) / 0.035, 0, 1)
    wine = np.array([0.34, 0.05, 0.12], np.float32) * (0.75 + 0.35 * n)[..., None]
    col = col * (1 - 0.92 * stain[..., None]) + wine * (0.92 * stain[..., None])

    # sombreado cilíndrico (luz desde arriba a la izquierda) + oclusión en extremos
    nz = np.sqrt(np.clip(1 - u * u, 0, 1))
    lam = np.clip(-0.55 * u + 0.83 * nz, 0, 1)
    shade = 0.30 + 0.85 * lam
    ends = np.clip(np.minimum(v, 1 - v) / 0.06, 0, 1) ** 0.5
    shade *= 0.65 + 0.35 * ends
    spec = np.clip(-0.55 * u + 0.83 * nz, 0, 1) ** 24 * 0.12
    col = np.clip(col * shade[..., None] + spec[..., None], 0, 1)

    rgba = np.dstack([col, alpha]).astype(np.float32)
    img = Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")
    return img.resize((diam, length), Image.LANCZOS)


# ---------------------------------------------------------------- partículas
class Cork:
    def __init__(self, sprite, x, y, vx, vy, ang, spin, scale, t0, g):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.ang, self.spin, self.t0, self.g = ang, spin, t0, g
        sw, sh = sprite.size
        spr = sprite.resize((max(1, int(sw * scale)), max(1, int(sh * scale))), Image.LANCZOS)
        if scale < 0.65:      # lejos: desenfoque y más oscuro (profundidad de campo)
            spr = spr.filter(ImageFilter.GaussianBlur(2.2))
            arr = np.asarray(spr, np.float32)
            arr[..., :3] *= 0.72
            spr = Image.fromarray(arr.astype(np.uint8), "RGBA")
        elif scale > 1.45:    # muy cerca de cámara: fuera de foco
            spr = spr.filter(ImageFilter.GaussianBlur(3.5))
        self.spr = spr
        a = spr.split()[3].filter(ImageFilter.GaussianBlur(10 * scale))
        self.shadow = Image.merge("RGBA", [Image.new("L", spr.size, 0)] * 3 + [a.point(lambda p: int(p * 0.45))])
        self.off = (int(14 * scale), int(26 * scale))

    def draw(self, canvas, t):
        dt = t - self.t0
        if dt < 0:
            return
        x = self.x + self.vx * dt
        y = self.y + self.vy * dt + 0.5 * self.g * dt * dt
        ang = self.ang + self.spin * dt
        if y > H + 400:
            return
        for img, (ox, oy) in ((self.shadow, self.off), (self.spr, (0, 0))):
            r = img.rotate(ang, resample=Image.BICUBIC, expand=True)
            px, py = int(x - r.width / 2 + ox), int(y - r.height / 2 + oy)
            canvas.alpha_composite(r, (px, py)) if 0 <= px and 0 <= py and px + r.width <= W and py + r.height <= H \
                else _paste_clipped(canvas, r, px, py)


def _paste_clipped(canvas, img, px, py):
    x0, y0 = max(0, px), max(0, py)
    x1, y1 = min(W, px + img.width), min(H, py + img.height)
    if x1 <= x0 or y1 <= y0:
        return
    canvas.alpha_composite(img.crop((x0 - px, y0 - py, x1 - px, y1 - py)), (x0, y0))


def render_corks(out, corks, seconds, sub=3):
    os.makedirs(out, exist_ok=True)
    corks = sorted(corks, key=lambda c: c.spr.width)  # los chicos (lejos) primero
    for f in range(int(seconds * FPS)):
        acc = np.zeros((H, W, 4), np.float32)
        for s in range(sub):  # desenfoque de movimiento: promedio de sub-cuadros
            t = (f + s / sub) / FPS
            canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            for c in corks:
                c.draw(canvas, t)
            a = np.asarray(canvas, np.float32)
            a[..., :3] *= a[..., 3:4] / 255
            acc += a
        acc /= sub
        rgb = np.where(acc[..., 3:4] > 0, acc[..., :3] * 255 / np.maximum(acc[..., 3:4], 1e-3), 0)
        frame = np.dstack([np.clip(rgb, 0, 255), acc[..., 3]]).astype(np.uint8)
        Image.fromarray(frame, "RGBA").save(f"{out}/{f:04d}.png", compress_level=1)


def intro_corks(sprites, rng):
    corks = []
    for i in range(15):
        scale = rng.choice([0.45, 0.55, 0.7, 0.85, 1.0, 1.15, 1.3, 1.6])
        corks.append(Cork(sprites[i % len(sprites)], rng.uniform(80, W - 80), -280 * scale,
                          rng.uniform(-50, 50), rng.uniform(150, 350), rng.uniform(0, 360),
                          rng.uniform(-150, 150), scale, rng.uniform(0, 1.7), 1300))
    return corks


def rain_corks(sprites, rng):
    corks = []
    for i in range(20):
        scale = rng.choice([0.7, 0.9, 1.1, 1.3, 1.5, 1.8])
        corks.append(Cork(sprites[i % len(sprites)], (i + 0.5) / 20 * W + rng.uniform(-40, 40), -320 * scale,
                          rng.uniform(-80, 80), rng.uniform(1100, 1600), rng.uniform(0, 360),
                          rng.uniform(-300, 300), scale, rng.uniform(0, 0.35), 2600))
    return corks


# ---------------------------------------------------------------- ola de vino
def render_wine(out, seed, seconds=1.0):
    os.makedirs(out, exist_ok=True)
    rng = np.random.default_rng(seed)
    x = np.arange(W, dtype=np.float32)
    y = np.arange(H, dtype=np.float32)[:, None]
    drips = [(rng.uniform(0, W), rng.uniform(18, 45), rng.uniform(60, 220)) for _ in range(9)]
    drips_b = [(rng.uniform(0, W), rng.uniform(25, 60), rng.uniform(40, 140)) for _ in range(6)]
    base = np.array([96, 8, 30], np.float32)
    ease = lambda p: p * p * (3 - 2 * p)
    n = int(seconds * FPS)
    for f in range(n):
        t = f / (n - 1)
        p1 = ease(min(1, t / 0.46))
        grow = min(1, t / 0.46)
        bumps = sum(L * grow * np.exp(-((x - cx) / wd) ** 2) for cx, wd, L in drips)
        front = -420 + (H + 520) * p1 + 9 * np.sin(x / 83 + t * 5) + 14 * np.sin(x / 217 + 1.3) + bumps
        p2 = ease(np.clip((t - 0.56) / 0.44, 0, 1))
        bumps_b = sum(L * np.exp(-((x - cx) / wd) ** 2) for cx, wd, L in drips_b)
        back = -260 + (H + 520) * p2 + 11 * np.sin(x / 97 + 2 + t * 4) - bumps_b * (p2 > 0)
        df = front[None, :] - y
        db = y - back[None, :] if p2 > 0 else np.full_like(df, 1e4)
        d = np.minimum(df, db)
        alpha = np.clip(d / 1.5, 0, 1)
        depth = 0.62 + 0.38 * np.exp(-np.maximum(d, 0) / 140)
        sheen = 0.025 * (np.sin(x / 160 + y / 260 + t * 4) * 0.5 + 0.5)
        col = base[None, None, :] * depth[..., None] + 255 * sheen[..., None] * 0.35
        rim = np.exp(-((df - 11) / 4.5) ** 2) * 0.42 + np.exp(-((db - 11) / 5) ** 2) * 0.25
        col = col * (1 - rim[..., None]) + np.array([250, 190, 200], np.float32) * rim[..., None]
        dark = np.clip(1 - d / 3.5, 0, 1) * 0.5  # borde fino más oscuro
        col *= (1 - dark)[..., None]
        frame = np.dstack([np.clip(col, 0, 255), alpha * 255]).astype(np.uint8)
        Image.fromarray(frame, "RGBA").save(f"{out}/{f:04d}.png", compress_level=1)


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    sprites = [make_cork(s) for s in range(5)]
    if len(sys.argv) > 2 and sys.argv[2] == "preview":
        sheet = Image.new("RGBA", (5 * 160, 360), (20, 10, 14, 255))
        for i, s in enumerate(sprites):
            sheet.alpha_composite(s.rotate(i * 17 - 30, resample=Image.BICUBIC, expand=True).crop((0, 0, 160, 360)), (i * 160, 0))
        sheet.convert("RGB").save(f"{out}/cork_preview.jpg")
        sys.exit()
    rng = random.Random(7)
    render_corks(f"{out}/intro_corks", intro_corks(sprites, rng), 4.0, sub=6)
    print("intro_corks listo", flush=True)
    render_corks(f"{out}/cork_rain", rain_corks(sprites, random.Random(3)), 1.2, sub=10)
    print("cork_rain listo", flush=True)
    render_wine(f"{out}/wine_a", 11)
    render_wine(f"{out}/wine_b", 23)
    print("wine listo", flush=True)
