"""Spot ESTILO VINOS — compositor cuadro a cuadro (1080x1920, 30 fps).

Guion (120 BPM). Cada transición es una técnica de montaje real, motivada por lo que hay en la toma:
  0.0   corcho de la marca disparado hacia cámara; pasa frente a la lente y revela la tienda (macro -> general)
  2.5   corte en el golpe con "zoom punch".                                   VINOS
  4.3   whip pan horizontal siguiendo la línea de las estanterías
  6.5   zoom-through: la cámara entra en una botella oscura y sale en los destilados.   DESTILADOS
  8.3   luz cálida que se filtra en la lente (light leak) y disuelve a las cajas.       REGALOS
 10.5   match cut entre cajas en el golpe
 12.35  giro de cámara (roll) con desenfoque de movimiento
 12.35  rampa de velocidad -> cámara lenta sobre las copas, destello en el cristal.     EL ARTE DE ELEGIR
 16.0   cambio de foco: el brillo de las copas se vuelve el bokeh de las lámparas
 17.45  las lámparas sobreexponen y disuelven a la góndola
 18.4   whip vertical; 19.55 una columna pasa frente a la lente; 20.45 corte con rampa de velocidad
 21.5   zoom punch en el golpe; 22.5 disolución lenta al plano héroe en cámara lenta (polvo dorado)
 24.5   empuje de cámara que continúa en la toma de la clienta.  ENVÍOS A DOMICILIO / ESCRIBINOS
 30.0   fundido a negro en el silencio; 30.5 el logo aparece en foco con barrido de luz dorada. Datos y CTA.

Uso:
  python3 render.py out.mp4 [cuadro_inicial]   render completo (o desde un cuadro)
  python3 render.py --chunks DIR                render por tramos reanudable (DIR/chunk_XXX.mp4)
  python3 render.py --preview 0.3,6.4 dir      cuadros sueltos para revisar
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageFilter

from common import (DURATION, FPS, H, SERIF, SERIF_IT, T, W, WINE, Dust, Shot, affine_blit, clamp01, ease_in,
                    ease_io, ease_out, gold_fill, kinetic, logo_mask, make_cork, put_layer, star_glint, text_mask,
                    zoom_blur)

HERE = os.path.dirname(os.path.abspath(__file__))
FXDIR = os.path.join(HERE, "..", ".work-fx")

# ------------------------------------------------------------------ tomas
S = dict(
    hook=Shot("IMG_1375", 0.3, 2.3, res=2160),
    s1370=Shot("IMG_1370", 0.4, 2.2),
    s1364=Shot("IMG_1364", 0.6, 2.5, res=2160),
    s1368a=Shot("IMG_1368", 0.5, 2.2),
    s1353=Shot("IMG_1353", 0.4, 2.5),
    s1355=Shot("IMG_1355", 0.5, 2.3),
    s1374=Shot("IMG_1374", 0.0, 4.1, ifps=90),
    s1366=Shot("IMG_1366", 0.5, 1.6),
    s1360=Shot("IMG_1360", 0.5, 1.4),
    s1357=Shot("IMG_1357", 0.5, 1.5),
    s1367=Shot("IMG_1367", 0.5, 1.5),
    s1368b=Shot("IMG_1368", 2.4, 1.5),
    s1376=Shot("IMG_1376", 0.6, 1.35),
    s1375h=Shot("IMG_1375", 2.2, 1.4, ifps=60),
    s1380=Shot("IMG_1380", 1.0, 3.9, ifps=60),
)
LAST_USE = dict(hook=2.55, s1370=4.5, s1364=6.5, s1368a=8.6, s1353=10.55, s1355=12.4, s1374=16.6, s1366=17.7,
                s1360=18.65, s1357=19.85, s1367=20.5, s1368b=21.55, s1376=22.8, s1375h=24.55, s1380=30.5)

# ------------------------------------------------------------------ precálculos
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
RC = np.hypot(XX - W / 2, YY - H / 2)
THETA = np.arctan2(YY - H / 2, XX - W / 2)
VIGNETTE = (1 - 0.42 * np.clip(RC / np.hypot(W / 2, H / 2), 0, 1) ** 2.2)[..., None]
LOWER = (1 - 0.55 * np.clip((YY - 1050) / 600, 0, 1) ** 1.3 * np.clip((1750 - YY) / 300 + 0.6, 0, 1))[..., None]
_rng = np.random.default_rng(5)
GRAIN = [(_rng.normal(0, 0.022, (H // 2, W // 2)).astype(np.float32)) for _ in range(6)]
BG_DEEP = (np.array([0.13, 0.02, 0.045], np.float32) * np.exp(-(RC / 900) ** 2)[..., None]
           + np.array([0.012, 0.004, 0.006], np.float32))
WARM = np.array([1.0, 0.78, 0.5], np.float32)

CORK_BIG = make_cork(seed=4, diam=620, length=1600)
GLINT = star_glint(300)
DUST = Dust(160, 3, rise=36)
DUST_LOGO = Dust(220, 9, rise=60)
LOGO_W = 860
LOGO = logo_mask(LOGO_W)
LOGO_X, LOGO_Y = (W - LOGO_W) // 2, 430
LOGO_GLOW = np.asarray(Image.fromarray((LOGO * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(28)), np.float32) / 255

_r = np.random.default_rng(21)
DROPS = [dict(a=_r.uniform(0, 6.283), v=_r.uniform(250, 1500), r=_r.uniform(3, 11), d=_r.uniform(0, 0.06)) for _ in range(18)]
SPIKES = [(_r.uniform(-math.pi, math.pi), _r.uniform(0.15, 0.45), _r.uniform(0.03, 0.07)) for _ in range(14)]

# rampa de velocidad de la toma de copas
_u = np.arange(0, 4.4, 0.001)
_v = np.where(_u < 0.45, 2.4, np.where(_u > 1.25, 0.35, 0.35 + 2.05 * (0.5 + 0.5 * np.cos(np.pi * (_u - 0.45) / 0.8))))
RAMP_SRC = np.cumsum(_v) * 0.001


def ramp(u):
    i = int(np.clip(u * 1000, 0, len(_u) - 1))
    return RAMP_SRC[i], _v[i]


# ------------------------------------------------------------------ utilidades de imagen
def blur(img, radius):
    """Desenfoque gaussiano rápido (trabaja a 1/4 de resolución)."""
    if radius < 0.5:
        return img
    small = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BILINEAR)
    small = small.filter(ImageFilter.GaussianBlur(radius / 4))
    return np.asarray(small.resize((W, H), Image.BICUBIC), np.float32) / 255


def gather(img, sx, sy):
    xi = np.clip(sx, 0, W - 1).astype(np.int32)
    yi = np.clip(sy, 0, H - 1).astype(np.int32)
    return img[yi, xi]


def gain(img, g):
    return img * g


def finish(f, idx, bloom=0.32):
    small = Image.fromarray((np.clip(f, 0, 1) * 255).astype(np.uint8)).resize((W // 8, H // 8), Image.BILINEAR)
    hl = np.clip(np.asarray(small, np.float32) / 255 - 0.62, 0, 1) * 2.6
    hl = Image.fromarray((np.clip(hl, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7))
    hl = np.asarray(hl.resize((W, H), Image.BICUBIC), np.float32) / 255
    f = f + hl * WARM * bloom
    f = f * VIGNETTE
    g = GRAIN[idx % 6]
    f = f + np.repeat(np.repeat(g, 2, 0), 2, 1)[..., None]
    return np.clip(f, 0, 1)


# ------------------------------------------------------------------ CGI: corcho y gotas
def cork_state(t):
    s = 0.035 * math.exp(8.2 * t)
    fore = 0.45 + 0.55 * abs(math.cos(1.2 + 9 * t))
    return (540 + 40 * math.sin(3 * t), 960 - 140 * (1 - min(t, 1)), s * fore, s, 20 + 260 * t)


def draw_cork(frame, t, n=5):
    acc_c = np.zeros((H, W, 3), np.float32); acc_a = np.zeros((H, W), np.float32)
    for i in range(n):
        ts = t + (i / (n - 1) - 0.5) * 0.35 / FPS
        cx, cy, sx, sy, ang = cork_state(max(0.0, ts))
        if sy > 7:
            sy = 7; sx = min(sx, 7)
        c, a = affine_blit(CORK_BIG, cx, cy, sx, sy, ang)
        acc_c += c * a[..., None]; acc_a += a
    acc_c /= n; acc_a /= n
    return frame * (1 - acc_a[..., None]) + acc_c


def draw_drops(frame, t):
    """Gotas de vino que salen con el descorche: elipses estiradas según su velocidad, con brillo especular."""
    if t < T["pop"]:
        return frame
    from PIL import ImageDraw
    ss = 2
    layer = Image.new("RGBA", (W // ss, H // ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = 540, 820
    for p in DROPS:
        dt = t - T["pop"] - p["d"]
        if dt <= 0:
            continue
        grow = 1 + 5 * dt
        dist = p["v"] * dt * grow
        ca, sa = math.cos(p["a"]), math.sin(p["a"])
        x, y = cx + ca * dist, cy + sa * dist + 300 * dt * dt
        r = p["r"] * grow
        stretch = 1 + min(3.0, p["v"] * grow / 500)
        pts = []
        for k in range(24):  # gota: elipse alargada en la dirección del movimiento
            th = k / 24 * 2 * math.pi
            ex = math.cos(th) * r * stretch * (1.25 if math.cos(th) < 0 else 1.0)
            ey = math.sin(th) * r * (1 - 0.25 * max(0, -math.cos(th)))
            pts.append(((x + ex * ca - ey * sa) / ss, (y + ex * sa + ey * ca) / ss))
        d.polygon(pts, fill=(92, 6, 26, 240))
        hx, hy = x + ca * r * 0.3 - sa * r * 0.35, y + sa * r * 0.3 + ca * r * 0.35
        d.ellipse([(hx - r * 0.28) / ss, (hy - r * 0.28) / ss, (hx + r * 0.28) / ss, (hy + r * 0.28) / ss], fill=(255, 215, 220, 170))
    layer = layer.filter(ImageFilter.GaussianBlur(0.9)).resize((W, H), Image.BILINEAR)
    a = np.asarray(layer, np.float32) / 255
    return frame * (1 - a[..., 3:4]) + a[..., :3] * a[..., 3:4]


# ------------------------------------------------------------------ transiciones líquidas
# ------------------------------------------------------------------ secciones


def whip_h(t):
    u0 = (t - 4.1) / 0.36
    fa = S["s1370"].view(t - 2.5, 1.0 + 0.08 * (t - 2.5) / 2)
    fb = S["s1364"].view(t - 4.1, 1.0)
    strip = np.concatenate([fa, fb], axis=1)
    acc = np.zeros((H, W, 3), np.float32)
    n = 10
    for i in range(n):
        d = ease_io(u0 + (i / (n - 1) - 0.5) / FPS / 0.36 * 1.4)
        o = int(d * W)
        acc += strip[:, o:o + W]
    return acc / n, 0.3


def sec_1364(t):
    st = t - 4.1
    if t < 6.1:
        f = S["s1364"].view(st, 1.0 + 0.05 * (t - 4.46) / 1.6)
        return f, 0.3
    zf = lambda tt: 1.05 + 5 * ease_in((tt - 6.1) / 0.37, 3)
    f = zoom_blur(S["s1364"], st, zf(t - 0.6 / FPS), zf(t), 0.52, 0.47, n=7)
    dip = 1 - 0.85 * ease_in((t - 6.2) / 0.27, 2)
    f = f * dip + (1 - dip) * np.array([0.02, 0.04, 0.03], np.float32)
    return f, 0.3


def sec_1368a(t):
    st = t - 6.47
    zf = lambda tt: 1 + 3 * (1 - ease_out((tt - 6.47) / 0.5, 3))
    z0, z1 = zf(t - 0.6 / FPS), zf(t)
    f = zoom_blur(S["s1368a"], st, z0, z1, 0.5, 0.5, n=6) if z0 - z1 > 0.01 else S["s1368a"].view(st, z1)
    f = f * (0.15 + 0.85 * ease_out((t - 6.47) / 0.2))
    f = f * LOWER
    f = kinetic(f, t, 6.95, 8.15, "DESTILADOS", 1330, 150, SERIF, 0.12)
    return f, 0.32






def sec_1374(t):
    u = t - 12.35
    st, v = ramp(u)
    f = S["s1374"].view(st, 1.0 + 0.1 * clamp01(u / 4.2), span=min(0.12, v / FPS * 0.9))
    if 13.55 < t < 14.15:  # destello sobre el cristal de una copa
        k = math.sin(math.pi * (t - 13.55) / 0.6)
        g = GLINT * k * 1.0
        gh, gw = g.shape
        x0, y0 = GLASS[0] - gw // 2, GLASS[1] - gh // 2
        f[y0:y0 + gh, x0:x0 + gw] += g[..., None] * np.array([1.0, 0.92, 0.8], np.float32)
    f = f * LOWER
    f = kinetic(f, t, 14.0, 15.75, "EL ARTE DE ELEGIR", 1330, 96, SERIF, 0.16)
    return f, 0.33


def whip_v(t):
    u0 = (t - 18.25) / 0.34
    fa, _ = sec_1360(t)
    fb = S["s1357"].view(t - 18.25, 1.0)
    strip = np.concatenate([fa, fb], axis=0)
    acc = np.zeros((H, W, 3), np.float32)
    n = 10
    for i in range(n):
        d = ease_io(u0 + (i / (n - 1) - 0.5) / FPS / 0.34 * 1.4)
        o = int(d * H)
        acc += strip[o:o + H]
    return acc / n, 0.3


def sec_1375h(t):
    f = S["s1375h"].view((t - 22.25) * 0.5, 1.05 - 0.05 * clamp01((t - 22.75) / 2))
    f = f + DUST.render(t - 22.25, 0.9)
    f = f * LOWER
    f = kinetic(f, t, 22.95, 24.2, "VINOS · DESTILADOS · REGALOS", 1330, 54, SERIF, 0.22)
    return f, 0.36


def sec_1380(t):
    f = S["s1380"].view((t - 24.2) * 0.6, 1.0 + 0.06 * clamp01((t - 24.8) / 5))
    f = f * LOWER
    f = kinetic(f, t, 25.15, 27.3, "ENVÍOS A DOMICILIO", 1330, 96, SERIF, 0.12)
    f = kinetic(f, t, 27.45, 30.0, "ESCRIBINOS", 1310, 150, SERIF, 0.14)
    f = kinetic(f, t, 27.75, 30.0, "y recibilo en tu casa", 1440, 66, SERIF_IT, 0.02, sweep=False,
                color=np.array([0.96, 0.92, 0.86], np.float32))
    return f, 0.34


LY0, LX0 = LOGO_Y, LOGO_X
LH, LW = LOGO.shape


# ------------------------------------------------------------------ transiciones v2
GLASS = (713, 768)  # brillo de una copa en la toma de cristalería
CORK_FULL = None


def cork_fullframe():
    """Textura del corcho desenfocada a pantalla completa: lo que ve la lente cuando el corcho pasa pegado."""
    global CORK_FULL
    if CORK_FULL is None:
        spr = CORK_BIG.convert("RGB")
        w = spr.size[0]
        crop = spr.crop((60, 300, w - 60, 300 + int((w - 120) * 16 / 9)))
        img = crop.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(28))
        CORK_FULL = np.asarray(img, np.float32) / 255 * 0.75
    return CORK_FULL


def hook_zoom(tt):
    return 2.8 - 1.8 * ease_out((tt - 0.5) / 1.8, 3)


def hook_view(t):
    st = t - 0.5
    z, zp = hook_zoom(t), hook_zoom(t - 1 / FPS)
    if zp - z > 0.015:
        return zoom_blur(S["hook"], st, zp, z, 0.55, 0.58, n=4)
    return S["hook"].view(st, z, 0.55, 0.58)


def hook(t):
    if t < 0.5:
        f = BG_DEEP.copy() * (0.6 + 0.4 * t / 0.5)
        f = draw_cork(f, t)
    else:
        f = hook_view(t)
    f = draw_drops(f, t)
    a = math.sin(math.pi * clamp01((t - 0.38) / 0.24))
    if a > 0:
        cf = np.roll(cork_fullframe(), int((t - 0.38) * 2400), axis=0)
        f = f * (1 - a) + cf * a
    return f, 0.4


def hook_footage(t):
    f = hook_view(t) * (0.8 + 0.2 * clamp01((t - 2.4) / 0.1))
    f = kinetic(f, t, 0.85, 2.45, "DESCORCHÁ", 880, 130, SERIF, 0.10)
    f = kinetic(f, t, 1.3, 2.45, "LO EXTRAORDINARIO", 1030, 62, SERIF, 0.32, sweep=False,
                color=np.array([0.95, 0.9, 0.82], np.float32))
    return f, 0.35


def punch(st, amount=0.06, dur=0.35):
    return 1 + amount * (1 - ease_out(st / dur))


def sec_1370(t):
    st = t - 2.5
    f = S["s1370"].view(st, punch(st) + 0.08 * st / 2 - 0.0) * LOWER
    return kinetic(f, t, 2.72, 3.95, "VINOS", 1330, 250, SERIF, 0.18), 0.32


LEAKS = [(-200, 1500, 900, 300, 520, (1.0, 0.55, 0.18), 1.0), (1300, 200, 200, 1400, 420, (1.0, 0.78, 0.42), 0.8),
         (500, 2200, 700, -200, 600, (0.85, 0.22, 0.12), 0.6)]
LY4, LX4 = np.mgrid[0:H // 4, 0:W // 4].astype(np.float32) * 4


def leak_layer(u):
    L = np.zeros((H // 4, W // 4, 3), np.float32)
    for x0, y0, x1, y1, r, col, amp in LEAKS:
        cx, cy = x0 + (x1 - x0) * u, y0 + (y1 - y0) * u
        L += np.exp(-((LX4 - cx) ** 2 + (LY4 - cy) ** 2) / (2 * r * r))[..., None] * np.array(col, np.float32) * amp
    img = Image.fromarray((np.clip(L, 0, 1) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)
    return np.asarray(img, np.float32) / 255


def light_leak(t):
    u = clamp01((t - 8.05) / 0.5)
    fa, _ = sec_1368a(t)
    fb = S["s1353"].view(t - 8.05, 1.04) * LOWER
    mix = ease_io((u - 0.3) / 0.4)
    f = np.clip(fa * (1 - mix) + fb * mix, 0, 1)
    L = np.clip(leak_layer(u) * math.sin(math.pi * u) ** 1.2 * 1.1, 0, 1)
    return 1 - (1 - f) * (1 - L), 0.45


def sec_1353(t):
    f = S["s1353"].view(t - 8.05, 1.04 - 0.04 * clamp01((t - 8.55) / 1.9)) * LOWER
    return kinetic(f, t, 8.72, 10.15, "REGALOS", 1330, 200, SERIF, 0.14), 0.32


def sec_1355(t):
    st = t - 10.5
    return S["s1355"].view(st, punch(st, 0.05)) * (1 + 0.18 * math.exp(-st / 0.05)), 0.32


def rot_frame(img, ang, scale):
    pil = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    a = math.radians(ang); ca, sa = math.cos(a), math.sin(a)
    m00, m01, m10, m11 = ca / scale, sa / scale, -sa / scale, ca / scale
    c0 = W / 2 - (m00 * W / 2 + m01 * H / 2); c1 = H / 2 - (m10 * W / 2 + m11 * H / 2)
    out = pil.transform((W, H), Image.AFFINE, (m00, m01, c0, m10, m11, c1), resample=Image.BILINEAR)
    return np.asarray(out, np.float32) / 255


def roll(t):
    """Giro de cámara: la toma gira acelerando, corte a 90°, la siguiente llega girando y frena."""
    u = (t - 12.05) / 0.6
    img = S["s1355"].view(t - 10.5, 1.0) if u < 0.5 else S["s1374"].view(ramp(t - 12.35)[0], 1.0)
    acc = np.zeros((H, W, 3), np.float32); n = 7
    for i in range(n):
        us = u + (i / (n - 1) - 0.5) / FPS / 0.6
        ang = 90 * ease_in(us / 0.5, 3) if u < 0.5 else -90 * (1 - ease_out((us - 0.5) / 0.5, 3))
        acc += rot_frame(img, ang, 1 + 1.15 * math.sin(math.pi * clamp01(us)) ** 0.7)
    return acc / n, 0.3


def focus_pull(t, t0, dur, fa_fn, fb_fn, rmax=34):
    u = clamp01((t - t0) / dur)
    r = rmax * math.sin(math.pi * u)
    mix = ease_io((u - 0.35) / 0.3)
    f = 0
    if mix < 1:
        f = f + fa_fn(t) * (1 - mix)
    if mix > 0:
        f = f + fb_fn(t) * mix
    f = blur(f, r)
    return f + np.clip(f - 0.65, 0, 1) * 0.9 * (r / rmax), 0.5


def glass_to_lamps(t):
    return focus_pull(t, 15.95, 0.6, lambda tt: sec_1374(tt)[0], lambda tt: S["s1366"].view(tt - 15.95, 1.0))


def sec_1366(t):
    return S["s1366"].view(t - 15.95, 1.0 + 0.04 * (t - 16.55)), 0.35


def lamp_bloom(t):
    u = clamp01((t - 17.25) / 0.4)
    k = math.sin(math.pi * u)
    fa = S["s1366"].view(t - 15.95, 1.0 + 0.04 * (t - 16.55))
    fb = S["s1360"].view(t - 17.3, 1.06 - 0.06 * ease_out(u))
    mix = ease_io((u - 0.35) / 0.3)
    return (fa * (1 - mix) + fb * mix) * (1 + 1.6 * k), 0.35 + 0.9 * k


def sec_1360(t):
    return S["s1360"].view(t - 17.3, 1.0), 0.32


def sec_1357(t):
    return S["s1357"].view(t - 18.25, 1.0 + 0.04 * (t - 18.6)), 0.3


_g = np.random.default_rng(8).random(H // 8).astype(np.float32)
_g = np.asarray(Image.fromarray((_g * 255).astype(np.uint8)[:, None]).resize((1, H), Image.BICUBIC), np.float32)[:, 0] / 255
BAR = (np.array([0.065, 0.038, 0.027], np.float32) * (0.75 + 0.5 * _g)[:, None])[:, None, :]


def pass_by(t):
    """Una columna oscura del local pasa pegada a la lente y tapa el corte."""
    u = clamp01((t - 19.3) / 0.5)
    fa = sec_1357(t)[0]
    fb = S["s1367"].view(t - 19.5, 1.0)
    xc = -520 + (W + 1040) * ease_io(u)
    x = XX[0]
    reveal = np.clip((xc - x) / 6 + 0.5, 0, 1)[None, :, None]
    f = fa * (1 - reveal) + fb * reveal
    shade = np.clip((560 - np.abs(x - xc)) / 220, 0, 1)[None, :, None] * 0.35
    a = np.clip((380 - np.abs(x - xc)) / 140 + 0.5, 0, 1)[None, :, None]
    f = f * (1 - shade)
    return f * (1 - a) + BAR * a, 0.3


def sec_1367(t):
    return S["s1367"].view(t - 19.5, 1.0), 0.3


def speed_cut(t):
    """Rampa de velocidad: la toma acelera hasta el corte y la siguiente arranca rápida y frena."""
    if t < 20.45:
        x = clamp01((t - 20.2) / 0.25)
        v = 1 + 3 * x * x
        return S["s1367"].view((t - 19.5) + 0.25 * x ** 3, 1.0, span=v / FPS * 0.9), 0.3
    x = clamp01((t - 20.45) / 0.3)
    v = 1 + 3 * (1 - x) ** 2
    return S["s1368b"].view((t - 20.45) + 0.3 * (1 - (1 - x) ** 3), 1.0, span=v / FPS * 0.9), 0.3


def sec_1368b(t):
    return S["s1368b"].view(t - 20.45 + 0.3, 1.0), 0.32


def sec_1376(t):
    st = t - 21.5
    k = math.exp(-st / 0.1)
    r = np.random.default_rng(int(t * 1000))
    f = S["s1376"].view(st, punch(st, 0.10), 0.5 + r.normal(0, 0.004 * k), 0.5 + r.normal(0, 0.004 * k))
    return f * (1 + 0.12 * k), 0.32


def dissolve_hero(t):
    mix = ease_io((t - 22.25) / 0.5)
    return sec_1376(t)[0] * (1 - mix) + sec_1375h(t)[0] * mix, 0.4


def push_cut(t):
    """Empuje de cámara que acelera, corte, y la toma siguiente continúa el movimiento y frena."""
    if t < 24.5:
        zf = lambda tt: 1.05 + 0.5 * ease_in((tt - 24.2) / 0.3, 3)
        f = zoom_blur(S["s1375h"], (t - 22.25) * 0.5, zf(t - 0.6 / FPS), zf(t), 0.5, 0.5, n=6)
        f = f + DUST.render(t - 22.25, 0.9)
    else:
        zf = lambda tt: 1.35 - 0.35 * ease_out((tt - 24.5) / 0.3, 3)
        z0, z1 = zf(t - 0.6 / FPS), zf(t)
        f = zoom_blur(S["s1380"], (t - 24.2) * 0.6, z0, z1, 0.5, 0.5, n=6) if z0 - z1 > 0.005 else S["s1380"].view((t - 24.2) * 0.6, z1)
    return f * LOWER, 0.36


def fade_black(t):
    f, b = sec_1380(t)
    return f * (1 - ease_in((t - 30.0) / 0.42, 2)), b


def logo_scene(t):
    u = t - 30.5
    f = BG_DEEP.copy() + DUST_LOGO.render(max(0.0, u), 0.6 * clamp01(u / 1.2))
    if u > 0:
        a = ease_out(u / 0.9, 2)
        sc = 1.06 - 0.06 * ease_out(u / 1.4, 3)
        bl = 14 * (1 - ease_out(u / 0.8, 2))
        img = Image.fromarray((LOGO * 255).astype(np.uint8)).resize((int(LW * sc), int(LH * sc)), Image.BICUBIC)
        if bl > 0.3:
            img = img.filter(ImageFilter.GaussianBlur(bl))
        m = np.asarray(img, np.float32) / 255
        mh, mw = m.shape
        region = f[LY0:LY0 + LH, LX0:LX0 + LW]
        region += LOGO_GLOW[..., None] * np.array([0.9, 0.6, 0.25], np.float32) * 0.3 * a
        f = put_layer(f, m, gold_fill(mh, mw, clamp01((t - 31.2) / 0.9)), (W - mw) / 2, LY0 + LH / 2 - mh / 2, a, shadow=0)
    if t > 32.15:
        lw = int(280 * ease_out((t - 32.15) / 0.5))
        f[1205:1208, W // 2 - lw // 2:W // 2 + lw // 2] = np.array([0.86, 0.69, 0.38], np.float32)
    f = kinetic(f, t, 32.3, 99, "ENVÍOS A DOMICILIO", 1270, 50, SERIF, 0.34)
    f = kinetic(f, t, 32.6, 99, "@estilovinos", 1365, 80, SERIF, 0.04, sweep=False, color=np.array([0.97, 0.95, 0.92], np.float32))
    f = kinetic(f, t, 32.9, 99, "INDEPENDENCIA 1001", 1455, 44, SERIF, 0.32, sweep=False, color=np.array([0.85, 0.80, 0.74], np.float32))
    return f * (1 - ease_in((t - 35.5) / 0.5, 1.5)), 0.4


# ------------------------------------------------------------------ línea de tiempo
TIMELINE = [
    (0.0, 0.62, hook), (0.62, 2.5, hook_footage), (2.5, 4.1, sec_1370), (4.1, 4.46, whip_h),
    (4.46, 6.47, sec_1364), (6.47, 8.05, sec_1368a), (8.05, 8.55, light_leak), (8.55, 10.5, sec_1353),
    (10.5, 12.05, sec_1355), (12.05, 12.65, roll), (12.65, 15.95, sec_1374), (15.95, 16.55, glass_to_lamps),
    (16.55, 17.25, sec_1366), (17.25, 17.65, lamp_bloom), (17.65, 18.25, sec_1360), (18.25, 18.6, whip_v),
    (18.6, 19.3, sec_1357), (19.3, 19.8, pass_by), (19.8, 20.2, sec_1367), (20.2, 20.75, speed_cut),
    (20.75, 21.5, sec_1368b), (21.5, 22.25, sec_1376), (22.25, 22.75, dissolve_hero), (22.75, 24.2, sec_1375h),
    (24.2, 24.8, push_cut), (24.8, 30.0, sec_1380), (30.0, 30.45, fade_black), (30.45, 36.01, logo_scene),
]


def frame_at(t):
    for a, b, fn in TIMELINE:
        if a <= t < b:
            return fn(t)
    raise ValueError(t)


def release(t):
    for k, last in LAST_USE.items():
        if t > last and S[k].frames is not None:
            S[k].free()


def render_range(out, first, last):
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "19", "-preset", "medium",
                            "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(first, last):
        t = i / FPS
        f, bl = frame_at(t)
        enc.stdin.write((finish(f, i, bl) * 255 + 0.5).astype(np.uint8).tobytes())
        release(t)
    enc.stdin.close(); enc.wait()


def main():
    if sys.argv[1] == "--preview":
        times = [float(x) for x in sys.argv[2].split(",")]
        out = sys.argv[3]; os.makedirs(out, exist_ok=True)
        for t in times:
            f, bl = frame_at(t)
            f = finish(f, int(t * FPS), bl)
            Image.fromarray((f * 255).astype(np.uint8)).save(f"{out}/t{t:06.2f}.jpg", quality=88)
            print("preview", t, flush=True)
        return
    if sys.argv[1] == "--chunks":
        d = sys.argv[2]; os.makedirs(d, exist_ok=True)
        n = int(DURATION * FPS); size = 120
        for c in range(0, n, size):
            path = f"{d}/chunk_{c // size:03d}.mp4"
            if os.path.exists(path):
                continue
            render_range(path + ".part.mp4", c, min(n, c + size))
            os.replace(path + ".part.mp4", path)
            print(f"tramo {c // size} listo", flush=True)
        print("video listo (tramos)", flush=True)
        return
    out = sys.argv[1]
    n = int(DURATION * FPS)
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 0  # permite re-renderizar solo desde un cuadro
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "17", "-preset", "medium",
                            "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(first, n):
        t = i / FPS
        f, bl = frame_at(t)
        f = finish(f, i, bl)
        enc.stdin.write((f * 255 + 0.5).astype(np.uint8).tobytes())
        release(t)
        if i % 30 == 0:
            print(f"{t:5.1f}s / {DURATION}s", flush=True)
    enc.stdin.close()
    enc.wait()
    print("video listo", out)


if __name__ == "__main__":
    main()
