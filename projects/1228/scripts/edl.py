"""Cut list (from capcut-talking-head-edit, unchanged logic). usage: python edl.py WORK_DIR"""
import json, sys
import numpy as np
import cct

work = sys.argv[1]
J = cct.load(f"{work}/job.json")
FPS = J.get("fps", 30)
W = cct.load(f"{work}/words.json")
db = np.load(f"{work}/db10ms.npy")
N = len(db)
SIL = -50.0
PACE = {"tight": (0.45, 0.12, 0.10), "natural": (0.60, 0.20, 0.15)}[J.get("pacing", "tight")]
ZOOM_PACE = (0.80, 0.22, 0.16)
T = lambda i, end=False: W[i]["e"] if end else W[i]["s"]


def silences(t0, t1, thr=SIL, min_len=0.03):
    a, b = max(0, int(t0 * 100)), min(N, int(t1 * 100))
    return [((a + x) / 100, (a + y) / 100) for x, y in cct.runs(db[a:b] < thr) if (y - x) / 100 >= min_len]


def gap_between(i, j):
    t0, t1 = T(i, True) - 0.25, T(j) + 0.25
    c = silences(t0, t1) or silences(t0, t1, thr=-45)
    if not c:
        m = (T(i, True) + T(j)) / 2
        return (m, m)
    return max(c, key=lambda r: r[1] - r[0])


def local_min(t, win=0.08):
    a, b = int((t - win) * 100), int((t + win) * 100)
    return (a + int(np.argmin(db[a:b]))) / 100


fs = {int(k): v for k, v in J.get("force_start", {}).items()}
fe = {int(k): v for k, v in J.get("force_end", {}).items()}
removed = []
for a, b, why in J.get("remove_words", []):
    if a in fs:
        s = local_min(fs[a])
    elif a == 0:
        s = T(0) - 0.3
    else:
        g = gap_between(a - 1, a)
        s = min(g[1], g[0] + 0.12)
    if b in fe:
        e = fe[b]
    elif b == len(W) - 1:
        e = T(b, True) + 0.3
    else:
        g = gap_between(b, b + 1)
        e = max(g[0], g[1] - 0.08)
    removed.append((s, e, why))
removed += [tuple(r) for r in J.get("remove_time", [])]
removed.sort()

speech = db > SIL
for x, y in cct.runs(~speech):
    if y - x < 12:
        speech[x:y] = True
for x, y in cct.runs(speech):
    if y - x < 6:
        speech[x:y] = False

zoom_src = [(T(a) - 0.05, T(b, True) + 0.12, why) for a, b, why in J.get("zooms", [])]
in_zoom = lambda t: any(z0 <= t <= z1 for z0, z1, _ in zoom_src)
end_src = J.get("end_src") or (W[-1]["e"] + 0.6)
start_src = J.get("start_src")

keep = np.zeros(N, bool)
k0 = int(start_src * 100) if start_src is not None else max(0, int(np.argmax(speech)) - 8)
keep[k0:int(end_src * 100)] = True
for s, e, _ in removed:
    keep[int(round(s * 100)):int(round(e * 100))] = False
for x, y in cct.runs(~speech):
    if x == 0 or y >= N:
        continue
    t0, t1 = x / 100, y / 100
    min_gap, tail, lead = ZOOM_PACE if in_zoom((t0 + t1) / 2) else PACE
    if t1 - t0 >= min_gap:
        keep[int(round((t0 + tail) * 100)):int(round((t1 - lead) * 100))] = False

clips = [(x / 100, y / 100) for x, y in cct.runs(keep)]
removal_ends = {round(e, 2) for _, e, _ in removed}


def merge_short(clips, min_len=0.7, max_restore=1.0):
    changed = True
    while changed:
        changed = False
        for k, (a, b) in enumerate(clips):
            if b - a >= min_len:
                continue
            opts = []
            if k > 0 and a - clips[k - 1][1] <= max_restore and round(a, 2) not in removal_ends:
                opts.append((a - clips[k - 1][1], k - 1))
            if k + 1 < len(clips) and clips[k + 1][0] - b <= max_restore and round(clips[k + 1][0], 2) not in removal_ends:
                opts.append((clips[k + 1][0] - b, k))
            if opts:
                _, j = min(opts)
                clips[j:j + 2] = [(clips[j][0], clips[j + 1][1])]
                changed = True
                break
    return clips


clips = merge_short(clips)
has_words = lambda a, b: any(w["s"] < b - 0.05 and w["e"] > a + 0.05 for w in W)
dropped = [(a, b) for a, b in clips if not has_words(a, b)]
clips = [(a, b) for a, b in clips if has_words(a, b)]
clips_f = [[cct.fr(a, FPS), cct.fr(b, FPS)] for a, b in clips if cct.fr(b, FPS) - cct.fr(a, FPS) >= 3]
clips_f[-1][1] = max(clips_f[-1][1], cct.fr(W[-1]["e"] + J.get("end_hold", 2.0), FPS))

bounds = sorted({cct.fr(z0, FPS) for z0, _, _ in zoom_src} | {cct.fr(z1, FPS) for _, z1, _ in zoom_src})
split = []
for fa, fb in clips_f:
    inner = [x for x in bounds if fa + 9 < x < fb - 9]
    pts = [fa] + inner + [fb]
    for p, q in zip(pts, pts[1:]):
        split.append({"src0": p, "src1": q, "cont": p in inner})
tl = 0
for c in split:
    c["tl0"] = tl
    tl += c["src1"] - c["src0"]
    c["tl1"] = tl
TOTAL = tl


def src_to_tl(t):
    f = t * FPS
    for c in split:
        if c["src0"] <= f < c["src1"]:
            return (c["tl0"] + f - c["src0"]) / FPS
    for c in split:
        if c["src0"] >= f:
            return c["tl0"] / FPS
    return TOTAL / FPS


PUNCH = J.get("punch", 1.12) or 1.0
zones = [{"tl0": src_to_tl(z0), "tl1": src_to_tl(z1), "why": why} for z0, z1, why in zoom_src]
for z in zones:
    z["dur"] = z["tl1"] - z["tl0"]
prev_end, active = PUNCH, None
for c in split:
    mid = (c["tl0"] + c["tl1"]) / 2 / FPS
    z = next((zz for zz in zones if zz["tl0"] <= mid <= zz["tl1"]), None)
    if z is not None:
        if z is not active:
            s0 = prev_end if c["cont"] else (1.0 if prev_end >= 1.06 else min(1.06, PUNCH))
            amt = min(0.09, max(0.04, 0.012 * z["dur"]), 1.18 - s0)
            z["s0"], z["s1"], active = s0, s0 + amt, z
        ramp = lambda t: z["s0"] + (z["s1"] - z["s0"]) * min(1, max(0, (t - z["tl0"]) / max(1e-6, z["dur"])))
        c["scale0"], c["scale1"] = round(ramp(c["tl0"] / FPS), 4), round(ramp((c["tl1"] - 1) / FPS), 4)
        c["zoom"] = z["why"]
    else:
        active = None
        s = prev_end if c["cont"] else (1.0 if prev_end >= 1.06 else PUNCH)
        c["scale0"] = c["scale1"] = s
        c["zoom"] = None
    prev_end = c["scale1"]


def to_tl(t):
    f = t * FPS
    for c in split:
        if c["src0"] <= f < c["src1"]:
            return round((c["tl0"] + f - c["src0"]) / FPS, 3)
    return None


words_tl = [{"i": w["i"], "w": w["w"].strip(), "s": to_tl(w["s"] + 0.02), "e": to_tl(max(w["s"] + 0.03, w["e"] - 0.02))}
            for w in W]
cct.save(f"{work}/words_tl.json", words_tl)
cct.save(f"{work}/edl.json", {"fps": FPS, "total_frames": TOTAL, "clips": split, "inserts": [], "zones": zones,
                              "removed": [{"s": s, "e": e, "why": w} for s, e, w in removed]})
lens = np.array([(c["src1"] - c["src0"]) / FPS for c in split if not c["cont"]])
print(f"  part {TOTAL / FPS:.1f}s from {(end_src - (W[0]['s'])):.1f}s raw; {len(split)} clips; shortest {lens.min():.2f}s; "
      f"removed {len(removed)}; dropped {len(dropped)} wordless")
