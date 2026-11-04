"""Banda sonora del spot ESTILO VINOS: música original (120 BPM, re menor) + diseño de sonido sincronizado.

Todo se sintetiza desde cero (sin samples). Salidas: mix.wav (música + efectos) y sfx.wav (solo efectos,
para usar con un tema de la biblioteca de Instagram).
Uso: python3 audio.py <carpeta-salida>
"""
import math
import os
import sys
import wave

import numpy as np

from common import DURATION, T

SR = 48000
N = int((DURATION + 0.3) * SR)
rng = np.random.default_rng(42)


# ------------------------------------------------------------------ utilidades
def tt(dur):
    return np.arange(int(dur * SR)) / SR


def lowpass(x, fc, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X / np.sqrt(1 + (f / fc) ** (2 * order)), len(x))


def highpass(x, fc, order=2):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR) + 1e-6
    return np.fft.irfft(X / np.sqrt(1 + (fc / f) ** (2 * order)), len(x))


def bandpass(x, lo, hi):
    return highpass(lowpass(x, hi, 3), lo, 3)


def sweep(x, centers, width=0.6):
    """Filtro pasabanda que se mueve en el tiempo (centro en Hz por cuadro de 512 muestras)."""
    n, hop = 2048, 512
    win = np.hanning(n)
    out = np.zeros(len(x) + n); norm = np.zeros(len(x) + n)
    f = np.fft.rfftfreq(n, 1 / SR) + 1
    xp = np.pad(x, (0, n))
    for i, start in enumerate(range(0, len(x), hop)):
        c = centers(start / SR)
        band = np.exp(-(np.log2(f / c) / width) ** 2)
        seg = np.fft.irfft(np.fft.rfft(xp[start:start + n] * win) * band, n)
        out[start:start + n] += seg * win; norm[start:start + n] += win ** 2
    return (out / np.maximum(norm, 1e-3))[:len(x)]


def saw(freq, t, phase=0.0):
    return 2 * ((freq * t + phase) % 1.0) - 1


def adsr(n, a=0.005, d=0.1, s=0.7, r=0.05):
    e = np.ones(n) * s
    na, nd, nr = int(a * SR), int(d * SR), int(r * SR)
    na = min(na, n); e[:na] = np.linspace(0, 1, na)
    nd = min(nd, n - na); e[na:na + nd] = np.linspace(1, s, nd)
    if nr < n:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


class Bus:
    def __init__(self):
        self.L = np.zeros(N); self.R = np.zeros(N)

    def add(self, at, sig, gain=1.0, pan=0.0):
        """pan -1 (izq) .. 1 (der). `sig` mono o (2, n)."""
        i = int(at * SR)
        if i >= N:
            return
        if sig.ndim == 1:
            l = sig * math.cos((pan + 1) * math.pi / 4); r = sig * math.sin((pan + 1) * math.pi / 4)
        else:
            l, r = sig
        n = min(len(l), N - max(i, 0))
        if i < 0:
            l, r = l[-i:], r[-i:]; i = 0; n = min(len(l), N)
        self.L[i:i + n] += l[:n] * gain; self.R[i:i + n] += r[:n] * gain

    def arr(self):
        return np.vstack([self.L, self.R])


def reverb(st, decay=2.0, wet=0.3, tone=5000):
    n = int(decay * SR)
    t = np.arange(n) / SR
    out = []
    for ch in range(2):
        ir = rng.normal(0, 1, n) * np.exp(-t * 6.9 / decay)
        ir = lowpass(ir, tone, 1); ir[:int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))
        ir /= np.sqrt(np.sum(ir ** 2))
        L = len(st[ch]) + n
        size = 1 << (L - 1).bit_length()
        y = np.fft.irfft(np.fft.rfft(st[ch], size) * np.fft.rfft(ir, size), size)[:len(st[ch])]
        out.append(st[ch] * (1 - wet) + y * wet * 1.6)
    return np.vstack(out)


# ------------------------------------------------------------------ instrumentos
def kick(g=1.0):
    t = tt(0.5)
    f = 48 + 120 * np.exp(-t / 0.028)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.26)
    s[:150] += rng.normal(0, 0.5, 150) * np.linspace(1, 0, 150)
    return np.tanh(s * 1.6) * g


def clap():
    t = tt(0.35)
    n = rng.normal(0, 1, len(t))
    env = np.zeros(len(t))
    for d in (0, 0.011, 0.022):
        env += np.where(t >= d, np.exp(-(t - d) / (0.012 if d < 0.02 else 0.13)), 0)
    return bandpass(n * env, 900, 6000) * 0.7 + np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.06) * 0.3


def hat(open_=False):
    t = tt(0.25 if open_ else 0.06)
    return highpass(rng.normal(0, 1, len(t)), 7000) * np.exp(-t / (0.09 if open_ else 0.018)) * 0.35


def bass(f, dur):
    t = tt(dur + 0.03)
    s = saw(f, t) * 0.6 + saw(f * 1.004, t, 0.3) * 0.4
    s = lowpass(s, 380, 2) + np.sin(2 * np.pi * f * t) * 0.6
    return s * adsr(len(t), 0.004, 0.08, 0.75, 0.03)


def pad(freqs, dur, cutoff=1400, a=0.35, r=0.6):
    t = tt(dur + r)
    out = np.zeros((2, len(t)))
    for f in freqs:
        for ch, dets in enumerate(((-0.13, 0.05, 0.19), (-0.2, -0.04, 0.12))):
            for dsem in dets:
                out[ch] += saw(f * 2 ** (dsem / 12), t, rng.random())
    env = adsr(len(t), a, 0.4, 0.8, r)
    return np.vstack([lowpass(out[0], cutoff, 2), lowpass(out[1], cutoff, 2)]) * env / (len(freqs) * 3)


def stab(freqs, dur=0.3):
    t = tt(dur)
    s = sum(saw(f, t) + saw(f * 1.006, t, 0.5) for f in freqs)
    return lowpass(s, 2600, 2) * np.exp(-t / 0.09) / len(freqs) * 0.6


def bell(f, dur=2.5):
    t = tt(dur)
    s = sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-t / d)
            for r, a, d in ((1, 1, 1.4), (2.0, 0.35, 0.8), (3.01, 0.2, 0.5), (4.2, 0.1, 0.3)))
    return s * np.minimum(1, t / 0.002) * 0.5


# ------------------------------------------------------------------ efectos de sonido
def boom(size=1.0):
    t = tt(2.5 * size)
    f = 30 + 85 * np.exp(-t / 0.12)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (0.9 * size))
    s += lowpass(rng.normal(0, 1, len(t)), 160, 2) * np.exp(-t / (0.35 * size)) * 1.2
    s += highpass(rng.normal(0, 1, len(t)), 2000) * np.exp(-t / 0.05) * 0.25
    return np.tanh(s * 1.8) * 0.9


def whoosh(dur=0.5, f0=250, f1=3500, pan0=-0.8, pan1=0.8):
    t = tt(dur)
    u = t / dur
    n = rng.normal(0, 1, len(t))
    s = sweep(n, lambda x: f0 * (f1 / f0) ** math.sin(math.pi * min(1, x / dur)), 0.7)
    s *= np.sin(np.pi * u) ** 1.6
    p = pan0 + (pan1 - pan0) * u
    return np.vstack([s * np.cos((p + 1) * np.pi / 4), s * np.sin((p + 1) * np.pi / 4)]) * 1.4


def riser(dur):
    t = tt(dur)
    u = t / dur
    s = sweep(rng.normal(0, 1, len(t)), lambda x: 300 * (6000 / 300) ** (x / dur), 0.8) * u ** 2
    tone = np.sin(2 * np.pi * np.cumsum(180 * (6 ** u)) / SR) * u ** 3 * 0.25
    trem = 0.7 + 0.3 * np.sin(2 * np.pi * np.cumsum(4 + 20 * u) / SR)
    return (s + tone) * trem


def reverse_cymbal(dur):
    t = tt(dur)
    return highpass(rng.normal(0, 1, len(t)), 3500) * (t / dur) ** 3 * 0.6


def cork_pop():
    t = tt(0.6)
    click = highpass(rng.normal(0, 1, len(t)), 2500) * np.exp(-t / 0.002)
    pop = np.sin(2 * np.pi * np.cumsum(330 + 900 * np.exp(-t / 0.01)) / SR) * np.exp(-t / 0.014)
    thump = np.sin(2 * np.pi * 135 * t) * np.exp(-t / 0.035)
    hiss = bandpass(rng.normal(0, 1, len(t)), 2500, 9000) * np.exp(-t / 0.12) * 0.12
    return (click * 0.6 + pop * 1.0 + thump * 0.6 + hiss)


def clink(f0=2350):
    t = tt(2.2)
    s = np.zeros(len(t))
    for r, a, d in ((1, 1, 1.4), (2.32, 0.6, 0.9), (4.25, 0.35, 0.5), (6.63, 0.2, 0.3), (8.9, 0.1, 0.2)):
        s += a * np.sin(2 * np.pi * f0 * r * t) * np.exp(-t / d)
        s += a * 0.3 * np.sin(2 * np.pi * (f0 * r + 1.7) * t) * np.exp(-t / d)
    s[:96] += rng.normal(0, 1, 96) * 0.4
    return s * 0.25


def shimmer(dur, n=40, lo=3000, hi=9000):
    out = np.zeros(int((dur + 0.6) * SR))
    for _ in range(n):
        at = rng.uniform(0, dur); f = rng.uniform(lo, hi); d = rng.uniform(0.08, 0.4)
        t = tt(d * 3)
        p = np.sin(2 * np.pi * f * t) * np.exp(-t / d) * rng.uniform(0.03, 0.09)
        i = int(at * SR); out[i:i + len(p)] += p[:len(out) - i]
    return out


def liquid(dur, bubbles=70):
    t = tt(dur)
    body = lowpass(rng.normal(0, 1, len(t)), 900, 2) * (0.5 + 0.5 * np.sin(np.pi * t / dur)) * 0.35
    out = body.copy()
    for _ in range(bubbles):
        at = rng.uniform(0, dur); f0 = rng.uniform(280, 950); d = rng.uniform(0.012, 0.03)
        bt = tt(d * 4)
        b = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 0.8 * bt / (d * 4))) / SR) * np.exp(-bt / d) * rng.uniform(0.15, 0.4)
        i = int(at * SR); out[i:i + len(b)] += b[:len(out) - i]
    return out


def wood_ticks(dur, n=22):
    out = np.zeros(int((dur + 0.2) * SR))
    for _ in range(n):
        at = rng.uniform(0, dur); f = rng.uniform(650, 1500)
        t = tt(0.08)
        p = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 2.7 * t)) * np.exp(-t / 0.012) * rng.uniform(0.2, 0.5)
        i = int(at * SR); out[i:i + len(p)] += p[:len(out) - i]
    return out


def impact(size=1.0):
    t = tt(0.8)
    metal = sum(np.sin(2 * np.pi * f * t) * np.exp(-t / 0.12) for f in (420, 1130, 1870, 2910)) * 0.12
    return boom(0.5 * size) * 0.8 + np.pad(clap() * 0.7 + 0, (0, int(2.5 * 0.5 * size * SR) - len(clap()))) \
        [:int(2.5 * 0.5 * size * SR)] + np.pad(metal, (0, max(0, int(2.5 * 0.5 * size * SR) - len(metal))))[:int(2.5 * 0.5 * size * SR)]


# ------------------------------------------------------------------ arreglo
D2, A2, D3, F3, A3, D4, E4, F4 = 73.42, 110.0, 146.83, 174.61, 220.0, 293.66, 329.63, 349.23
CHORDS = [  # Dm  Bb  F  C  (i - VI - III - VII)
    (73.42, (146.83, 174.61, 220.0, 293.66)),
    (58.27, (116.54, 146.83, 174.61, 233.08)),
    (87.31, (174.61, 220.0, 261.63, 349.23)),
    (65.41, (130.81, 164.81, 196.0, 261.63)),
]


def chord_at(t):
    return CHORDS[int((t - 0.5) // 2) % 4]


def build():
    music, drums, sfx = Bus(), Bus(), Bus()
    kicks = []

    def K(at, g=1.0):
        drums.add(at, kick(g), 0.9); kicks.append(at)

    beat = 0.5
    # GANCHO: silencio tenso, descorche, golpe
    sfx.add(T["pop"], cork_pop(), 1.0)
    sfx.add(0.0, whoosh(0.5, 400, 2500, 0, 0), 0.5)
    sfx.add(T["hook_boom"], boom(1.2), 1.0)
    sfx.add(0.36, whoosh(0.3, 150, 1200, 0, 0), 0.7)  # el corcho pasa pegado a la lente
    music.add(0.5, pad((D2, A2, D3), 2.0, 700, 0.6, 0.4), 0.9)
    for k in range(16):  # tic-tac que acelera la tensión
        drums.add(0.5 + k * 0.125, hat(), 0.15 + 0.35 * k / 16, pan=0.3 * (-1) ** k)
    sfx.add(1.3, riser(1.2), 0.35)
    sfx.add(2.5, impact(0.5), 0.3)  # zoom punch

    # DESARROLLO 2.5 - 16.5
    t = 2.5
    while t < 16.49:
        half = 13.5 <= t < 16.0  # cámara lenta: el ritmo se abre a medio tiempo
        bar_pos = round(((t - 0.5) % 2) / beat)
        if not half or bar_pos in (0, 2):
            K(t)
        if not half:
            drums.add(t + 0.25, hat(), 0.5, pan=0.25)
        if t >= 4.5 and bar_pos in (1, 3):
            drums.add(t, clap(), 0.55 if not half else 0.3)
        root, notes = chord_at(t)
        if bar_pos == 0:
            music.add(t, pad(notes, 2.0, 1500 if t < 13.5 else 900), 0.85)
        if not half:
            music.add(t, bass(root, 0.22), 0.5); music.add(t + 0.25, bass(root * (2 if bar_pos % 2 else 1), 0.22), 0.45)
        else:
            music.add(t, bass(root, 0.45), 0.45)
        t += beat
    sfx.add(T["whip1"] - 0.2, whoosh(0.42, 300, 4000, -0.9, 0.9), 0.9)
    sfx.add(6.1, riser(0.37), 0.35); sfx.add(T["zoom_through"], boom(0.5), 0.6)
    sfx.add(8.05, whoosh(0.5, 400, 2500, -0.5, 0.5), 0.35); sfx.add(8.1, shimmer(0.5, 16), 0.6)  # luz que se filtra
    sfx.add(T["match"], impact(1.0), 0.75)
    sfx.add(12.05, whoosh(0.6, 250, 4500, -0.8, 0.8), 0.85)  # giro de cámara
    sfx.add(T["glint"] - 0.05, clink(), 0.55); sfx.add(T["glint"], shimmer(0.5, 18, 5000, 11000), 0.8)
    sfx.add(15.45, reverse_cymbal(0.55), 0.6)
    sfx.add(15.95, whoosh(0.6, 200, 1500, 0, 0), 0.3)  # cambio de foco

    # MOMENTO WOW 16.5 - 22.25: todo más denso
    t = 16.5
    while t < 22.24:
        bar_pos = round(((t - 0.5) % 2) / beat)
        K(t)
        for s16 in range(4):
            drums.add(t + s16 * 0.125, hat(s16 == 2), 0.35 if s16 % 2 else 0.2, pan=0.3 * (-1) ** s16)
        if bar_pos in (1, 3):
            drums.add(t, clap(), 0.65)
        root, notes = chord_at(t)
        if bar_pos == 0:
            music.add(t, pad(notes, 2.0, 2200), 0.8)
        for s16 in range(4):
            music.add(t + s16 * 0.125, bass(root * (2 if s16 == 2 else 1), 0.11), 0.45)
        if bar_pos in (0, 2):
            music.add(t, stab([n * 2 for n in notes[:3]]), 0.55)
        t += beat
    sfx.add(17.2, riser(0.25), 0.3); sfx.add(T["bloom"], impact(0.8), 0.45)
    sfx.add(T["whip2"] - 0.2, whoosh(0.4, 250, 3500, 0, 0), 0.8)
    sfx.add(19.25, whoosh(0.55, 120, 900, -0.9, 0.9), 0.9)  # columna que pasa frente a la lente
    sfx.add(20.2, riser(0.25), 0.4)  # rampa de velocidad
    sfx.add(T["chroma"], impact(1.2), 0.7)  # zoom punch
    sfx.add(21.9, reverse_cymbal(0.4), 0.4)  # disolución al plano héroe

    # RESPIRO 22.5 - 24.5: campanas sobre el plano héroe
    music.add(22.25, pad((D3, F3, A3, D4), 2.4, 900, 0.3, 1.0), 0.9)
    music.add(22.25, pad((D2,), 2.4, 300, 0.2, 1.0), 0.8)
    for at, f in ((22.5, 440.0), (23.0, 349.23), (23.5, 587.33), (24.0, 523.25)):
        music.add(at, bell(f), 0.35, pan=0.3 if f > 450 else -0.3)
    sfx.add(T["focus"] - 0.3, whoosh(0.6, 200, 1200, 0, 0), 0.3)

    # RECONSTRUCCIÓN 24.5 - 30.45 con riser hacia el final
    t = 24.5
    while t < 30.42:
        bar_pos = round(((t - 0.5) % 2) / beat)
        if t < 28.5:
            if bar_pos in (0, 2):
                K(t, 0.9)
            drums.add(t + 0.25, hat(), 0.3)
        else:
            K(t)
            drums.add(t + 0.25, hat(), 0.45)
        root, notes = chord_at(t)
        if bar_pos == 0:
            music.add(t, pad(notes, 2.0, 1200 + 600 * (t > 26.5)), 0.85)
        if t >= 26.5:
            music.add(t, bass(root, 0.22), 0.45); music.add(t + 0.25, bass(root, 0.22), 0.4)
        t += beat
    step = 0.25
    t = 28.5
    while t < 30.4:  # redoble que acelera
        drums.add(t, clap(), 0.25 + 0.35 * (t - 28.5) / 1.9)
        step = 0.25 if t < 29.5 else (0.125 if t < 30.0 else 0.0625)
        t += step
    sfx.add(28.5, riser(1.92), 0.55)
    sfx.add(29.9, reverse_cymbal(0.55), 0.45)  # fundido a negro antes del golpe

    # CIERRE: golpe final, acorde amplio y brillo sobre el logo
    sfx.add(T["wine_rise"] + 0.05, boom(1.6), 1.1)
    music.add(30.5, pad((D2 / 2, D2, A2, D3, A3, D4, E4, F4), 4.8, 1800, 0.01, 1.5), 1.4)
    music.add(30.5, stab([D3, A3, D4, F4]), 0.8)
    drums.add(30.5, kick(1.0), 1.0)
    sfx.add(T["logo_sweep"], shimmer(1.2, 60, 3000, 10000), 1.2)
    music.add(T["logo_sweep"], bell(587.33, 3.5), 0.3); music.add(T["logo_sweep"] + 0.25, bell(880.0, 3.5), 0.22, pan=0.3)
    music.add(32.3, bell(440.0, 3.5), 0.18, pan=-0.3)

    # compresión "sidechain": la música respira con el bombo
    tl = np.arange(N) / SR
    duck = np.ones(N)
    for k in kicks:
        m = tl >= k
        duck[m] = np.minimum(duck[m], 1 - 0.38 * np.exp(-(tl[m] - k) / 0.13))
    # curva de intensidad: el desarrollo contenido, el WOW explota, el cierre es lo más fuerte
    pts = [(0, 0.8), (2.5, 0.62), (13.4, 0.7), (13.6, 0.55), (16.4, 0.6), (16.5, 1.0), (22.2, 1.0),
           (22.5, 0.55), (24.5, 0.55), (28.4, 0.75), (30.42, 1.0), (30.5, 1.15), (DURATION + 0.3, 1.0)]
    sect = np.interp(tl, [p[0] for p in pts], [p[1] for p in pts])
    m = music.arr() * duck * sect
    drums_sect = sect
    m = reverb(m, 2.2, 0.28, 4500)
    d = drums.arr() * drums_sect
    d = reverb(d, 0.9, 0.12, 6000)
    s = reverb(sfx.arr(), 1.8, 0.22, 7000)
    return m, d, s


def master(x, ceiling=0.89):
    x = np.tanh(x * 1.15) / np.tanh(1.15)
    fade = np.ones(x.shape[1]); n = int(0.35 * SR); fade[-n:] = np.linspace(1, 0, n)
    x = x * fade
    return x / np.max(np.abs(x)) * ceiling


def write_wav(path, x):
    pcm = (np.clip(x.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    m, d, s = build()
    write_wav(f"{out}/mix.wav", master(m * 0.55 + d * 0.6 + s * 0.85))
    write_wav(f"{out}/sfx.wav", master(s * 0.85 + d * 0.0))
    print("audio listo")
