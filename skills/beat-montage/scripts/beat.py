"""synthesised royalty-free 120 BPM travel beat (60 s) -> beat.wav
sections (s): 0-8 intro (pad + filtered hats), 8-16 build (kick + riser + snare roll),
16-32 drop, 32-40 break (pad + pluck), 40-56 drop 2, 56-60 outro.
usage: PY beat.py out.wav [variant]   variant 0..9 changes key, chord progression and texture
"""
import numpy as np, wave, sys
SR, BPM, DUR = 48000, 120, 60.0
B = 60 / BPM
N = int(SR * DUR)
t = np.arange(N) / SR
out = np.zeros((N, 2), np.float32)
VAR = int(sys.argv[2]) if len(sys.argv) > 2 else 0
rng = np.random.default_rng(1 + VAR)
KEY = [0, 2, -3, 5, -1, 3, -2, 4, 1, -4][VAR % 10]            # transpose in semitones


def add(sig, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= N:
        return
    sig = sig[:N - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    out[i:i + len(sig), 0] += sig * gain * l * 1.41
    out[i:i + len(sig), 1] += sig * gain * r * 1.41


def env(n, a, d):
    e = np.ones(n, np.float32)
    na = max(1, int(a * SR))
    e[:na] = np.linspace(0, 1, na)
    e[na:] = np.exp(-np.arange(n - na) / (d * SR))
    return e


def kick():
    n = int(0.45 * SR); tt = np.arange(n) / SR
    f = 45 + 110 * np.exp(-tt * 30)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.16)).astype(np.float32)


def clap():
    n = int(0.25 * SR)
    x = rng.normal(0, 1, n).astype(np.float32)
    x = np.convolve(x, np.ones(6) / 6, "same") - np.convolve(x, np.ones(40) / 40, "same")
    return x * env(n, 0.001, 0.07) * 0.9


def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR)
    x = rng.normal(0, 1, n).astype(np.float32)
    x = x - np.convolve(x, np.ones(8) / 8, "same")
    return x * env(n, 0.0005, 0.06 if open_ else 0.012) * 0.35


def note(f):
    return 440 * 2 ** ((f - 69) / 12)


def saw(freq, n, voices=5, det=0.12):
    tt = np.arange(n) / SR
    s = np.zeros(n, np.float32)
    for v in range(voices):
        fr = freq * 2 ** ((v - voices // 2) * det / 12)
        s += (2 * ((tt * fr + rng.random()) % 1) - 1)
    return s / voices


def lowpass(x, k):
    return np.convolve(x, np.ones(k) / k, "same")


# chord progressions (one bar = 4 beats = 2 s), picked by variant, transposed by KEY
PROGS = [
    ([[60, 64, 67], [55, 59, 62, 67], [57, 60, 64], [53, 57, 60, 65]], [36, 31, 33, 29]),   # I V vi IV
    ([[57, 60, 64], [53, 57, 60, 65], [60, 64, 67], [55, 59, 62, 67]], [33, 29, 36, 31]),   # vi IV I V
    ([[60, 64, 67], [57, 60, 64], [53, 57, 60, 65], [55, 59, 62, 67]], [36, 33, 29, 31]),   # I vi IV V
    ([[53, 57, 60, 65], [55, 59, 62, 67], [57, 60, 64], [57, 60, 64]], [29, 31, 33, 33]),   # IV V vi vi
]
CH, ROOT = PROGS[VAR % len(PROGS)]
CH = [[m + KEY for m in c] for c in CH]
ROOT = [r + KEY for r in ROOT]


def section(s, e, a, b):
    return a <= s < b


bars = int(DUR / (4 * B))
side = np.ones(N, np.float32)                       # sidechain pump from kicks
for bar in range(bars):
    t0 = bar * 4 * B
    ci = bar % 4
    intro, build, drop1, brk, drop2, outro = (t0 < 8, 8 <= t0 < 16, 16 <= t0 < 32, 32 <= t0 < 40, 40 <= t0 < 56, t0 >= 56)
    n = int(4 * B * SR)
    # pad
    pad = sum(saw(note(m), n, 5, 0.15) for m in CH[ci]) / len(CH[ci])
    pad = lowpass(pad, 18 if (intro or brk or outro) else 8) * env(n, 0.25, 3.0)
    add(pad, t0, 0.38 if (intro or brk or outro) else 0.16)
    # bass (8ths) in build/drops
    if build or drop1 or drop2:
        for k in range(8):
            m = int(0.22 * SR)
            bs = lowpass(saw(note(ROOT[ci]), m, 2, 0.05), 6) * env(m, 0.003, 0.12)
            add(bs, t0 + k * B / 2, 0.55)
    # pluck arpeggio in drops and break
    if drop1 or drop2 or brk:
        arp = CH[ci] + [CH[ci][0] + 12]
        for k in range(8):
            m = int(0.3 * SR)
            pl = lowpass(saw(note(arp[k % len(arp)] + 12), m, 3, 0.08), 3) * env(m, 0.002, 0.09)
            add(pl, t0 + k * B / 2, 0.16, pan=0.35 if k % 2 else -0.35)
    for beat in range(4):
        tb = t0 + beat * B
        if build or drop1 or drop2 or (outro and beat == 0):
            add(kick(), tb, 0.95)
            i = int(tb * SR); m = int(0.28 * SR)
            side[i:i + m] = np.minimum(side[i:i + m], 0.45 + 0.55 * (np.arange(min(m, N - i)) / m))
        if (drop1 or drop2) and beat in (1, 3):
            add(clap(), tb, 0.6)
        if not outro:
            add(hat(), tb + B / 2, 0.5 if (drop1 or drop2) else 0.3, pan=0.2)
            if drop1 or drop2:
                add(hat(), tb, 0.25, pan=-0.2)
                add(hat(True), tb + B / 2 + B / 4 * 0, 0.0)
# snare roll + riser into each drop (last 2 s before 16 and 40)
for d in (16.0, 40.0):
    for k in range(16):
        add(clap(), d - 2 + k * 0.125, 0.08 + 0.22 * k / 15)
    n = int(2 * SR)
    nz = rng.normal(0, 1, n).astype(np.float32)
    nz = nz - lowpass(nz, 30)
    add(nz * np.linspace(0, 0.06, n) ** 1.5 / 0.06 ** 0.5, d - 2)
# impact on drops
for d in (16.0, 40.0):
    n = int(1.2 * SR); tt = np.arange(n) / SR
    boom = np.sin(2 * np.pi * (60 * np.exp(-tt * 3)) * tt) * env(n, 0.001, 0.4)
    add(boom.astype(np.float32), d, 0.7)
out[:, 0] *= side; out[:, 1] *= side
# fade out last 3 s, normalise to -1 dBFS peak
fade = np.ones(N, np.float32); fade[-3 * SR:] = np.linspace(1, 0, 3 * SR)
out *= fade[:, None]
out /= np.max(np.abs(out)) / 0.89
w = wave.open(sys.argv[1] if len(sys.argv) > 1 else "beat.wav", "wb")
w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((out * 32767).astype(np.int16).tobytes()); w.close()
print("beat ok")
