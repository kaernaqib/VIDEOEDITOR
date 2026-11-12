"""Measure the look of reference reels, to build or check a style pack.

usage: python3 analyze_style.py OUT.json REF1.mp4 [REF2.mp4 ...] [--sheets DIR]
Per reel and averaged over all of them:
  - pacing: cuts (scene changes), average shot length, cuts per 10 s
  - loudness: integrated LUFS, true peak
  - picture: brightness, contrast (luma std), saturation, warmth (R-B), share of near-B&W frames,
    shadow / highlight tint, dominant colours (top 6, hex)
  - captions: where bright saturated text sits (top / middle / bottom thirds), from yellow-ish pixel mass
--sheets DIR also writes a 6x4 contact sheet per reel (keep those LOCAL: they are frames of someone else's video;
never commit them to a public repo).
Fill style.json's "measured" block from the "average" result; the human-judgement fields come from looking at the sheets.
"""
import json, os, re, subprocess, sys
import numpy as np
from PIL import Image

args = [a for a in sys.argv[1:]]
sheets = None
if "--sheets" in args:
    i = args.index("--sheets"); sheets = args[i + 1]; del args[i:i + 2]
out, refs = args[0], args[1:]
assert refs, __doc__


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def duration(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout)


def cuts(p, thr=0.3):
    r = run(["ffmpeg", "-hide_banner", "-i", p, "-vf", f"select='gt(scene,{thr})',showinfo", "-an", "-f", "null", "-"])
    return [float(x) for x in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def loudness(p):
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", p, "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    return (float(i[-1]) if i else None), (float(tp[-1]) if tp else None)


def frames(p, n=48, w=160):
    d = duration(p)
    wv, hv = (int(x) for x in run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                    "stream=width,height", "-of", "csv=p=0", p]).stdout.strip().split(",")[:2])
    hh = int(round(hv * w / wv / 2) * 2)
    buf = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-vf", f"fps={n / max(d, 1):.4f},scale={w}:{hh}",
                                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout, np.uint8)
    return buf.reshape(-1, hh, w, 3).astype(np.float32) / 255.0


def palette(px, k=6, iters=12):
    rng = np.random.default_rng(0)
    pts = px.reshape(-1, 3)
    pts = pts[rng.choice(len(pts), min(20000, len(pts)), replace=False)]
    c = pts[rng.choice(len(pts), k, replace=False)]
    for _ in range(iters):
        lab = np.argmin(((pts[:, None] - c[None]) ** 2).sum(-1), 1)
        c = np.array([pts[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
    share = np.bincount(lab, minlength=k) / len(lab)
    order = np.argsort(-share)
    return [{"hex": "#%02X%02X%02X" % tuple(int(v * 255) for v in c[j]), "share": round(float(share[j]), 3)} for j in order]


def picture(F):
    r, g, b = F[..., 0], F[..., 1], F[..., 2]
    luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
    mx, mn = F.max(-1), F.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    per_frame_sat = sat.reshape(len(F), -1).mean(1)
    sh, hi = luma < 0.25, luma > 0.75
    tint = lambda m: [round(float(F[..., k][m].mean() - luma[m].mean()), 3) if m.any() else 0.0 for k in range(3)]
    # caption-like pixels: bright + yellow (R,G high, B low) or bright white with high local contrast
    yellow = (r > .75) & (g > .62) & (b < .35)
    rows = yellow.reshape(len(F), F.shape[1], F.shape[2]).sum((0, 2)).astype(float)
    thirds = np.array_split(rows, 3)
    tot = rows.sum() or 1
    return {
        "brightness": round(float(luma.mean()), 3),
        "contrast": round(float(luma.reshape(len(F), -1).std(1).mean()), 3),
        "saturation": round(float(sat.mean()), 3),
        "warmth_r_minus_b": round(float((r - b).mean()), 3),
        "bw_frame_share": round(float((per_frame_sat < 0.06).mean()), 3),
        "shadow_tint_rgb": tint(sh),
        "highlight_tint_rgb": tint(hi),
        "yellow_text_by_third": {"top": round(thirds[0].sum() / tot, 2), "middle": round(thirds[1].sum() / tot, 2),
                                 "bottom": round(thirds[2].sum() / tot, 2)},
        "palette": palette(F),
    }


res = {"refs": {}}
for p in refs:
    d = duration(p)
    c = cuts(p)
    i, tp = loudness(p)
    F = frames(p)
    name = os.path.basename(p)
    res["refs"][name] = {
        "duration_s": round(d, 2), "cuts": len(c), "avg_shot_s": round(d / (len(c) + 1), 2),
        "cuts_per_10s": round(10 * len(c) / d, 2), "lufs": i, "true_peak_db": tp, **picture(F),
    }
    if sheets:
        os.makedirs(sheets, exist_ok=True)
        run(["ffmpeg", "-v", "error", "-y", "-i", p, "-vf", f"fps={24 / max(d, 1):.4f},scale=240:-2,tile=6x4", "-frames:v", "1",
             os.path.join(sheets, os.path.splitext(name)[0][:40] + ".jpg")])
    print(f"{name[:50]:50s} {d:5.1f}s cuts {len(c):3d} shot {d / (len(c) + 1):4.2f}s  {i} LUFS  "
          f"sat {res['refs'][name]['saturation']:.2f} warm {res['refs'][name]['warmth_r_minus_b']:+.3f}")

keys = ["duration_s", "cuts_per_10s", "avg_shot_s", "lufs", "brightness", "contrast", "saturation", "warmth_r_minus_b", "bw_frame_share"]
R = list(res["refs"].values())
res["average"] = {k: round(float(np.mean([x[k] for x in R if x[k] is not None])), 3) for k in keys}
res["average"]["yellow_text_by_third"] = {t: round(float(np.mean([x["yellow_text_by_third"][t] for x in R])), 2) for t in ("top", "middle", "bottom")}
json.dump(res, open(out, "w"), indent=1)
print("average:", json.dumps(res["average"]))
