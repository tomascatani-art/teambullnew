"""Audio del Reel estilo referencia: beat filtrado en el gancho, "drop" en el glitch, pops en cada palabra/check,
barridos y golpes sincronizados con cada corte, y golpe final con el logo.
Uso: python3 audio_reel.py <carpeta>  -> reel_mix.wav, reel_sfx.wav
"""
import os
import sys

import numpy as np

import audio as A
from audio import (SR, Bus, bass, bell, boom, clap, hat, highpass, impact, kick, lowpass, master, pad, reverb, riser,
                   shimmer, stab, tt, whoosh, write_wav)

DUR = 15.0
A.N = int((DUR + 0.3) * SR)
rng = np.random.default_rng(7)


def ui_pop(f0=650, f1=1350, g=1.0):
    t = tt(0.12)
    s = np.sin(2 * np.pi * np.cumsum(f0 + (f1 - f0) * np.minimum(1, t / 0.03)) / SR) * np.exp(-t / 0.045)
    s[:60] += rng.normal(0, 0.3, 60)
    return s * 0.5 * g


def glitch_sfx(dur=0.3):
    n = int(dur * SR)
    out = np.zeros(n); i = 0
    while i < n:
        L = int(rng.integers(30, 900)); out[i:i + L] = rng.uniform(-1, 1); i += L
    t = tt(dur)
    for f in rng.uniform(300, 2400, 3):
        out += np.sign(np.sin(2 * np.pi * f * t)) * 0.25 * (rng.random(len(t)) > 0.5)
    out = np.round(out * 6) / 6  # bitcrush
    env = np.sin(np.pi * t / dur) ** 0.6
    return highpass(out, 200) * env * 0.45


def pluck(f, dur=0.2):
    t = tt(dur + 0.25)
    s = (2 * ((f * t) % 1) - 1) * 0.6 + (2 * ((f * 1.005 * t) % 1) - 1) * 0.4
    return lowpass(s, 2800, 2) * np.exp(-t / 0.13) * 0.5


CHORDS = [(73.42, (146.83, 174.61, 220.0, 293.66)), (58.27, (116.54, 146.83, 174.61, 233.08)),
          (87.31, (174.61, 220.0, 261.63, 349.23)), (65.41, (130.81, 164.81, 196.0, 261.63))]


def build():
    pre, music, drums, sfx = Bus(), Bus(), Bus(), Bus()
    drop = 2.9
    beat = 0.5
    # gancho: beat apagado (filtrado) que anticipa el drop
    t = drop - 5 * beat
    while t < drop - 1e-6:
        pre.add(t, kick(0.8), 0.8)
        pre.add(t, bass(73.42, 0.4), 0.5)
        pre.add(t + 0.25, hat(), 0.3)
        t += beat
    pre.add(0.0, pad((146.83, 174.61, 220.0), 2.9, 900, 0.2, 0.3)[0], 0.6)
    sfx.add(1.9, riser(1.0), 0.45)
    # pops de palabras y checks
    for at in (0.0, 0.05, 0.35, 0.75, 1.15, 1.55, 1.95, 2.12, 2.58):
        sfx.add(at, ui_pop(), 0.55)
    for at in (0.35, 0.55, 0.75, 0.95):
        sfx.add(at + 0.02, ui_pop(900, 1900, 0.8), 0.5, pan=0.4 if at in (0.55, 0.95) else -0.4)
    # DROP en el glitch
    sfx.add(2.72, glitch_sfx(0.3), 0.9)
    sfx.add(drop, boom(0.9), 0.9)
    t = drop
    while t < 12.0 - 1e-6:
        k = round((t - drop) / beat)
        bar = k // 4
        root, notes = CHORDS[bar % 4]
        drums.add(t, kick(), 0.95)
        for s in range(4):
            drums.add(t + s * 0.125, hat(s == 2), 0.3 if s % 2 else 0.18, pan=0.3 * (-1) ** s)
        if k % 2 == 1:
            drums.add(t, clap(), 0.6)
        if k % 4 == 0:
            music.add(t, pad(notes, 2.0, 2000), 0.75)
            music.add(t, stab([n * 2 for n in notes[:3]]), 0.5)
        music.add(t, bass(root, 0.2), 0.5); music.add(t + 0.25, bass(root * 2, 0.2), 0.4)
        arp = [notes[0] * 2, notes[1] * 2, notes[2] * 2, notes[3] * 2]
        for j in range(4):  # melodía arpegiada en semicorcheas
            music.add(t + j * 0.125, pluck(arp[(k * 4 + j) % 4 if j != 3 else (k + 1) % 4]), 0.32, pan=0.35 * (-1) ** j)
        t += beat
    # transiciones: barridos y golpes de corte
    for tc, (f0, f1, p0, p1) in {3.6: (300, 3500, 0, 0), 5.6: (300, 3800, -0.9, 0.9), 6.4: (300, 3500, 0, 0),
                                 7.8: (300, 4000, -0.7, 0.7), 8.4: (300, 4000, 0.7, -0.7),
                                 10.2: (250, 3800, -0.9, 0.9)}.items():
        sfx.add(tc - 0.18, whoosh(0.36, f0, f1, p0, p1), 0.85)
    sfx.add(6.88, glitch_sfx(0.24), 0.7)
    for tc in (4.7, 7.5):
        sfx.add(tc, impact(0.35), 0.28)
    # cierre
    sfx.add(11.0, riser(1.0), 0.5)
    sfx.add(12.0, boom(1.3), 1.0)
    music.add(12.0, pad((36.71, 73.42, 110.0, 146.83, 220.0, 293.66, 349.23), 3.0, 1600, 0.01, 1.2), 1.2)
    music.add(12.0, stab([146.83, 220.0, 293.66, 349.23]), 0.7)
    drums.add(12.0, kick(), 1.0)
    sfx.add(12.15, shimmer(1.0, 40, 3000, 10000), 1.0)
    for at in (12.45, 12.7, 12.85):
        sfx.add(at, ui_pop(700, 1400, 0.7), 0.4)
    music.add(12.45, bell(587.33, 2.5), 0.25)

    p = pre.arr()
    p = np.vstack([lowpass(p[0], 450, 2), lowpass(p[1], 450, 2)])
    tl = np.arange(A.N) / SR
    duck = np.ones(A.N)
    m = reverb(music.arr() + p, 1.6, 0.22, 5000)
    d = reverb(drums.arr(), 0.7, 0.1, 6000)
    s = reverb(sfx.arr(), 1.2, 0.18, 7000)
    return m * duck, d, s


if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    m, d, s = build()
    write_wav(f"{out}/reel_mix.wav", master(m * 0.85 + d * 0.8 + s * 0.7))
    write_wav(f"{out}/reel_sfx.wav", master(s * 0.85))
    print("audio reel listo")
