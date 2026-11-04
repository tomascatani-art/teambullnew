"""Spot ESTILO VINOS — compositor cuadro a cuadro (1080x1920, 30 fps).

Guion (120 BPM):
  0.0  GANCHO   un corcho de la marca sale disparado hacia cámara; al golpear, el vino abre un agujero
                que revela la tienda (macro -> plano general).  "DESCORCHÁ / LO EXTRAORDINARIO"
  2.5           las letras atraviesan la cámara y dan paso a la góndola. "VINOS"
  4.3           barrido de cámara (whip) siguiendo la línea de las estanterías
  6.5           la cámara se mete dentro de una botella oscura y sale en los destilados. "DESTILADOS"
  8.3           una estela de luz dorada cruza y descubre las cajas de regalo. "REGALOS"
 10.5           match cut entre cajas, con destello en el golpe musical
 12.35          una ola de vino (con refracción real sobre la imagen) cambia de escena
 12.35-16.5     rampa de velocidad: rápido -> cámara lenta sobre las copas; destello en el cristal
 16.0           el reflejo de una copa se abre como un portal hacia las lámparas
 17.45          las lámparas encandilan y la luz da paso a la siguiente góndola
 18.4           whip vertical; 19.5 lluvia de corchos; 20.45 las estanterías se separan en franjas
 21.5           impacto cromático; 22.5 la luz del local "quema" la imagen y revela el plano héroe
 22.5-24.5      respiro en cámara lenta con polvo dorado. "VINOS · DESTILADOS · REGALOS"
 24.5           cambio de foco; la clienta se lleva su compra. "ENVÍOS A DOMICILIO" / "ESCRIBINOS"
 30.45          el vino sube y llena la pantalla; el logo se llena de vino y se vuelve dorado. Datos y CTA.

Uso:
  python3 render.py out.mp4                 render completo
  python3 render.py --preview 0.3,6.4 dir   cuadros sueltos para revisar
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
    s1367=Shot("IMG_1367", 0.5, 1.2),
    s1368b=Shot("IMG_1368", 2.4, 1.3),
    s1376=Shot("IMG_1376", 0.6, 1.35),
    s1375h=Shot("IMG_1375", 2.2, 1.4, ifps=60),
    s1380=Shot("IMG_1380", 1.0, 3.9, ifps=60),
)
LAST_USE = dict(hook=2.7, s1370=4.5, s1364=6.5, s1368a=8.6, s1353=10.55, s1355=12.7, s1374=16.6, s1366=17.5,
                s1360=18.65, s1357=19.6, s1367=20.65, s1368b=21.55, s1376=22.8, s1375h=24.85, s1380=30.5)

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
GLINT = star_glint(520)
DUST = Dust(160, 3, rise=36)
DUST_LOGO = Dust(220, 9, rise=60)
LOGO_W = 860
LOGO = logo_mask(LOGO_W)
LOGO_X, LOGO_Y = (W - LOGO_W) // 2, 430
LOGO_GLOW = np.asarray(Image.fromarray((LOGO * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(28)), np.float32) / 255

_r = np.random.default_rng(21)
DROPS = [dict(a=_r.uniform(0, 6.283), v=_r.uniform(250, 1500), r=_r.uniform(3, 11), d=_r.uniform(0, 0.06)) for _ in range(42)]
SPIKES = [(_r.uniform(-math.pi, math.pi), _r.uniform(0.15, 0.45), _r.uniform(0.03, 0.07)) for _ in range(14)]

# rampa de velocidad de la toma de copas
_u = np.arange(0, 4.4, 0.001)
_v = np.where(_u < 0.45, 2.4, np.where(_u > 1.25, 0.35, 0.35 + 2.05 * (0.5 + 0.5 * np.cos(np.pi * (_u - 0.45) / 0.8))))
RAMP_SRC = np.cumsum(_v) * 0.001


def ramp(u):
    i = int(np.clip(u * 1000, 0, len(_u) - 1))
    return RAMP_SRC[i], _v[i]


def cork_rain_frame(i):
    p = os.path.join(FXDIR, "cork_rain", f"{i:04d}.png")
    if not os.path.exists(p):
        return None
    a = np.asarray(Image.open(p), np.float32) / 255
    return a[..., :3], a[..., 3:4]


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
def wine_sheet(u, seed=0):
    """Lámina de vino que baja: devuelve (cobertura 0..1, distancia al borde frontal, distancia al trasero)."""
    x = XX[0]
    rng = np.random.default_rng(seed)
    drips = [(rng.uniform(0, W), rng.uniform(18, 45), rng.uniform(60, 220)) for _ in range(9)]
    p1 = ease_io(min(1, u / 0.46))
    bumps = sum(L * min(1, u / 0.46) * np.exp(-((x - c) / w) ** 2) for c, w, L in drips)
    front = -420 + (H + 520) * p1 + 9 * np.sin(x / 83 + u * 5) + 14 * np.sin(x / 217 + 1.3) + bumps
    p2 = ease_io(clamp01((u - 0.54) / 0.46))
    back = -260 + (H + 520) * p2 + 11 * np.sin(x / 97 + 2 + u * 4)
    df = front[None, :] - YY
    db = YY - back[None, :] if p2 > 0 else np.full((H, W), 1e4, np.float32)
    return df, db


def liquid_over(under, df, db):
    d = np.minimum(df, db)
    inside = np.clip(d / 1.5, 0, 1)[..., None]
    thick = np.clip(d, 0, None)
    disp = 38 * np.exp(-thick / 70)
    refr = gather(under, XX, YY - disp)
    opac = (1 - np.exp(-thick / 55))[..., None]
    depth = (0.62 + 0.38 * np.exp(-thick / 140))[..., None]
    wine = np.array([0.38, 0.03, 0.11], np.float32) * depth
    liquid = refr * np.array([0.9, 0.35, 0.4], np.float32) * (1 - opac) + wine * opac
    rim = (np.exp(-((df - 10) / 4.5) ** 2) * 0.5 + np.exp(-((db - 10) / 5) ** 2) * 0.3)[..., None]
    liquid = liquid * (1 - rim) + np.array([1.0, 0.8, 0.82], np.float32) * rim
    return under * (1 - inside) + liquid * inside


# ------------------------------------------------------------------ secciones
def hook(t):
    if t < T["hook_boom"]:
        f = BG_DEEP.copy() * (0.6 + 0.4 * t / 0.5)
        f = draw_cork(f, t)
        return draw_drops(f, t), 0.45
    # el vino abre un agujero que revela la tienda
    u = (t - T["hook_boom"]) / 0.42
    R = 2300 * (1 - (1 - clamp01(u)) ** 2)
    edge = R * (1 + 0.08 * np.sin(5 * THETA + 1) + 0.06 * np.sin(11 * THETA + 2))
    for a, amp, wd in SPIKES:
        dth = np.angle(np.exp(1j * (THETA - a)))
        edge = edge + R * amp * np.exp(-(dth / wd) ** 2)
    st = t - 0.5
    z = 2.8 - 1.8 * ease_out(st / 1.8, 3)
    inner = zoom_blur(S["hook"], st, z + 0.12, z, 0.55, 0.58, n=4)
    outer = draw_cork(BG_DEEP.copy(), t)
    m = np.clip((edge - RC) / 2.5, 0, 1)[..., None]
    rim = np.exp(-((RC - edge - 10) / 14) ** 2)[..., None]
    f = outer * (1 - m) + inner * m
    f = f * (1 - rim) + (np.array([0.42, 0.03, 0.12], np.float32) + 0.5 * np.exp(-((RC - edge - 4) / 3) ** 2)[..., None]) * rim
    f = f + np.array([1, 0.85, 0.7], np.float32) * 0.6 * math.exp(-(t - 0.5) / 0.06)
    return draw_drops(f, t), 0.4


HOOK_TXT = text_mask("DESCORCHÁ", 130, SERIF, 0.10)
HOOK_SUB = text_mask("LO EXTRAORDINARIO", 62, SERIF, 0.32)


def hook_footage(t):
    st = t - 0.5
    z = 2.8 - 1.8 * ease_out(st / 1.8, 3)
    z_prev = 2.8 - 1.8 * ease_out((st - 1 / FPS) / 1.8, 3)
    f = zoom_blur(S["hook"], st, z_prev, z, 0.55, 0.58, n=4) if z_prev - z > 0.015 else S["hook"].view(st, z, 0.55, 0.58)
    f = f * (0.78 + 0.22 * clamp01((t - 2.45) / 0.1))
    if t < 2.38:
        f = kinetic(f, t, 0.85, 2.6, "DESCORCHÁ", 880, 130, SERIF, 0.10)
        f = kinetic(f, t, 1.3, 2.6, "LO EXTRAORDINARIO", 1030, 62, SERIF, 0.32, sweep=False, color=np.array([0.95, 0.9, 0.82], np.float32))
    return f, 0.35


def text_fly(f, t, t0):
    """Las letras vuelan hacia la cámara y la atraviesan."""
    u = clamp01((t - t0) / 0.3)
    s = 1 + 7 * ease_in(u, 2.4)
    a = 1 - ease_in(u, 1.3)
    for mask, y, col in ((HOOK_TXT, 880, None), (HOOK_SUB, 1030, np.array([0.95, 0.9, 0.82], np.float32))):
        mh, mw = mask.shape
        nw, nh = int(mw * s), int(mh * s)
        cy = 960 + (y - 960) * s
        x0, y0 = (W - nw) / 2, cy - nh / 2
        # recortar a pantalla antes de escalar
        sx0, sy0 = max(0, -x0) / s, max(0, -y0) / s
        sx1, sy1 = min(mw, (W - x0) / s), min(mh, (H - y0) / s)
        if sx1 <= sx0 or sy1 <= sy0:
            continue
        sub = Image.fromarray((mask * 255).astype(np.uint8)).crop((int(sx0), int(sy0), int(math.ceil(sx1)), int(math.ceil(sy1))))
        tw, th = max(1, int(sub.width * s)), max(1, int(sub.height * s))
        sub = sub.resize((tw, th), Image.BILINEAR).filter(ImageFilter.GaussianBlur(min(12, 1 + 3 * s * u)))
        m = np.asarray(sub, np.float32) / 255
        color = col if col is not None else np.array([0.92, 0.76, 0.45], np.float32)
        f = put_layer(f, m, color, max(0, x0) + 0, max(0, y0), a, shadow=0)
    return f


def sec_1370(t):
    st = t - 2.5
    fa = S["s1370"].view(st, 1.0 + 0.08 * st / 2)
    fa = fa * (1 + 1.4 * math.exp(-(t - 2.5) / 0.07))
    if t < 2.65:
        fa = text_fly(fa, t, 2.35)
    fa = fa * LOWER
    fa = kinetic(fa, t, 2.72, 3.95, "VINOS", 1330, 250, SERIF, 0.18)
    return fa, 0.32


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


ANG = math.radians(-65)
PROJ = (XX - W / 2) * math.cos(ANG) + (YY - H / 2) * math.sin(ANG)


def streak(t):
    u = (t - 8.05) / 0.5
    fa, _ = sec_1368a(t)
    fb = S["s1353"].view(t - 8.05, 1.04)
    p = -1150 + 2300 * ease_io(u)
    mix = np.clip((p - PROJ) / 20 + 0.5, 0, 1)[..., None]
    f = fa * (1 - mix) + fb * mix
    dd = PROJ - p
    glow = np.exp(-(dd / 12) ** 2) * 1.8 + np.exp(-(dd / 80) ** 2) * 0.55 + np.exp(-(dd / 320) ** 2) * 0.18
    f = f + glow[..., None] * WARM * math.sin(math.pi * clamp01(u)) ** 0.5
    return f, 0.5


def sec_1353(t):
    f = S["s1353"].view(t - 8.05, 1.04 - 0.04 * clamp01((t - 8.55) / 1.9))
    f = f * (1 + 0.5 * ease_in((t - 10.3) / 0.2, 2))
    f = f * LOWER
    f = kinetic(f, t, 8.72, 10.15, "REGALOS", 1330, 200, SERIF, 0.14)
    return f, 0.32


def sec_1355(t):
    st = t - 10.5
    z = 1.08 - 0.08 * ease_out(st / 0.3)
    f = S["s1355"].view(st, z)
    k = math.exp(-st / 0.07)
    f = f * (1 + 2.2 * k) + np.array([0.5, 0.35, 0.15], np.float32) * k
    return f, 0.32


def wine_wipe(t):
    u = (t - 12.05) / 0.6
    under = S["s1355"].view(t - 10.5, 1.0) if u < 0.5 else S["s1374"].view(ramp(t - 12.35)[0], 1.0)
    df, db = wine_sheet(u, seed=11)
    return liquid_over(under, df, db), 0.3


PORTAL_C = (713, 768)
PR = np.hypot(XX - PORTAL_C[0], YY - PORTAL_C[1])


def sec_1374(t):
    u = t - 12.35
    st, v = ramp(u)
    f = S["s1374"].view(st, 1.0 + 0.1 * clamp01(u / 4.2), span=min(0.12, v / FPS * 0.9))
    if 13.55 < t < 14.15:  # destello sobre el cristal de una copa
        k = math.sin(math.pi * (t - 13.55) / 0.6)
        g = GLINT * k * 1.6
        gh, gw = g.shape
        x0, y0 = PORTAL_C[0] - gw // 2, PORTAL_C[1] - gh // 2
        f[y0:y0 + gh, x0:x0 + gw] += g[..., None] * np.array([1.0, 0.92, 0.8], np.float32)
    f = f * LOWER
    f = kinetic(f, t, 14.0, 15.75, "EL ARTE DE ELEGIR", 1330, 96, SERIF, 0.16)
    return f, 0.33


def portal(t):
    u = clamp01((t - 15.95) / 0.6)
    R = 25 + 2600 * ease_in(u, 2.2)
    cur, _ = sec_1374(t)
    nxt = S["s1366"].view(t - 15.95, 1.0)
    rn = PR / max(R, 1)
    k = 0.55 + 0.45 * np.clip(rn, 0, 1) ** 2  # lente: magnifica el centro del portal
    inner = gather(nxt, PORTAL_C[0] + (XX - PORTAL_C[0]) * k, PORTAL_C[1] + (YY - PORTAL_C[1]) * k)
    push = 1 - 55 * np.exp(-((PR - R) / 60) ** 2) / np.maximum(PR, 1)
    outer = gather(cur, PORTAL_C[0] + (XX - PORTAL_C[0]) * push, PORTAL_C[1] + (YY - PORTAL_C[1]) * push)
    m = np.clip((R - PR) / 2, 0, 1)[..., None]
    f = outer * (1 - m) + inner * m
    rim = np.exp(-((PR - R) / 6) ** 2)[..., None]
    f = f + rim * np.array([1.0, 0.86, 0.6], np.float32) * 1.2
    return f, 0.4


def sec_1366(t):
    st = t - 15.95
    f = S["s1366"].view(st, 1.0)
    g = 1 + 6 * ease_in((t - 17.2) / 0.25, 2)
    return f * g, 0.35 + 1.2 * ease_in((t - 17.2) / 0.25, 2)


def sec_1360(t):
    st = t - 17.3
    k = 1 - ease_out((t - 17.45) / 0.28)
    f = S["s1360"].view(st, 1.12 - 0.12 * ease_out((t - 17.45) / 0.6))
    return f * (1 + 5 * k), 0.35 + 1.2 * k


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


def sec_1357(t):
    if t < T["corkrain"]:
        f = S["s1357"].view(t - 18.25, 1.0 + 0.04 * (t - 18.6))
    else:
        f = S["s1367"].view(t - 19.5, 1.0)
    i = int(round((t - 19.0) * FPS))
    if 0 <= i < 36:
        r = cork_rain_frame(i)
        if r is not None:
            f = f * (1 - r[1]) + r[0] * r[1]
    return f, 0.3


def slices(t):
    st_a = t - 19.5
    fa = S["s1367"].view(st_a, 1.0)
    fb = S["s1368b"].view(t - 20.3, 1.1 - 0.1 * ease_out((t - 20.3) / 0.5))
    if t < 20.3:
        return sec_1357(t)
    f = fb.copy()
    bands = 6
    bh = H // bands
    for i in range(bands):
        sl = slice(i * bh, (i + 1) * bh if i < bands - 1 else H)
        acc = np.zeros_like(fa[sl]); n = 6
        for k in range(n):
            tt = t + (k / (n - 1) - 0.5) / FPS
            d = ease_in((tt - 20.3 - i * 0.025) / 0.25, 2.2)
            o = int(d * W * 1.05) * (1 if i % 2 == 0 else -1)
            band = np.zeros_like(fa[sl]); alpha = np.zeros(band.shape[:2] + (1,), np.float32)
            if abs(o) < W:
                if o >= 0:
                    band[:, o:] = fa[sl][:, :W - o]; alpha[:, o:] = 1
                else:
                    band[:, :W + o] = fa[sl][:, -o:]; alpha[:, :W + o] = 1
            acc += band * alpha + fb[sl] * (1 - alpha)
        f[sl] = acc / n
    return f, 0.3


def sec_1368b(t):
    return S["s1368b"].view(t - 20.3, 1.1 - 0.1 * ease_out((t - 20.3) / 0.5)), 0.32


def sec_1376(t):
    st = t - 21.5
    k = math.exp(-st / 0.09)
    r = np.random.default_rng(int(t * 1000))
    jx, jy = r.normal(0, 0.012 * k), r.normal(0, 0.012 * k)
    f = S["s1376"].view(st, 1.06 - 0.06 * ease_out(st / 0.3) + 0.001, 0.5 + jx, 0.5 + jy)
    sh = int(30 * k)
    if sh > 0:
        f = f.copy()
        f[..., 0] = np.roll(f[..., 0], sh, axis=1)
        f[..., 2] = np.roll(f[..., 2], -sh, axis=1)
    return f * (1 + 0.6 * k), 0.32


def burn(t):
    u = clamp01((t - 22.25) / 0.5)
    fa, _ = sec_1376(t)
    fb = S["s1375h"].view((t - 22.25) * 0.5, 1.05)
    lum = fa @ np.array([0.3, 0.55, 0.15], np.float32)
    thr = 1.05 - 1.2 * ease_io(u)
    m = np.clip((lum - thr) / 0.12, 0, 1)
    m = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)[..., None] / 255
    edge = m * (1 - m) * 4
    f = fa * (1 - m) + fb * m + edge * WARM * 0.9
    return f, 0.5


def sec_1375h(t):
    f = S["s1375h"].view((t - 22.25) * 0.5, 1.05 - 0.05 * clamp01((t - 22.75) / 2))
    f = f + DUST.render(t - 22.25, 0.9)
    f = f * LOWER
    f = kinetic(f, t, 22.95, 24.2, "VINOS · DESTILADOS · REGALOS", 1330, 54, SERIF, 0.22)
    return f, 0.36


def rack_focus(t):
    u = clamp01((t - 24.2) / 0.6)
    r = 30 * math.sin(math.pi * u)
    mix = ease_io((u - 0.35) / 0.3)
    fa = sec_1375h(t)[0] if mix < 1 else 0
    fb = S["s1380"].view((t - 24.2) * 0.6, 1.0) if mix > 0 else 0
    f = fa * (1 - mix) + fb * mix
    f = blur(f, r)
    return f + np.clip(f - 0.7, 0, 1) * 0.8 * (r / 30), 0.5


def sec_1380(t):
    f = S["s1380"].view((t - 24.2) * 0.6, 1.0 + 0.06 * clamp01((t - 24.8) / 5))
    f = f * LOWER
    f = kinetic(f, t, 25.15, 27.3, "ENVÍOS A DOMICILIO", 1330, 96, SERIF, 0.12)
    f = kinetic(f, t, 27.45, 30.0, "ESCRIBINOS", 1310, 150, SERIF, 0.14)
    f = kinetic(f, t, 27.75, 30.0, "y recibilo en tu casa", 1440, 66, SERIF_IT, 0.02, sweep=False,
                color=np.array([0.96, 0.92, 0.86], np.float32))
    return f, 0.34


def wine_rise(t):
    u = clamp01((t - 29.85) / 0.6)
    under, _ = sec_1380(t)
    level = H + 120 - (H + 300) * ease_in(u, 1.6)
    x = XX[0]
    surf = level + 22 * np.sin(x / 90 + 9 * u) + 11 * np.sin(x / 37 - 5 * u)
    d = YY - surf[None, :]
    inside = np.clip(d / 1.5, 0, 1)[..., None]
    th = np.clip(d, 0, None)
    refr = gather(under, XX, YY - 34 * np.exp(-th / 60))
    opac = (1 - np.exp(-th / 70))[..., None]
    liquid = refr * np.array([0.9, 0.35, 0.4], np.float32) * (1 - opac) + np.array([0.36, 0.03, 0.1], np.float32) * opac
    men = np.exp(-((d - 4) / 3) ** 2)[..., None]
    liquid = liquid * (1 - men * 0.7) + np.array([1, 0.75, 0.75], np.float32) * men * 0.7
    return under * (1 - inside) + liquid * inside, 0.35


LY0, LX0 = LOGO_Y, LOGO_X
LH, LW = LOGO.shape
LYY = np.arange(LH, dtype=np.float32)[:, None]
LXX = np.arange(LW, dtype=np.float32)[None, :]


def logo_scene(t):
    u = (t - T["wine_rise"])
    flat = np.broadcast_to(np.array([0.36, 0.03, 0.1], np.float32), (H, W, 3))
    f = flat * (1 - ease_out(u / 0.7)) + BG_DEEP * ease_out(u / 0.7)
    f = f + DUST_LOGO.render(u, 0.7 * clamp01(u / 1.0))
    # resplandor detrás del logo
    gl = clamp01((t - 31.6) / 0.6) * 0.35
    region = f[LY0:LY0 + LH, LX0:LX0 + LW]
    region += LOGO_GLOW[..., None] * np.array([0.9, 0.6, 0.25], np.float32) * gl
    # 1) el vino llena las letras
    fill_u = ease_io((t - 30.6) / 0.95)
    level = LH + 20 - (LH + 60) * fill_u
    surf = level + 10 * np.sin(LXX / 40 + 12 * t)
    filled = np.clip((LYY - surf) / 2, 0, 1)
    near = np.exp(-((LYY - surf - 5) / 4) ** 2)
    wine_col = np.array([0.55, 0.05, 0.15], np.float32) * (0.75 + 0.25 * np.exp(-(LYY - surf).clip(0) / 60))[..., None] \
        + near[..., None] * np.array([0.9, 0.6, 0.6], np.float32) * 0.6
    outline = np.array([1, 1, 1], np.float32) * 0.13
    col = wine_col * filled[..., None] + outline * (1 - filled[..., None])
    # 2) el vino se vuelve oro, con un barrido de luz
    gm = ease_io((t - 31.5) / 0.55)
    if gm > 0:
        gold = gold_fill(LH, LW, clamp01((t - 31.7) / 0.9))
        col = col * (1 - gm) + gold * gm
    a = clamp01(u / 0.15)
    f = put_layer(f, LOGO, col, LX0, LY0, a, shadow=0)
    # línea dorada y datos
    if t > 32.15:
        lw = int(280 * ease_out((t - 32.15) / 0.5))
        f[1205:1208, W // 2 - lw // 2:W // 2 + lw // 2] = np.array([0.86, 0.69, 0.38], np.float32)
    f = kinetic(f, t, 32.3, 99, "ENVÍOS A DOMICILIO", 1270, 50, SERIF, 0.34)
    f = kinetic(f, t, 32.6, 99, "@estilovinos", 1365, 80, SERIF, 0.04, sweep=False, color=np.array([0.97, 0.95, 0.92], np.float32))
    f = kinetic(f, t, 32.9, 99, "INDEPENDENCIA 1001", 1455, 44, SERIF, 0.32, sweep=False, color=np.array([0.85, 0.80, 0.74], np.float32))
    if t >= 30.5:  # destello dorado breve en el golpe final
        f = f + np.array([0.9, 0.7, 0.4], np.float32) * 0.28 * math.exp(-(t - 30.5) / 0.05)
    f = f * (1 - ease_in((t - 35.5) / 0.5, 1.5))
    return f, 0.4


# ------------------------------------------------------------------ línea de tiempo
TIMELINE = [
    (0.0, 0.95, hook), (0.95, 2.5, hook_footage), (2.5, 4.1, sec_1370), (4.1, 4.46, whip_h),
    (4.46, 6.47, sec_1364), (6.47, 8.05, sec_1368a), (8.05, 8.55, streak), (8.55, 10.5, sec_1353),
    (10.5, 12.05, sec_1355), (12.05, 12.65, wine_wipe), (12.65, 15.95, sec_1374), (15.95, 16.55, portal),
    (16.55, 17.45, sec_1366), (17.45, 18.25, sec_1360), (18.25, 18.6, whip_v), (18.6, 19.75, sec_1357),
    (19.75, 20.6, slices), (20.6, 21.5, sec_1368b), (21.5, 22.25, sec_1376), (22.25, 22.75, burn),
    (22.75, 24.2, sec_1375h), (24.2, 24.8, rack_focus), (24.8, 29.85, sec_1380), (29.85, 30.45, wine_rise),
    (30.45, 36.01, logo_scene),
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
