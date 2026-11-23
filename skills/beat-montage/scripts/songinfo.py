"""find beat phase and drops of a track with a known BPM -> json
usage: PY songinfo.py track.mp3 BPM
drop = point where low-end energy jumps from quiet (<45% of max over previous 3 s) to loud (>70% over next 2 s), snapped to a downbeat.
"""
import json, subprocess, sys
import numpy as np
path, bpm = sys.argv[1], float(sys.argv[2])
SR = 22050
raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True).stdout
x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
hop = 512
frames = len(x) // hop
win = np.hanning(2048)
spec = []
for i in range(0, len(x) - 2048, hop):
    spec.append(np.abs(np.fft.rfft(x[i:i + 2048] * win)))
S = np.array(spec)
freqs = np.fft.rfftfreq(2048, 1 / SR)
fps = SR / hop
low = S[:, freqs < 150].sum(1)
flux = np.maximum(0, np.diff(np.log1p(S), axis=0)).sum(1)
flux = np.concatenate([[0], flux])
beat = 60 / bpm
# beat phase: fold onset strength on the beat period
phases = np.linspace(0, beat, 64, endpoint=False)
score = []
t = np.arange(len(flux)) / fps
for ph in phases:
    idx = np.round((np.arange(ph, t[-1], beat)) * fps).astype(int)
    idx = idx[idx < len(flux)]
    score.append(flux[idx].mean())
phase = float(phases[int(np.argmax(score))])
# smoothed low energy per 0.1 s
k = int(fps * 0.5)
lowS = np.convolve(low, np.ones(k) / k, "same")
lowS /= lowS.max()
drops = []
for i in range(int(fps * 8), len(lowS) - int(fps * 3)):
    pre = lowS[i - int(fps * 3):i].mean()
    post = lowS[i:i + int(fps * 2)].mean()
    if pre < 0.45 and post > 0.70 and (not drops or t[i] - drops[-1] > 20):
        # snap to nearest bar (4 beats) on the phase grid
        tb = phase + round((t[i] - phase) / beat) * beat
        drops.append(round(float(tb), 3))
print(json.dumps({"file": path, "bpm": bpm, "beat": beat, "phase": round(phase, 3), "dur": round(len(x) / SR, 2), "drops": drops}))
