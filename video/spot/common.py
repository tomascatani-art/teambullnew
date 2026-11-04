"""Piezas compartidas del spot de Estilo Vinos: tiempos, carga de tomas, texto, corcho, partículas."""
import glob
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
SRC_DIR = os.environ.get("EV_SRC", "/root/.claude/uploads/daaa446b-3640-58cf-b2d3-a41053907cff")
LOGO = os.environ.get("EV_LOGO", f"{SRC_DIR}/8a237bde-image.jpg")
SERIF = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
SERIF_IT = "/usr/share/fonts/truetype/freefont/FreeSerifItalic.ttf"
SERIF_B = "/usr/share/fonts/truetype/freefont/FreeSerifBold.ttf"

# Momentos clave (segundos) — compartidos por imagen y sonido. 120 BPM: 1 tiempo = 0.5 s
T = dict(
    pop=0.02, hook_boom=0.5, text_fly=2.5, whip1=4.28, zoom_through=6.47, streak=8.3,
    match=10.5, wine=12.35, glint=13.75, portal=16.0, bloom=17.45, whip2=18.43,
    corkrain=19.55, slices=20.45, chroma=21.5, burn=22.5, focus=24.5,
    wine_rise=30.45, logo_sweep=31.7, end=36.0,
)
DURATION = T["end"]

# Etalonaje: negros profundos, sombras bordó, luces doradas
GRADE = ("eq=contrast=1.12:brightness=-0.025:saturation=1.08:gamma=0.97,"
         "colorbalance=rs=0.06:gs=-0.01:bs=-0.03:rm=0.03:gm=-0.01:bm=-0.05:rh=0.03:gh=0.015:bh=-0.06")

GOLD_TOP = np.array([1.0, 0.94, 0.80], np.float32)
GOLD_MID = np.array([0.86, 0.69, 0.38], np.float32)
GOLD_BOT = np.array([0.60, 0.42, 0.17], np.float32)
WINE = np.array([0.36, 0.03, 0.10], np.float32)


def ease_out(u, p=3):
    u = min(1.0, max(0.0, u)); return 1 - (1 - u) ** p


def ease_in(u, p=3):
    u = min(1.0, max(0.0, u)); return u ** p


def ease_io(u):
    u = min(1.0, max(0.0, u)); return u * u * (3 - 2 * u)


def clamp01(u):
    return min(1.0, max(0.0, u))


# ------------------------------------------------------------------ tomas
class Shot:
    """Fragmento de un video original, cargado en memoria ya encuadrado 9:16 y etalonado."""

    def __init__(self, name, ss, dur, res=1080, ifps=None):
        self.name, self.ss, self.dur, self.res, self.ifps = name, ss, dur, res, ifps
        self.frames = None

    def load(self):
        if self.frames is not None:
            return
        path = glob.glob(f"{SRC_DIR}/*{self.name}.mov")[0]
        w = self.res; h = w * 16 // 9
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,crop={w}:{h},{GRADE},fps=30"
        self.fps = 30
        if self.ifps:
            vf += f",minterpolate=fps={self.ifps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
            self.fps = self.ifps
        cmd = ["ffmpeg", "-v", "error", "-ss", str(self.ss), "-t", str(self.dur), "-i", path,
               "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        raw = subprocess.run(cmd, check=True, stdout=subprocess.PIPE).stdout
        self.frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
        self.w, self.h = w, h

    def free(self):
        self.frames = None

    def raw(self, st, span=0.0):
        """Cuadro en el segundo `st` del fragmento; con `span` promedia cuadros (desenfoque de movimiento)."""
        self.load()
        n = len(self.frames)
        if span <= 1.0 / self.fps:
            return self.frames[int(np.clip(round(st * self.fps), 0, n - 1))]
        a = int(np.clip(round((st - span / 2) * self.fps), 0, n - 1))
        b = int(np.clip(round((st + span / 2) * self.fps), a + 1, n))
        return self.frames[a:b].mean(axis=0).astype(np.uint8)

    def view(self, st, zoom=1.0, cx=0.5, cy=0.5, span=0.0):
        """Encuadre 1080x1920 con zoom hacia (cx, cy). Devuelve float32 0..1."""
        fr = self.raw(st, span)
        zoom = max(1.0, zoom)
        if zoom <= 1.0001 and fr.shape[1] == W:
            return fr.astype(np.float32) / 255
        ww, hh = self.w / zoom, self.h / zoom
        x0 = max(0.0, min(cx * self.w - ww / 2, self.w - ww))
        y0 = max(0.0, min(cy * self.h - hh / 2, self.h - hh))
        img = Image.fromarray(fr).resize((W, H), Image.BILINEAR, box=(x0, y0, x0 + ww, y0 + hh))
        return np.asarray(img, np.float32) / 255


def zoom_blur(shot, st, z0, z1, cx, cy, n=6, span=0.0):
    """Promedia encuadres entre dos zooms: desenfoque radial de un empuje de cámara."""
    acc = np.zeros((H, W, 3), np.float32)
    for i in range(n):
        acc += shot.view(st, z0 + (z1 - z0) * i / max(1, n - 1), cx, cy, span)
    return acc / n


# ------------------------------------------------------------------ texto dorado
_font_cache = {}


def font(path, size):
    k = (path, size)
    if k not in _font_cache:
        _font_cache[k] = ImageFont.truetype(path, size)
    return _font_cache[k]


_text_cache = {}


def text_mask(text, size, path=SERIF, tracking=0.0):
    """Máscara (float 0..1) de un texto con espaciado entre letras."""
    k = (text, size, path, tracking)
    if k in _text_cache:
        return _text_cache[k]
    f = font(path, size)
    widths = [f.getlength(c) for c in text]
    total = sum(widths) + tracking * size * (len(text) - 1)
    asc, desc = f.getmetrics()
    img = Image.new("L", (int(total) + 8, asc + desc + 8), 0)
    d = ImageDraw.Draw(img)
    x = 4
    for c, wd in zip(text, widths):
        d.text((x, 4), c, font=f, fill=255)
        x += wd + tracking * size
    m = np.asarray(img, np.float32) / 255
    _text_cache[k] = m
    return m


def gold_fill(h, w, sweep=None):
    """Degradado dorado vertical; `sweep` (0..1) agrega un brillo diagonal que lo recorre."""
    y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    top = np.clip(1 - y * 2, 0, 1); bot = np.clip(y * 2 - 1, 0, 1); mid = 1 - top - bot
    col = top * GOLD_TOP + mid * GOLD_MID + bot * GOLD_BOT
    col = np.broadcast_to(col, (h, w, 3)).copy()
    if sweep is not None:
        xx = np.linspace(0, 1, w, dtype=np.float32)[None, :]
        yy = np.linspace(0, 1, h, dtype=np.float32)[:, None]
        band = np.exp(-(((xx + yy * 0.35) - (sweep * 1.8 - 0.4)) / 0.06) ** 2)
        col = col + band[..., None] * 0.9
    return np.clip(col, 0, 1.6)


def put_layer(frame, mask, color, x, y, alpha=1.0, shadow=0.55):
    """Compone una máscara coloreada en (x, y) (esquina sup. izq.), con sombra suave para legibilidad."""
    mh, mw = mask.shape
    x, y = int(x), int(y)
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + mw), min(H, y + mh)
    if x1 <= x0 or y1 <= y0 or alpha <= 0:
        return frame
    m = mask[y0 - y:y1 - y, x0 - x:x1 - x] * alpha
    c = color[y0 - y:y1 - y, x0 - x:x1 - x] if color.ndim == 3 else color
    if shadow > 0:
        sm = np.asarray(Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(10)), np.float32) / 255
        frame[y0:y1, x0:x1] *= (1 - shadow * sm)[..., None]
    frame[y0:y1, x0:x1] = frame[y0:y1, x0:x1] * (1 - m[..., None]) + c * m[..., None]
    return frame


def kinetic(frame, t, t0, t1, text, y, size, path=SERIF, tracking=0.12, sweep=True, color=None, rise=0.32, out=0.25):
    """Palabra que sube desde detrás de una línea invisible, brilla, y se va."""
    if t < t0 or t > t1:
        return frame
    m = text_mask(text, size, path, tracking)
    if m.shape[1] > W - 130:  # ajustar al ancho de pantalla
        size = int(size * (W - 130) / m.shape[1])
        m = text_mask(text, size, path, tracking)
    mh, mw = m.shape
    u = (t - t0) / rise
    off = (1 - ease_out(u, 4)) * mh * 0.95
    vis = np.zeros_like(m)  # recorte: solo se ve lo que ya "salió" de la línea
    shift = int(off)
    if shift < mh:
        vis[:mh - shift] = m[shift:] if shift > 0 else m
    alpha = clamp01((t1 - t) / out)
    col = color if color is not None else gold_fill(mh, mw, clamp01((t - t0 - 0.15) / 0.9) if sweep else None)
    scale_drift = 1 + 0.03 * clamp01((t - t0) / (t1 - t0))
    if abs(scale_drift - 1) > 1e-3:
        nw, nh = int(mw * scale_drift), int(mh * scale_drift)
        vis = np.asarray(Image.fromarray((vis * 255).astype(np.uint8)).resize((nw, nh), Image.BILINEAR), np.float32) / 255
        if col.ndim == 3:
            col = np.asarray(Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).resize((nw, nh), Image.BILINEAR), np.float32) / 255
        mw, mh = nw, nh
    return put_layer(frame, vis, col, (W - mw) / 2, y - mh / 2, alpha)


# ------------------------------------------------------------------ logo
def logo_mask(width):
    img = Image.open(LOGO).convert("L")
    img = img.resize((width, int(img.height * width / img.width)), Image.LANCZOS)
    a = np.asarray(img, np.float32) / 255
    return np.clip((a - 0.12) / 0.8, 0, 1)


# ------------------------------------------------------------------ corcho de marca (CGI)
def noise2(w, h, cells, rng):
    small = rng.random((max(2, int(h / cells)), max(2, int(w / cells)))).astype(np.float32)
    return np.asarray(Image.fromarray((small * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC), np.float32) / 255


def make_cork(seed=1, diam=128, length=330):
    """Corcho fotorrealista con la marca impresa. Escala todos los detalles con el tamaño."""
    k = diam / 128
    rng = np.random.default_rng(seed)
    w, h = diam, length
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx + 0.5) / w * 2 - 1
    v = (yy + 0.5) / h
    r = 0.16 * w
    qx = np.abs(xx - w / 2) - (w / 2 - r)
    qy = np.abs(yy - h / 2) - (h / 2 - r)
    sdf = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    alpha = np.clip(-sdf, 0, 1)
    base = np.array([0.80, 0.63, 0.44], np.float32)
    n = 0.55 * noise2(w, h, 6 * k, rng) + 0.45 * noise2(w, h, 22 * k, rng)
    col = base * (0.80 + 0.35 * n)[..., None]
    pores = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(pores)
    for _ in range(int(340 * (length / 330))):
        px, py = rng.uniform(0, w), rng.uniform(0, h)
        pw, ph = rng.uniform(0.6, 2.4) * k, rng.uniform(1.2, 6.0) * k
        d.ellipse([px - pw, py - ph, px + pw, py + ph], fill=int(rng.uniform(80, 220)))
    pores = np.asarray(pores.filter(ImageFilter.GaussianBlur(0.6 * k)), np.float32) / 255
    col *= (1 - 0.45 * pores)[..., None]
    txt = Image.new("L", (h, w), 0)
    td = ImageDraw.Draw(txt)
    f = ImageFont.truetype(SERIF, int(26 * k))
    label = "ESTILO  VINOS"
    tw = td.textlength(label, font=f)
    td.text(((h - tw) / 2 + 0.07 * h, w / 2 - 15 * k), label, font=f, fill=255)
    txt = np.asarray(txt.rotate(90, expand=True), np.float32) / 255
    kk = 0.62 * txt * (0.75 + 0.25 * n)
    col = col * (1 - kk[..., None]) + np.array([0.30, 0.16, 0.08], np.float32) * kk[..., None]
    edge = 0.80 + 0.05 * (noise2(w, h, 9 * k, rng) - 0.5) * 2
    stain = np.clip((v - edge) / 0.035, 0, 1)
    wine = np.array([0.34, 0.05, 0.12], np.float32) * (0.75 + 0.35 * n)[..., None]
    col = col * (1 - 0.92 * stain[..., None]) + wine * (0.92 * stain[..., None])
    nz = np.sqrt(np.clip(1 - u * u, 0, 1))
    lam = np.clip(-0.55 * u + 0.83 * nz, 0, 1)
    shade = (0.30 + 0.85 * lam) * (0.65 + 0.35 * np.clip(np.minimum(v, 1 - v) / 0.06, 0, 1) ** 0.5)
    col = np.clip(col * shade[..., None] + (lam ** 24 * 0.12)[..., None], 0, 1)
    rgba = np.dstack([col, alpha])
    return Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")


def affine_blit(sprite, cx, cy, sx, sy, ang_deg):
    """Dibuja `sprite` (PIL RGBA) centrado en (cx, cy) escalado (sx, sy) y rotado, directo a 1080x1920."""
    a = math.radians(ang_deg)
    ca, sa = math.cos(a), math.sin(a)
    sw, sh = sprite.size
    # salida -> sprite:  q = S^-1 R^-1 (p - c) + centro
    m00, m01 = ca / sx, sa / sx
    m10, m11 = -sa / sy, ca / sy
    c0 = sw / 2 - (m00 * cx + m01 * cy)
    c1 = sh / 2 - (m10 * cx + m11 * cy)
    img = sprite.transform((W, H), Image.AFFINE, (m00, m01, c0, m10, m11, c1), resample=Image.BILINEAR)
    arr = np.asarray(img, np.float32) / 255
    return arr[..., :3], arr[..., 3]


# ------------------------------------------------------------------ partículas doradas
class Dust:
    def __init__(self, n, seed, rise=40.0):
        r = np.random.default_rng(seed)
        self.p = np.c_[r.uniform(0, W, n), r.uniform(0, H, n)]
        self.v = np.c_[r.normal(0, 12, n), -r.uniform(0.3, 1.0, n) * rise]
        self.s = r.uniform(1.5, 7.0, n)
        self.ph = r.uniform(0, 6.28, n)
        self.b = r.uniform(0.3, 1.0, n)

    def render(self, t, strength=1.0):
        layer = np.zeros((H, W), np.float32)
        pos = self.p + self.v * t
        pos[:, 1] %= H; pos[:, 0] %= W
        for (x, y), s, ph, b in zip(pos, self.s, self.ph, self.b):
            rr = int(s * 3) + 1
            x0, y0 = int(x) - rr, int(y) - rr
            if x0 < 0 or y0 < 0 or x0 + 2 * rr + 1 > W or y0 + 2 * rr + 1 > H:
                continue
            g = np.arange(-rr, rr + 1, dtype=np.float32)
            k = np.exp(-(g[:, None] ** 2 + g[None, :] ** 2) / (2 * (s * 0.6) ** 2))
            tw = 0.55 + 0.45 * math.sin(t * 3 + ph)
            layer[y0:y0 + 2 * rr + 1, x0:x0 + 2 * rr + 1] += k * b * tw
        return np.clip(layer * strength, 0, 1.5)[..., None] * np.array([1.0, 0.80, 0.45], np.float32)


def star_glint(size=260):
    g = np.linspace(-1, 1, size, dtype=np.float32)
    x, y = np.meshgrid(g, g)
    r = np.hypot(x, y)
    rays = np.exp(-np.abs(x) * 40) * np.exp(-(y / 0.9) ** 2 * 3) + np.exp(-np.abs(y) * 40) * np.exp(-(x / 0.9) ** 2 * 3)
    diag = (np.exp(-np.abs(x - y) * 60) + np.exp(-np.abs(x + y) * 60)) * np.exp(-r * 4) * 0.4
    core = np.exp(-(r / 0.06) ** 2) + 0.35 * np.exp(-(r / 0.25) ** 2)
    return np.clip(rays + diag + core, 0, 2)
