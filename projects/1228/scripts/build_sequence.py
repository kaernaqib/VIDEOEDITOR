"""Write a CapCut timeline whose main track is a SEQUENCE of clips (vlog and faceless modes), plus a voice track,
the style's adjustment layer(s) and music. Talking-head edits use build.py instead.

usage: python3 build_sequence.py WORK_DIR PROJECT_COPY_DIR OUT_DIR
  WORK_DIR: sequence.json, templates.json (harvest.py), style.json (copy of styles/<id>/style.json)
  PROJECT_COPY_DIR: the (empty) target project's draft_info.json (or draft_content.json), draft_meta_info.json,
                    Timelines/project.json
sequence.json:
  {"fps": 30, "end": 41.2,
   "voice": {"device": "C:/.../vo_clean.wav", "local": "work/vo_clean.wav", "dur": 40.0, "start": 0.0} | null,
   "clips": [{"a": 0.0, "b": 2.1, "device": "C:/.../clip.mp4", "kind": "video"|"photo", "w": 1920, "h": 1080,
              "src": 3.5, "file_dur": 12.0, "audio": 0|1 (keep the clip's own sound, e.g. vlog talking bits),
              "push": 0.02 (slow push-in amount), "bw": false}],
   "music": [{"device", "local", "start", "end", "src" | "align", "fin", "fout"}],
   "music_below_voice_db": 15}
Every clip fills the 9:16 canvas (cover). Clips must be contiguous from 0 to "end" (faceless_plan.py guarantees it).
"bw": true puts that span under a B&W adjustment segment (style.grade.bw_segments must allow it).
"""
import copy, hashlib, json, os, re, subprocess, sys, time
import cct

work, proj, outd = sys.argv[1:4]
Q = cct.load(f"{work}/sequence.json")
T = cct.load(f"{work}/templates.json")
ST = cct.load(f"{work}/style.json")
FPS = Q.get("fps", 30)
us = lambda f: cct.us(f, FPS)

name = next(n for n in ("draft_info.json", "draft_content.json") if os.path.exists(f"{proj}/{n}"))
assert open(f"{proj}/{name}", "rb").read().lstrip()[:1] == b"{", "this CapCut build encrypts projects"
skel = cct.load(f"{proj}/{name}")
meta = cct.load(f"{proj}/draft_meta_info.json")
tl_id = cct.load(f"{proj}/Timelines/project.json").get("main_timeline_id") if os.path.exists(f"{proj}/Timelines/project.json") else None
cv = skel.get("canvas_config") or {}
CW, CH = cv.get("width", 1080), cv.get("height", 1920)

M = copy.deepcopy(skel["materials"])
for k in M:
    if isinstance(M[k], list):
        M[k] = []


def add(kind, tmpl, **kw):
    o = copy.deepcopy(tmpl); o["id"] = cct.U(); o.update(kw); M.setdefault(kind, []).append(o); return o["id"]


def refs(pairs, speed=None, skip=()):
    return [add(k, o, **({"speed": float(speed)} if (k == "speeds" and speed is not None) else {})) for k, o in pairs if k not in skip]


def kf(prop, pts):
    return {"id": cct.U(), "material_id": "", "property_type": prop,
            "keyframe_list": [{"id": cct.U(), "curveType": "Line", "time_offset": int(t), "left_control": {"x": 0.0, "y": 0.0},
                               "right_control": {"x": 0.0, "y": 0.0}, "values": [float(v)], "string_value": "", "graphID": ""} for t, v in pts]}


def track(kind, flag=0):
    return {"id": cct.U(), "type": kind, "flag": flag, "attribute": 0, "name": "", "is_default_name": True, "segments": []}


def cover(w, h):
    """CapCut scale 1.0 = fit inside the canvas; this is the scale that fills it."""
    return round(max(CW / w, CH / h) / min(CW / w, CH / h), 4)


def lufs(path):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])


clips = sorted(Q["clips"], key=lambda c: c["a"])
assert clips and abs(clips[0]["a"]) < 1e-3, "the first clip must start at 0"
for x, y in zip(clips, clips[1:]):
    assert abs(x["b"] - y["a"]) < 1e-3, f"gap or overlap at {x['b']} -> {y['a']}: re-run faceless_plan.py"
missing = [c for c in clips if not c.get("device")]
assert not missing, f"{len(missing)} clips have no device (NEEDS_VISUAL): fetch visuals first"

# 1 main track: the sequence
main = track("video")
f_prev = 0
for c in clips:
    f0, f1 = f_prev, cct.fr(c["b"], FPS)
    f_prev = f1
    tl_us, dur_us = us(f0), us(f1) - us(f0)
    s0 = cover(c["w"], c["h"])
    s1 = round(s0 * (1 + c.get("push", 0.02)), 4)
    if c["kind"] == "video":
        fd = int(c["file_dur"] * 1e6)
        src_us = us(cct.fr(c.get("src", 0.0), FPS))
        assert src_us + dur_us <= fd, (c.get("show") or c["device"], "runs past the end of its file")
        mid = add("videos", T["video_material"], path=c["device"], material_name=os.path.basename(c["device"]),
                  width=c["w"], height=c["h"], duration=fd, unique_id="", local_material_id="", media_path="")
    else:
        src_us = 0
        mid = add("videos", T["photo_material"], path=c["device"], material_name=os.path.basename(c["device"]),
                  width=c["w"], height=c["h"], unique_id="", local_material_id="", media_path="")
    s = copy.deepcopy(T["video_segment"])
    s.update({"id": cct.U(), "material_id": mid, "extra_material_refs": refs(T["video_refs"], speed=1.0),
              "source_timerange": {"start": src_us, "duration": dur_us}, "target_timerange": {"start": tl_us, "duration": dur_us},
              "speed": 1.0, "volume": float(c.get("audio", 0)), "last_nonzero_volume": 1.0, "keyframe_refs": [],
              "render_index": 0, "track_render_index": 0})
    s["clip"] = {"scale": {"x": s0, "y": s0}, "rotation": 0.0, "transform": {"x": 0.0, "y": 0.0},
                 "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0}
    s["uniform_scale"] = {"on": True, "value": 1.0}
    a, b = src_us, src_us + dur_us - us(1)        # keyframes are in SOURCE time
    s["common_keyframes"] = [kf("KFTypePositionX", [(a, 0), (b, 0)]), kf("KFTypePositionY", [(a, 0), (b, 0)]),
                             kf("KFTypeScaleX", [(a, s0), (b, s1)]), kf("KFTypeRotation", [(a, 0), (b, 0)])] if s1 != s0 else []
    main["segments"].append(s)
TOTAL = us(f_prev)
tracks = [main]

# 2 grade: the style's adjustment layer over everything, then B&W spans
grade = (ST.get("grade") or {}).get("capcut") or {}
if "adjust_segment" in T and grade:
    adj = dict(copy.deepcopy(T["adjust_track"]), id=cct.U(), segments=[])
    s = copy.deepcopy(T["adjust_segment"])
    rr = []
    for kind, o in T["adjust_refs"]:
        if kind == "effects":
            if o.get("type") in grade:
                rr.append(add("effects", o, value=float(grade[o["type"]])))
        else:
            rr.append(add(kind, o))
    s.update({"id": cct.U(), "material_id": add("placeholders", T["adjust_placeholder"]), "extra_material_refs": rr,
              "target_timerange": {"start": 0, "duration": TOTAL}, "keyframe_refs": [], "common_keyframes": []})
    adj["segments"].append(s)
    tracks.append(adj)
    skipped = sorted(set(grade) - {o.get("type") for k, o in T["adjust_refs"] if k == "effects"})
    if skipped:
        print("grade: the template's adjustment layer has no", skipped, "- set them once in the style template")
    bw = [c for c in clips if c.get("bw")]
    if bw and (ST.get("grade") or {}).get("bw_segments"):
        sat = next((o for k, o in T["adjust_refs"] if k == "effects" and o.get("type") == "saturation"), None)
        assert sat, "B&W needs a saturation effect in the template's adjustment layer"
        bwt = dict(copy.deepcopy(T["adjust_track"]), id=cct.U(), segments=[])
        for c in bw:
            t0, t1 = us(cct.fr(c["a"], FPS)), us(cct.fr(c["b"], FPS))
            s = copy.deepcopy(T["adjust_segment"])
            s.update({"id": cct.U(), "material_id": add("placeholders", T["adjust_placeholder"]),
                      "extra_material_refs": [add("effects", sat, value=-1.0)],
                      "target_timerange": {"start": t0, "duration": t1 - t0}, "keyframe_refs": [], "common_keyframes": []})
            bwt["segments"].append(s)
        tracks.append(bwt)

# 3 voice + music
def audio_seg(dev, local, start, src, dur_s, vol, fin=0.0, fout=0.0):
    fdur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", local],
                                capture_output=True, text=True).stdout)
    tl_us = us(cct.fr(start, FPS))
    src_us = us(cct.fr(src, FPS))
    dur_us = min(us(cct.fr(dur_s, FPS)), int(fdur * 1e6) - src_us - us(1), TOTAL - tl_us)
    aid = add("audios", T["audio_material"], name=os.path.basename(dev), path=dev, duration=int(fdur * 1e6), unique_id="", local_material_id="")
    rr = []
    for kind, o in T["audio_refs"]:
        if kind == "audio_fades":
            rr.append(add(kind, o, fade_in_duration=int(fin * 1e6), fade_out_duration=int(fout * 1e6)))
        else:
            rr.append(add(kind, o, **({"speed": 1.0} if kind == "speeds" else {})))
    s = copy.deepcopy(T["audio_segment"])
    s.update({"id": cct.U(), "material_id": aid, "extra_material_refs": rr, "source_timerange": {"start": src_us, "duration": dur_us},
              "target_timerange": {"start": tl_us, "duration": dur_us}, "volume": round(vol, 5), "last_nonzero_volume": 1.0,
              "speed": 1.0, "keyframe_refs": [], "common_keyframes": [], "render_index": 0})
    return s


V = Q.get("voice")
voice_lufs = None
if V:
    vt = track("audio")
    vt["segments"].append(audio_seg(V["device"], V["local"], V.get("start", 0.0), 0.0, V["dur"], 1.0))
    tracks.append(vt)
    voice_lufs = lufs(V["local"])
mus = [track("audio"), track("audio")]
below = Q.get("music_below_voice_db", (ST.get("music") or {}).get("below_voice_db", 15))
for k, m in enumerate(Q.get("music", [])):
    src = m["align"][0] - (m["align"][1] - m["start"]) if "align" in m else m.get("src", 0.0)
    ref = voice_lufs if voice_lufs is not None else ST.get("loudness_lufs", -14)
    vol = 10 ** (((ref - below) - lufs(m["local"])) / 20)
    mus[k % 2]["segments"].append(audio_seg(m["device"], m["local"], m["start"], max(0.0, src), m["end"] - m["start"], vol,
                                            m.get("fin", 1.2), m.get("fout", 1.2)))
tracks += [t for t in mus if t["segments"]]

for i, tr in enumerate(tracks):
    for s in tr["segments"]:
        s["track_render_index"] = i
D = copy.deepcopy(skel)
D.update(tracks=tracks, materials=M, duration=TOTAL, fps=float(FPS))
D["keyframes"] = {k: [] for k in (skel.get("keyframes") or {})}
cct.validate(D)

os.makedirs(outd, exist_ok=True)
blob = json.dumps(D, ensure_ascii=False, separators=(",", ":"))
open(f"{outd}/{name}", "w", encoding="utf-8").write(blob)
meta.update(tm_duration=TOTAL, tm_draft_modified=int(time.time() * 1e6))
cct.save(f"{outd}/draft_meta_info.json", meta, compact=True)
targets = [name, name + ".bak", "template-2.tmp"] + ([f"Timelines/{tl_id}/{n}" for n in (name, name + ".bak", "template-2.tmp")] if tl_id else [])
open(f"{outd}/install_targets.txt", "w").write("\n".join(targets) + "\n")
paths = sorted({m["path"] for m in M["videos"]} | {m["path"] for m in M.get("audios", [])})
open(f"{outd}/device_paths.txt", "w").write("\n".join(paths) + "\n")
md5 = hashlib.md5(blob.encode("utf-8")).hexdigest()
cct.save(f"{outd}/build_report.json", {"md5": md5, "seconds": TOTAL / 1e6, "voice_lufs": voice_lufs,
                                       "tracks": [(t["type"], t["flag"], len(t["segments"])) for t in tracks]})
print(f"built {name}: {[(t['type'], len(t['segments'])) for t in tracks]}, {TOTAL / 1e6:.2f}s, canvas {CW}x{CH}, md5 {md5}")
