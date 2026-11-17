"""540x960 preview rendered from the built 9:16 draft (crop/framing, B-roll, grade approx, music, SFX).
usage: python preview_reel.py REEL_DIR      (reads REEL_DIR/build/draft_content.json, writes REEL_DIR/preview_raw.mp4)
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

rd = sys.argv[1]
D = json.load(open(f"{rd}/build/draft_content.json", encoding="utf-8"))
M = {o["id"]: (k, o) for k, v in D["materials"].items() if isinstance(v, list) for o in v if isinstance(o, dict) and "id" in o}
FPS, W, H = 30, 540, 960
tmp = f"{rd}/_pv"
os.makedirs(tmp, exist_ok=True)
sec = lambda u: u / 1e6


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(" ".join(cmd[:14]) + "\n" + r.stderr[-1200:])


def geom(seg, mat):
    sc = seg["clip"]["scale"]["x"]; x = seg["clip"]["transform"]["x"]
    for k in seg.get("common_keyframes") or []:
        vals = [p["values"][0] for p in k["keyframe_list"]]
        if k["property_type"] == "KFTypeScaleX":
            sc = sum(vals) / len(vals)
        if k["property_type"] == "KFTypePositionX":
            x = sum(vals) / len(vals)
    w, h = mat["width"], mat["height"]
    fit = min(1080 / w, 1920 / h)
    r = 1 / (fit * sc)                       # source px per canvas px
    cw, ch = 1080 * r, 1920 * r
    cx = w / 2 - x * 540 * r
    x0 = max(0, min(w - cw, cx - cw / 2)); y0 = max(0, (h - ch) / 2)
    return f"crop={int(cw)}:{int(ch)}:{int(x0)}:{int(y0)},scale={W}:{H},setsar=1"


EQ = "eq=contrast=1.08:saturation=1.05"
main = D["tracks"][0]["segments"]


def cam(k_s):
    k, s = k_s
    mat = M[s["material_id"]][1]
    n = round(sec(s["target_timerange"]["duration"]) * FPS)
    o = f"{tmp}/c{k:03d}.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{sec(s['source_timerange']['start']):.4f}", "-i", mat["path"],
         "-frames:v", str(n), "-vf", f"fps={FPS},{geom(s, mat)},{EQ},format=yuv420p",
         "-af", f"volume={s.get('volume', 1)},atrim=0:{n / FPS:.4f},apad", "-t", f"{n / FPS:.4f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-c:a", "aac", "-ar", "48000", "-ac", "2", o])
    return o


with ThreadPoolExecutor(3) as ex:
    clips = list(ex.map(cam, enumerate(main)))
open(f"{tmp}/list.txt", "w").write("".join(f"file '{os.path.abspath(c)}'\n" for c in clips))
run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/list.txt", "-c", "copy", f"{tmp}/camera.mp4"])

inputs, fc, last, al, n = ["-i", f"{tmp}/camera.mp4"], [], "[0:v]", ["[0:a]"], 1
for tr in D["tracks"][1:]:
    for s in tr["segments"]:
        k, mat = M[s["material_id"]]
        st, du = s.get("source_timerange") or {}, s["target_timerange"]
        t0, d = sec(du["start"]), sec(du["duration"])
        if tr["type"] == "video" and k == "videos":
            inputs += ["-ss", f"{sec(st['start']):.3f}", "-t", f"{d + 0.1:.3f}", "-i", mat["path"]]
            fc.append(f"[{n}:v]fps={FPS},{geom(s, mat)},setpts=PTS-STARTPTS+{t0:.3f}/TB[o{n}]")
            fc.append(f"{last}[o{n}]overlay=eof_action=pass:enable='between(t,{t0:.3f},{t0 + d - 0.02:.3f})'[v{n}]")
            last = f"[v{n}]"; n += 1
        elif tr["type"] == "audio":
            fin = fout = 0.0
            for r in s["extra_material_refs"]:
                kk, o = M.get(r, (None, {}))
                if kk == "audio_fades":
                    fin, fout = sec(o.get("fade_in_duration", 0)), sec(o.get("fade_out_duration", 0))
            inputs += ["-ss", f"{sec(st['start']):.3f}", "-t", f"{d:.3f}", "-i", mat["path"]]
            f = f"[{n}:a]asetpts=PTS-STARTPTS,aresample=48000,aformat=channel_layouts=stereo,volume={s.get('volume', 1):.5f}"
            if fin:
                f += f",afade=t=in:st=0:d={fin:.2f}"
            if fout:
                f += f",afade=t=out:st={max(0, d - fout):.3f}:d={fout:.2f}"
            fc.append(f + f",adelay={int(t0 * 1000)}:all=1[a{n}]")
            al.append(f"[a{n}]"); n += 1
fc.append("".join(al) + f"amix=inputs={len(al)}:normalize=0:duration=first[a]")
run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(fc), "-map", last if last != "[0:v]" else "0:v",
     "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-c:a", "aac", "-b:a", "128k",
     "-movflags", "+faststart", f"{rd}/preview_raw.mp4"])
print("preview ->", f"{rd}/preview_raw.mp4")
