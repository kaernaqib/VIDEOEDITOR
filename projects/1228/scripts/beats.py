"""Find the beat grid of a music track, so cuts and big titles land on the beat.

usage: python3 beats.py MUSIC_FILE [--out beats.json] [--every 2]
Spectral-flux onsets -> tempo by autocorrelation (70-180 BPM) -> beat phase that best matches the onsets.
--every N also prints every Nth beat (cut points for a target shot length of N beats).
Writes {"bpm", "beats": [seconds...], "downbeats_guess": [...every 4th...], "strong": [the 16 strongest onsets]}.
"""
import json, subprocess, sys
import numpy as np

path = sys.argv[1]
arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
out, every = arg("--out", None), int(arg("--every", 0))
SR, HOP, NFFT = 22050, 512, 2048

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
assert len(x) > SR * 3, "need at least 3 s of audio"
n = 1 + (len(x) - NFFT) // HOP
win = np.hanning(NFFT).astype(np.float32)
frames = np.lib.stride_tricks.as_strided(x, (n, NFFT), (x.strides[0] * HOP, x.strides[0]))
mag = np.log1p(np.abs(np.fft.rfft(frames * win, axis=1)))
flux = np.maximum(0, np.diff(mag, axis=0)).sum(1)
flux = np.concatenate([[0], flux])
flux -= np.convolve(flux, np.ones(16) / 16, mode="same")          # local mean removal
flux = np.maximum(flux, 0)
fps = SR / HOP

ac = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
lags = np.arange(len(ac))
bpm_of = lambda lag: 60 * fps / lag
ok = (bpm_of(np.maximum(lags, 1)) >= 70) & (bpm_of(np.maximum(lags, 1)) <= 180) & (lags > 0)
lag = int(lags[ok][np.argmax(ac[ok])])
period = lag
best_phase = max(range(period), key=lambda p: flux[p::period].sum())
beat_frames = np.arange(best_phase, len(flux), period)
# refine each beat to the strongest onset within ±10% of a period
refined = []
for b in beat_frames:
    lo, hi = max(0, b - period // 10), min(len(flux), b + period // 10 + 1)
    refined.append(lo + int(np.argmax(flux[lo:hi])))
beats = [round(float(f) / fps, 3) for f in refined]
strong = sorted((np.argsort(flux)[-16:] / fps).round(3).tolist())
res = {"bpm": round(bpm_of(lag), 1), "beats": beats, "downbeats_guess": beats[::4], "strong": strong}
if out:
    json.dump(res, open(out, "w"), indent=1)
print(f"{res['bpm']} BPM, {len(beats)} beats, first {beats[:6]}")
if every:
    print(f"every {every} beats:", beats[::every][:40])
