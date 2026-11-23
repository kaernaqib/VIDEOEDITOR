"""turn a reel brief (clip pools per music section) into a montage plan that lands every cut on the beat.
usage: PY auto_montage.py reels.json REEL_ID OUTDIR   -> OUTDIR/plan.json
sections (120 BPM): intro 8x1s | build 16x0.5s | drop1 16s mixed | break 4x2s | drop2 16s mixed | outro 4s
"""
import json, os, sys
CFG = json.load(open(sys.argv[1], encoding="utf-8"))
RID, OUTD = sys.argv[2], sys.argv[3]
R = next(r for r in CFG["reels"] if r["id"] == RID)
clips = json.load(open(CFG["clips"], encoding="utf-8"))
idx = json.load(open(CFG["index"]))
dur = {i + 1: next((c["dur"] for c in clips if c["file"] == f), 0) for i, f in enumerate(idx)}
EX = set(CFG.get("exclude", []))
cursor = {int(k): v for k, v in CFG.get("minstart", {}).items()}


def pick(pool, d, i):
    """next unused segment of length d from the pool (round robin, skipping excluded/short clips)."""
    ok = [c for c in pool if c not in EX and dur.get(c, 0) >= d + 0.2]
    if not ok:
        raise SystemExit(f"pool empty for {d}s: {pool}")
    c = ok[i % len(ok)]
    s = cursor.get(c, 0.2)
    if s + d > dur[c] - 0.1:
        s = float(CFG.get("minstart", {}).get(str(c), 0.2))
    cursor[c] = s + d + 0.4
    return c, round(s, 2)


DROP = [1, 1, 1, 1, 1, 1, .5, .5, 1, 1, 1, 1, 1, 1, 1, 1, 1]    # 17 shots = 16 s
shots = []
def add(pool, ds, fxs, vol=0.0):
    for i, d in enumerate(ds):
        c, s = pick(pool, d, len(shots) + i)
        sh = {"c": c, "s": s, "d": d}
        fx = fxs(i)
        if fx:
            sh["fx"] = fx
        if vol or c in R.get("loud", []):
            sh["vol"] = vol or 0.7
        shots.append(sh)

add(R["intro"], [1.0] * 8, lambda i: ["zin"] if i % 2 == 0 else None)
add(R["build"], [0.5] * 16, lambda i: None)
add(R["drop1"], DROP, lambda i: ["flash", "punch"] if i == 0 else (["punch"] if i % 4 == 2 else (["zin"] if i % 4 == 1 else (["fast"] if i % 4 == 3 and R.get("fast", True) else None))))
add(R["break"], [2.0] * 4, lambda i: ["zin"] if i % 2 == 0 else ["zout"])
d2 = R.get("drop2_rhythm", "mixed")
ds2 = [0.5] * 8 + [1.0] * 12 if d2 == "stutter" else DROP
add(R["drop2"], ds2, lambda i: ["flash"] if i == 0 else (["punch"] if i % 3 == 1 else None), R.get("drop2_vol", 0.0))
c, s = pick(R["outro"], 4.0, 0)
shots.append({"c": c, "s": s, "d": 4.0, "fx": ["zout"]})
total = sum(x["d"] for x in shots)
assert abs(total - 60) < 1e-6, total
T = R["texts"]
plan = {"out": f"{OUTD}/berekeh_{RID}.mp4", "music": f"{OUTD}/beat.wav", "shots": shots,
        "texts": [{"t0": 0.1, "t1": 3.9, "small": T[0][0], "big": T[0][1], "y": 260},
                  {"t0": 16.0, "t1": 18.8, "small": T[1][0], "big": T[1][1], "y": 260},
                  {"t0": 40.0, "t1": 42.0, "small": T[2][0], "big": T[2][1], "y": 260},
                  {"t0": 56.2, "t1": 60.0, "small": T[3][0], "big": T[3][1], "y": 260}]}
os.makedirs(OUTD, exist_ok=True)
json.dump(plan, open(f"{OUTD}/plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(RID, "shots", len(shots), "clips", len({x['c'] for x in shots}))
