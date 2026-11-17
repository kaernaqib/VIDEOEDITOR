"""Full-res 1080x1920 frame of a reel at timeline time T, framed exactly like the camera clip.
usage: python thumb_frame.py REEL_DIR T OUT.jpg"""
import json, subprocess, sys

rd, t, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
D = json.load(open(f"{rd}/build/draft_content.json", encoding="utf-8"))
M = {o["id"]: o for k, v in D["materials"].items() if isinstance(v, list) for o in v if isinstance(o, dict) and "id" in o}
for s in D["tracks"][0]["segments"]:
    a, d = s["target_timerange"]["start"] / 1e6, s["target_timerange"]["duration"] / 1e6
    if a <= t < a + d:
        break
mat = M[s["material_id"]]
sc, x = s["clip"]["scale"]["x"], s["clip"]["transform"]["x"]
w, h = mat["width"], mat["height"]
r = 1 / (min(1080 / w, 1920 / h) * sc)
cw, ch = 1080 * r, 1920 * r
x0 = max(0, min(w - cw, w / 2 - x * 540 * r - cw / 2)); y0 = max(0, (h - ch) / 2)
src = s["source_timerange"]["start"] / 1e6 + (t - a)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{src:.3f}", "-i", mat["path"], "-frames:v", "1",
                "-vf", f"crop={int(cw)}:{int(ch)}:{int(x0)}:{int(y0)},scale=1080:1920,eq=contrast=1.08:saturation=1.08",
                "-q:v", "2", out], check=True)
print(out)
