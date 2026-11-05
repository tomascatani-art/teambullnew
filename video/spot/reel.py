"""Reel ESTILO VINOS — versión con la estructura, ritmo y transiciones del Reel de referencia.

Referencia (11 s): gancho con texto animado (sans chica + serif cursiva grande con degradé, lista con checks 3D),
glitch de bloques de píxeles hacia una toma cenital girada con una palabra grande en modo "diferencia",
y después tomas muy cortas con lente gran angular, cámara siempre en movimiento, ángulos holandeses,
cortes secos alternados con barridos con mucho desenfoque de movimiento, y color teal & orange.

Mapa de tiempos (s):
  0.00-2.90  gancho sobre la tienda: "una vinoteca que / lo tiene" + todo: vinos ✓ destilados ✓ regalos ✓
             "no podés evitar / preguntarte." "¿cuál es el"
  2.90       GLITCH de bloques -> toma cenital girada (cajas) "secreto?"
  3.60       barrido vertical       4.70 corte     5.60 corte (lámparas)
  6.40       barrido hacia arriba   7.00 corte     7.50 corte a ángulo holandés
  7.80       barrido diagonal       8.40 corte     10.20 barrido horizontal (la clienta)
 12.00-15.0  cierre: fondo desenfocado, logo, "Te esperamos." + datos

Uso:  python3 reel.py --chunks DIR | --preview 0.5,2.9 DIR | out.mp4
"""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import common

common.GRADE = ("eq=contrast=1.16:saturation=1.25:gamma=0.98,"
                "colorbalance=rs=-0.06:gs=0.0:bs=0.10:rm=0.02:bm=-0.02:rh=0.07:gh=0.02:bh=-0.08")
from common import FPS, H, W, Shot, clamp01, ease_in, ease_io, ease_out, logo_mask, put_layer, text_mask  # noqa: E402

SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
SANS_B = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
SERIF_BI = "/usr/share/fonts/truetype/freefont/FreeSerifBoldItalic.ttf"
SERIF_I = "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf"
DUR = 15.0
WHITE = np.array([1.0, 1.0, 1.0], np.float32)

# ------------------------------------------------------------------ tomas y movimientos de cámara
# clave, toma, inicio, fin, zoom inicial, zoom final, giro inicial, giro final (grados)
SEGS = [
    ("hook", Shot("IMG_1375", 0.4, 3.2, res=1440), 0.0, 2.9, 1.00, 1.12, 0, 0),
    ("A", Shot("IMG_1374", 0.3, 1.0, res=2160), 2.9, 3.6, 1.42, 1.55, 12, 17),
    ("B", Shot("IMG_1353", 0.5, 1.4), 3.6, 4.7, 1.12, 1.26, -3, 0),
    ("C", Shot("IMG_1360", 0.4, 1.1), 4.7, 5.6, 1.04, 1.15, 0, 1.5),
    ("D", Shot("IMG_1366", 0.3, 1.0), 5.6, 6.4, 1.04, 1.18, 0, -1),
    ("E", Shot("IMG_1370", 1.0, 0.8), 6.4, 7.0, 1.10, 1.20, 1, 0),
    ("F", Shot("IMG_1368", 0.8, 0.7), 7.0, 7.5, 1.05, 1.15, 0, 0),
    ("G", Shot("IMG_1367", 1.0, 0.5), 7.5, 7.8, 1.46, 1.52, -14, -17),
    ("H", Shot("IMG_1357", 1.0, 0.8), 7.8, 8.4, 1.16, 1.05, 4, 0),
    ("I", Shot("IMG_1376", 0.4, 2.0), 8.4, 10.2, 1.00, 1.15, 0, 0),
    ("J", Shot("IMG_1380", 1.5, 4.9), 10.2, DUR, 1.00, 1.12, 0, 0),
]
SEG = {s[0]: s for s in SEGS}

# lente gran angular: abombado (las esquinas quedan en su lugar, el centro se agranda)
YY, XX = np.mgrid[0:H, 0:W].astype(np.float32)
_xn, _yn = (XX - W / 2) / (H / 2), (YY - H / 2) / (H / 2)
_k = 0.10
_f = (1 + _k * (_xn ** 2 + _yn ** 2)) / (1 + _k * ((W / H) ** 2 + 1))
MAPX = np.clip(W / 2 + (XX - W / 2) * _f, 0, W - 1).astype(np.int32)
MAPY = np.clip(H / 2 + (YY - H / 2) * _f, 0, H - 1).astype(np.int32)
RC = np.hypot(XX - W / 2, YY - H / 2)
VIGNETTE = (1 - 0.28 * np.clip(RC / np.hypot(W / 2, H / 2), 0, 1) ** 2.4)[..., None]
_rng = np.random.default_rng(3)
GRAIN = [_rng.normal(0, 0.014, (H // 2, W // 2)).astype(np.float32) for _ in range(4)]


def shot_frame(key, t):
    """Cuadro de una toma en el tiempo de salida t, con su movimiento de cámara y la lente."""
    _, shot, t0, t1, z0, z1, a0, a1 = SEG[key]
    u = clamp01((t - t0) / (t1 - t0))
    z = z0 + (z1 - z0) * ease_io(u) if key != "J" else z0 + (z1 - z0) * u
    ang = a0 + (a1 - a0) * u
    raw = shot.raw(max(0.0, t - t0))
    sh, sw = raw.shape[:2]
    s = z * W / sw
    a = math.radians(ang); ca, sa = math.cos(a), math.sin(a)
    m00, m01, m10, m11 = ca / s, sa / s, -sa / s, ca / s
    c0 = sw / 2 - (m00 * W / 2 + m01 * H / 2); c1 = sh / 2 - (m10 * W / 2 + m11 * H / 2)
    img = Image.fromarray(raw).transform((W, H), Image.AFFINE, (m00, m01, c0, m10, m11, c1), resample=Image.BILINEAR)
    arr = np.asarray(img, np.float32) / 255
    return arr[MAPY, MAPX]


def release(t):
    for key, shot, t0, t1, *_ in SEGS:
        if t > t1 + 0.2 and shot.frames is not None:
            shot.free()


# ------------------------------------------------------------------ transiciones de la referencia
def shift(img, dx, dy, pad):
    """Desplaza con bordes extendidos (sin que aparezca el lado opuesto)."""
    ph, pw = pad.shape[:2]
    m = (ph - H) // 2
    return pad[m - dy:m - dy + H, m - dx:m - dx + W]


def whip(t, t0, dur, ka, kb, vec):
    """Barrido con desenfoque de movimiento fuerte; corte a mitad del barrido."""
    u = clamp01((t - t0) / dur)
    vx, vy = vec
    nrm = math.hypot(vx, vy); vx, vy = vx / nrm, vy / nrm
    if u < 0.5:
        img = shot_frame(ka, t); slide = ease_in(u / 0.5, 2) * 260
    else:
        img = shot_frame(kb, t); slide = -(1 - ease_out((u - 0.5) / 0.5, 2)) * 260
    amount = 420 * math.sin(math.pi * u) ** 1.3
    M = 760
    pad = np.pad(img, ((M, M), (M, M), (0, 0)), mode="edge")
    acc = np.zeros((H, W, 3), np.float32); n = 12
    for i in range(n):
        d = slide + (i / (n - 1) - 0.5) * amount
        acc += shift(img, int(vx * d), int(vy * d), pad)
    return acc / n


def glitch(t, t0=2.72, t1=3.02):
    """Bloques de píxeles que se desplazan y se estiran (datamosh) mezclando las dos tomas."""
    u = clamp01((t - t0) / (t1 - t0))
    I = math.sin(math.pi * u)
    fa, fb = draw_hook_text(shot_frame("hook", t), t), shot_frame("A", max(t, 2.9))
    if u > 0.55:
        fb = draw_secret(fb, max(t, 2.92))
    pb = ease_io((u - 0.25) / 0.5)
    rng = np.random.default_rng(int(t * 1000))
    out = np.empty_like(fa)
    y = 0
    while y < H:
        h = int(rng.integers(14, 200))
        src = fb if rng.random() < pb else fa
        band = src[y:y + h]
        if rng.random() < 0.4 * I:  # estirar una fila (smear)
            row = band[int(rng.integers(0, max(1, band.shape[0])))][None]
            band = np.repeat(row, band.shape[0], axis=0)
        dx = int(rng.normal(0, 150 * I))
        band = np.roll(band, dx, axis=1)
        if rng.random() < 0.25 * I:
            band = band.copy(); band[..., 0] = np.roll(band[..., 0], int(18 * I), axis=1)
        out[y:y + h] = band
        y += h
    # bloques verticales sueltos
    for _ in range(int(10 * I)):
        bx, bw = int(rng.integers(0, W - 60)), int(rng.integers(40, 260))
        by, bh = int(rng.integers(0, H - 100)), int(rng.integers(80, 600))
        src = fb if rng.random() < pb else fa
        out[by:by + bh, bx:bx + bw] = src[by:by + 1, bx:bx + bw] if rng.random() < 0.5 else src[by:by + bh, bx:bx + bw][::-1]
    return out


# ------------------------------------------------------------------ texto animado
def back_out(u, s=1.9):
    u = clamp01(u) - 1
    return 1 + u * u * ((s + 1) * u + s)


def wine_grad(h, w):
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    top = np.array([0.72, 0.16, 0.40], np.float32); bot = np.array([0.32, 0.03, 0.14], np.float32)
    return np.broadcast_to(top * (1 - y) + bot * y, (h, w, 3)).copy()


def word(f, t, t0, t1, text, path, size, cx, cy, color="white", track=0.0, shadow=0.35, out=0.08):
    """Palabra que aparece con rebote (escala con overshoot) y se va rápido."""
    if t < t0 or t >= t1:
        return f
    u = (t - t0) / 0.18
    sc = 0.65 + 0.35 * back_out(u)
    alpha = clamp01((t - t0) / 0.07) * clamp01((t1 - t) / out)
    m = text_mask(text, size, path, track)
    if abs(sc - 1) > 0.004:
        im = Image.fromarray((m * 255).astype(np.uint8))
        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
        m = np.asarray(im, np.float32) / 255
    mh, mw = m.shape
    x0, y0 = cx - mw / 2, cy - mh / 2
    if color == "diff":  # modo diferencia: invierte lo que hay debajo
        xi, yi = int(x0), int(y0)
        xa, ya, xb, yb = max(0, xi), max(0, yi), min(W, xi + mw), min(H, yi + mh)
        mm = m[ya - yi:yb - yi, xa - xi:xb - xi][..., None] * alpha
        reg = f[ya:yb, xa:xb]
        f[ya:yb, xa:xb] = reg * (1 - mm) + np.abs(1 - reg) * mm
        return f
    col = wine_grad(mh, mw) if color == "wine" else WHITE
    return put_layer(f, m, col, x0, y0, alpha, shadow=shadow)


def make_check(size=170):
    """Ícono 3D: cuadrado redondeado bordó brillante con un check blanco y resplandor."""
    s = size * 2
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pad = int(s * 0.18)
    body = Image.new("L", (s, s), 0)
    ImageDraw.Draw(body).rounded_rectangle([pad, pad, s - pad, s - pad], radius=int(s * 0.17), fill=255)
    y = np.linspace(0, 1, s, dtype=np.float32)[:, None]
    col = np.dstack([0.93 - 0.35 * y, 0.22 - 0.14 * y, 0.52 - 0.22 * y]) * np.ones((1, s, 1), np.float32)
    gloss = np.clip(1 - y / 0.42, 0, 1) * 0.35
    col = np.clip(col + gloss[..., None] if gloss.ndim == 2 else col, 0, 1)
    glow = np.asarray(body.filter(ImageFilter.GaussianBlur(s * 0.08)), np.float32) / 255
    a_body = np.asarray(body, np.float32) / 255
    chk = Image.new("L", (s, s), 0)
    ImageDraw.Draw(chk).line([(s * 0.36, s * 0.52), (s * 0.46, s * 0.62), (s * 0.66, s * 0.40)], fill=255,
                             width=int(s * 0.045), joint="curve")
    a_chk = np.asarray(chk.filter(ImageFilter.GaussianBlur(1)), np.float32) / 255
    rgb = col * a_body[..., None] + np.array([1.0, 0.35, 0.65], np.float32) * (glow * (1 - a_body))[..., None]
    rgb = rgb * (1 - a_chk[..., None]) + a_chk[..., None]
    alpha = np.clip(a_body + glow * 0.7, 0, 1)
    rgba = np.dstack([np.clip(rgb, 0, 1), alpha])
    return Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").resize((size, size), Image.LANCZOS)


CHECK = make_check()
ICONS = [(250, 905, -12, 0.35), (850, 930, 14, 0.55), (300, 1210, 9, 0.75), (790, 1270, -10, 0.95)]
TRAIL = [(330 + 520 * s + 120 * math.sin(s * 6), 1330 + 330 * s + 90 * math.cos(s * 5)) for s in np.linspace(0, 1, 60)]


def draw_icons(f, t):
    if t > 2.0:
        return f
    fade = clamp01((2.0 - t) / 0.1)
    # estela de luz (como el trazo rosado de la referencia)
    prog = clamp01((t - 0.3) / 0.9)
    if prog > 0:
        layer = Image.new("L", (W // 2, H // 2), 0)
        pts = [(x / 2, y / 2) for x, y in TRAIL[:max(2, int(len(TRAIL) * prog))]]
        ImageDraw.Draw(layer).line(pts, fill=255, width=26, joint="curve")
        tr = np.asarray(layer.filter(ImageFilter.GaussianBlur(9)).resize((W, H), Image.BILINEAR), np.float32) / 255
        f = 1 - (1 - f) * (1 - tr[..., None] * np.array([1.0, 0.35, 0.62], np.float32) * 0.85 * fade)
    for x, y, ang, t0 in ICONS:
        if t < t0:
            continue
        sc = back_out((t - t0) / 0.22, 2.4)
        bob = 10 * math.sin((t - t0) * 5 + x)
        im = CHECK.rotate(ang + 4 * math.sin((t - t0) * 3), resample=Image.BICUBIC, expand=True)
        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))), Image.BILINEAR)
        a = np.asarray(im, np.float32) / 255
        f = put_layer(f, a[..., 3] * fade, a[..., :3], x - im.width / 2, y + bob - im.height / 2, 1.0, shadow=0)
    return f


def draw_hook_text(f, t):
    f = draw_icons(f, t)
    if t < 1.95:
        f = word(f, t, 0.05, 1.95, "lo tiene", SERIF_BI, 205, 540, 560, "wine", shadow=0.15)
        f = word(f, t, 0.0, 1.95, "una vinoteca que", SANS, 60, 470, 455, shadow=0.3)
        for t0, t1, w in ((0.35, 0.75, "todo:"), (0.75, 1.15, "vinos"), (1.15, 1.55, "destilados"), (1.55, 1.95, "regalos.")):
            f = word(f, t, t0, t1, w, SERIF_I, 118, 540, 1075)
    elif t < 2.58:
        f = word(f, t, 1.95, 2.58, "no podés evitar", SANS_B, 76, 540, 470)
        f = word(f, t, 2.12, 2.58, "preguntarte.", SERIF_I, 128, 560, 610)
    else:
        f = word(f, t, 2.58, 3.0, "¿cuál es el", SERIF_I, 112, 540, 1040)
    return f


def draw_secret(f, t):
    return word(f, t, 2.92, 3.56, "secreto?", SERIF_BI, 250, 540, 900, "diff", out=0.05)


def watermark(f, t):
    if not (2.9 <= t < 12.0):
        return f
    m = text_mask("@estilovinos", 26, SANS)
    f = put_layer(f, m, WHITE, 1010 - m.shape[1], 528, 0.9, shadow=0.4)
    ic = Image.new("L", (40, 40), 0)
    d = ImageDraw.Draw(ic)
    d.rounded_rectangle([4, 4, 35, 35], radius=9, outline=255, width=3)
    d.ellipse([12, 12, 27, 27], outline=255, width=3)
    d.ellipse([27, 8, 31, 12], fill=255)
    return put_layer(f, np.asarray(ic, np.float32) / 255, WHITE, 1010 - m.shape[1] / 2 - 20, 482, 0.9, shadow=0.4)


# ------------------------------------------------------------------ cierre
LOGO = logo_mask(660)


def end_card(t):
    u = t - 12.0
    f = shot_frame("J", t)
    r = 18 * ease_out(u / 0.45)
    small = Image.fromarray((np.clip(f, 0, 1) * 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BILINEAR)
    f = np.asarray(small.filter(ImageFilter.GaussianBlur(max(0.1, r / 4))).resize((W, H), Image.BICUBIC), np.float32) / 255
    f = f * (1 - 0.5 * ease_out(u / 0.45))
    if u > 0.15:
        sc = 0.7 + 0.3 * back_out((u - 0.15) / 0.3)
        im = Image.fromarray((LOGO * 255).astype(np.uint8))
        im = im.resize((int(im.width * sc), int(im.height * sc)), Image.BILINEAR)
        m = np.asarray(im, np.float32) / 255
        f = put_layer(f, m, WHITE, (W - m.shape[1]) / 2, 650 - m.shape[0] / 2, clamp01((u - 0.15) / 0.1), shadow=0.3)
    f = word(f, t, 12.45, 99, "Te esperamos.", SERIF_BI, 128, 540, 1160)
    f = word(f, t, 12.7, 99, "Envíos a domicilio", SANS_B, 50, 540, 1290)
    f = word(f, t, 12.85, 99, "Independencia 1001  ·  @estilovinos", SANS, 40, 540, 1362)
    return f


# ------------------------------------------------------------------ línea de tiempo
CUTS = {  # transición entrante -> tipo
    3.6: ("whip", (0, 1)), 6.4: ("whip", (0, -1)), 7.8: ("whip", (1, 1)), 10.2: ("whip", (1, 0)),
}


def frame_at(t):
    if 2.72 <= t < 3.02:
        f = glitch(t)
    else:
        f = None
        for tc, (kind, vec) in CUTS.items():
            if tc - 0.12 <= t < tc + 0.12:
                ka = [s[0] for s in SEGS if abs(s[3] - tc) < 1e-6][0]
                kb = [s[0] for s in SEGS if abs(s[2] - tc) < 1e-6][0]
                f = whip(t, tc - 0.12, 0.24, ka, kb, vec)
        if f is None:
            if t >= 12.0:
                f = end_card(t)
            else:
                key = [s[0] for s in SEGS if s[2] <= t < s[3]][0]
                f = shot_frame(key, t)
                if key == "hook":
                    f = draw_hook_text(f, t)
                if key == "A":
                    f = draw_secret(f, t)
    f = watermark(f, t)
    return f


def finish(f, i):
    f = f * VIGNETTE + np.repeat(np.repeat(GRAIN[i % 4], 2, 0), 2, 1)[..., None]
    return np.clip(f, 0, 1)


def render_range(out, first, last):
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "19", "-preset", "medium",
                            "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(first, last):
        t = i / FPS
        enc.stdin.write((finish(frame_at(t), i) * 255 + 0.5).astype(np.uint8).tobytes())
        release(t)
    enc.stdin.close(); enc.wait()


def main():
    n = int(DUR * FPS)
    if sys.argv[1] == "--preview":
        out = sys.argv[3]; os.makedirs(out, exist_ok=True)
        for t in [float(x) for x in sys.argv[2].split(",")]:
            Image.fromarray((finish(frame_at(t), int(t * FPS)) * 255).astype(np.uint8)).save(f"{out}/t{t:06.2f}.jpg", quality=88)
            print("preview", t, flush=True)
        return
    if sys.argv[1] == "--chunks":
        d = sys.argv[2]; os.makedirs(d, exist_ok=True); size = 90
        for c in range(0, n, size):
            path = f"{d}/chunk_{c // size:03d}.mp4"
            if not os.path.exists(path):
                render_range(path + ".part.mp4", c, min(n, c + size))
                os.replace(path + ".part.mp4", path)
                print(f"tramo {c // size} listo", flush=True)
        print("video listo (tramos)", flush=True)
        return
    render_range(sys.argv[1], 0, n)


if __name__ == "__main__":
    main()
