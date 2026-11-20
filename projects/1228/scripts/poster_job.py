"""Build a poster-frame-reel job for one 1228 reel and render it.

usage: python poster_job.py WORK_DIR NN OUT_DIR [--still]
  reads WORK_DIR/rNN/{reel_edl.json, captions.json, words_tl.json, preview_raw.mp4} and WORK_DIR/poster_hooks.json
  writes OUT_DIR/reel_NN_poster.json and renders OUT_DIR/reel_NN_poster.mp4 with skills/poster-frame-reel
"""
import json, os, subprocess, sys

work, nn, out_dir = sys.argv[1], sys.argv[2].zfill(2), sys.argv[3]
rd = f"{work}/r{nn}"
L = lambda p: json.load(open(p, encoding="utf-8"))
edl, hooks = L(f"{rd}/reel_edl.json"), L(f"{work}/poster_hooks.json")
hk = hooks[nn]
fps = edl["fps"]


def tl_to_src(sec):
    fr = sec * fps
    for c in edl["clips"]:
        if c["tl0"] <= fr < c["tl1"]:
            return c["path"], (c["src0"] + fr - c["tl0"]) / fps
    c = edl["clips"][0]
    return c["path"], c["src0"] / fps


series = hooks.get("_series", {})
if hk.get("poster"):                                       # per-reel poster from reel frames: [{"tl", "focus", "zoom"}]
    tiles = []
    for p in hk["poster"]:
        src, t = tl_to_src(p["tl"])
        tiles.append(dict({k: v for k, v in p.items() if k != "tl"}, video=src, t=t))
    poster = {"tiles": tiles}
else:                                                      # one general series poster for every reel
    poster = {"image": series["poster_image"], "zoom": 1.0, "contrast": 1.0, "saturation": 1.0}
sfx_dir = series.get("sfx_dir", "D:/CLAUDE/kerja/_sfx")
lib = {x["name"]: x for x in L(f"{sfx_dir}/library.json")} if hk.get("sfx") else {}
sfx = [{"t": s["t"], "file": lib[s["name"]]["file"], "vol": s.get("vol", 0.5), "dur": s.get("dur", min(2.5, lib[s["name"]]["dur"]))}
       for s in hk.get("sfx", [])]
os.makedirs(out_dir, exist_ok=True)
job = {
    "out": f"{out_dir}/reel_{nn}_poster.mp4",
    "tmp": f"{rd}/_poster",
    "poster": poster,
    "sfx": sfx, "sfx_dir": sfx_dir,
    "pill": hk.get("pill") or [p.replace("{n}", str(int(nn))) for p in series.get("pill", [])] or None,
    "headline": hk["headline"],
    "accent_line": hk.get("accent_line", 0),
    "edl_fps": fps,
    "clips": [{k: c[k] for k in ("path", "src0", "src1", "f", "scale0", "scale1")} for c in edl["clips"]],
    "audio": f"{rd}/preview_raw.mp4",
    "captions": L(f"{rd}/captions.json")["captions"],
    "words": L(f"{rd}/words_tl.json"),
}
jp = f"{out_dir}/reel_{nn}_poster.json"
json.dump(job, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
here = os.path.dirname(os.path.abspath(__file__))
renderer = os.path.join(here, "..", "..", "..", "skills", "poster-frame-reel", "scripts", "render_poster_reel.py")
if not os.path.exists(renderer):
    renderer = os.path.expanduser("~/.claude/skills/poster-frame-reel/scripts/render_poster_reel.py")
subprocess.run([sys.executable, renderer, jp] + sys.argv[4:], check=True)
