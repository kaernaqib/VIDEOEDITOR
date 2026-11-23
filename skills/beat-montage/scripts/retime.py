"""re-time a 120 BPM montage plan onto a real song: every duration x (song beat / 0.5 s), the plan's drop (16 s) lands on the song's drop.
usage: PY retime.py plan.json song.mp3 BPM DROP_S OUT_PLAN.json
writes the music excerpt next to OUT_PLAN (music.wav) and points the plan at it.
"""
import json, os, subprocess, sys
plan, song, bpm, drop, outp = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), sys.argv[5]
P = json.load(open(plan, encoding="utf-8"))
f = (60 / bpm) / 0.5
for sh in P["shots"]:
    sh["d"] = round(sh["d"] * f, 4)
for tx in P.get("texts", []):
    tx["t0"] = round(tx["t0"] * f, 3)
    tx["t1"] = round(tx["t1"] * f, 3)
total = sum(sh["d"] for sh in P["shots"])
start = drop - 16 * f
assert start >= 0, f"drop too early: start {start}"
d = os.path.dirname(os.path.abspath(outp))
mus = os.path.join(d, "music.wav")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{total:.3f}", "-i", song,
                "-af", f"afade=t=in:d=0.04,afade=t=out:st={total - 2.0:.3f}:d=2.0", "-ar", "48000", "-ac", "2", mus], check=True)
P["music"] = mus
P["music_vol"] = 1.0
P["song"] = {"file": os.path.basename(song), "bpm": bpm, "drop": drop, "start": round(start, 3)}
base, ext = os.path.splitext(P["out"])
P["out"] = os.path.join(d, os.path.basename(base) + "_ncs" + ext)
json.dump(P, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(os.path.basename(outp), "x%.3f" % f, "len %.1fs" % total, "song from %.2fs" % start)
