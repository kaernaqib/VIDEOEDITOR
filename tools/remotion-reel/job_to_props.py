"""Turn a poster-frame job.json (from long_reels.py / poster_job.py) into Remotion props + a public dir.

usage: python job_to_props.py JOB.json PUBLIC_DIR [--no-proxy]
  writes PUBLIC_DIR/{props.json, poster.jpg, audio.wav, sfx/*, proxy_K.mp4}
  render: npx remotion render src/index.ts PosterReel OUT.mp4 --public-dir=PUBLIC_DIR --props=PUBLIC_DIR/props.json

Each source video is cut once into a 1920x1080 H.264 30fps proxy covering only the range the reel uses
(4K HEVC sources are slow to seek and big), then Remotion does all cutting, framing, text and audio.
Subtitle chunks (1-3 words + highlighted word) reuse chunks() from the ffmpeg renderer so both match.
"""
import importlib.util, json, os, shutil, subprocess, sys

FPS, W, BAND_H = 30, 1080, 806
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "rpr", os.path.join(here, "..", "..", "skills", "poster-frame-reel", "scripts", "render_poster_reel.py"))
rpr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpr)

job_path, pub = sys.argv[1], sys.argv[2]
job = json.load(open(job_path, encoding="utf-8"))
os.makedirs(f"{pub}/sfx", exist_ok=True)


def copy(src, name):
    dst = f"{pub}/{name}"
    if not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(src):
        shutil.copy2(src, dst)
    return name


# proxies: one per source file, covering [min t0 - 1, max t1 + 1]
sources = {}
for c in job["clips"]:
    s = sources.setdefault(c["path"], [1e9, 0])
    s[0], s[1] = min(s[0], c["t0"]), max(s[1], c["t1"])
proxy = {}
for k, (path, (a, b)) in enumerate(sources.items()):
    a = max(0.0, a - 1.0)
    name = f"proxy_{k}.mp4"
    proxy[path] = (name, a)
    if "--no-proxy" in sys.argv and os.path.exists(f"{pub}/{name}"):
        continue
    print(f"proxy {name}: {os.path.basename(path)} {a:.1f}-{b + 1:.1f}s")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", path, "-t", f"{b + 1 - a:.3f}",
                    "-vf", "fps=30,scale=1920:1080:flags=lanczos,format=yuv420p", "-an",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-g", "30", f"{pub}/{name}"], check=True)

clips, frame = [], 0
for c in job["clips"]:
    name, base = proxy[c["path"]]
    # same crop as band_vf(): 4:3-ish window centred on f * width -> CSS object-position x%
    cw = 1080 * W / BAND_H
    x0 = max(0, min(1920 - cw, c.get("f", 0.5) * 1920 - cw / 2))
    clips.append({"src": name, "startFromSec": round(c["t0"] - base, 4), "from": frame, "frames": c["frames"],
                  "posX": round(100 * x0 / (1920 - cw), 2)})
    frame += c["frames"]

sfx_dir = job.get("sfx_dir", "D:/CLAUDE/kerja/_sfx")
sfx = []
for s in job.get("sfx", []):
    name = "sfx/" + os.path.basename(s["file"])
    copy(os.path.join(sfx_dir, s["file"]), name)
    sfx.append({"src": name, "t": s["t"], "vol": s["vol"], "dur": s["dur"]})

cap = lambda w: w[:1].upper() + w[1:]
subs = [{"a": round(c["a"], 3), "b": round(c["b"], 3), "w": [cap(w) for w in c["w"]], "hi": c["hi"]}
        for c in rpr.chunks(job)]

# poster crop like tile_img(): face (focus y) at 30% of the 1080x610 poster area -> CSS object-position y%
P = job["poster"]
from PIL import Image
pw, ph_ = Image.open(P["image"]).size
ch = ph_ / P.get("zoom", 1.0)
cw = ch * 1080 / 610
if cw > pw:
    cw = pw; ch = cw * 610 / 1080
y0 = min(max(0, P.get("focus", [0.5, 0.35])[1] * ph_ - ch * P.get("face_at", 0.30)), ph_ - ch)
poster_y = round(100 * y0 / (ph_ - ch), 2) if ph_ > ch else 50

props = {
    "poster": copy(P["image"], "poster.jpg"),
    "posterPosY": poster_y,
    "audio": copy(job["audio"], "audio.wav") if job.get("audio") else None,
    "headline": [l if isinstance(l, str) else l["text"] for l in job["headline"]],
    "accentLine": job.get("accent_line", 0),
    "durationFrames": frame,
    "clips": clips, "sfx": sfx, "subs": subs,
}
json.dump(props, open(f"{pub}/props.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"props: {frame / FPS:.1f}s, {len(clips)} clips, {len(subs)} subtitle chunks, {len(sfx)} sfx -> {pub}/props.json")
