"""Build one 9:16 CapCut timeline per reel (adapted from build.py: multi-file camera, 16:9 -> 9:16 cover crop
with per-part horizontal framing, full-screen B-roll, grade layer, music bed, SFX), then text tracks.

usage: python build_reel.py WORK_DIR SKELETON_DIR [ids...]
  SKELETON_DIR: an empty-ish 9:16 project of the user's (draft_content.json, draft_meta_info.json, Timelines/project.json)
writes WORK_DIR/rNN/build/{draft_content.json, draft_meta_info.json, device_paths.txt, build_report.json, plan.json}
"""
import copy, hashlib, json, os, re, subprocess, sys, time
import cct

work, skel_dir = sys.argv[1], sys.argv[2]
only = set(sys.argv[3:])
REELS = {r["id"]: r for r in json.load(open(f"{work}/reels.json", encoding="utf-8"))}
PLAN = json.load(open(f"{work}/reel_plan.json", encoding="utf-8"))
BDB = json.load(open(f"{work}/broll.json", encoding="utf-8"))
T = cct.load(f"{work}/templates.json")
STYLE = cct.load(f"{work}/style.json")
FPS = 30
us = lambda f: cct.us(f, FPS)
CW, CH = 1080, 1920
# v2 (2026-11-16): face was too big with a full 9:16 cover crop -> smaller frame on a blurred canvas, no B-roll
FRAME = float(os.environ.get("REEL_FRAME", "2.0"))   # camera width as a multiple of the canvas width (cover = 3.16)
BLUR = 0.375                                          # CapCut canvas blur strength
NO_BROLL = os.environ.get("REEL_BROLL", "0") != "1"
MUSIC = {"device": "C:/Users/USER/Downloads/[ 1 HOUR SUMMER TROPICAL BEATS ] CHILLOUT, VLOG INSTRUMENTALS [No Copyright Sound] [FREE USE MUSIC] - Monetization - Instrumentals, Beats.mp3",
         "dur": 3889.344}
SFX = {"whoosh": "C:/Users/USER/Downloads/Claude-Video-Clipper-main/Claude-Video-Clipper-main/assets/sfx/whoosh-cinematic.mp3",
       "click": "C:/Users/USER/Downloads/Claude-Video-Clipper-main/Claude-Video-Clipper-main/assets/sfx/click.wav"}
# media-bin durations from 1228 (CapCut's own numbers)
BIN = {}
meta1228 = cct.load(os.path.join(os.environ["LOCALAPPDATA"], "CapCut", "User Data", "Projects", "com.lveditor.draft", "1228", "draft_meta_info.json"))
for g in meta1228["draft_materials"]:
    for v in g["value"]:
        if v.get("file_Path"):
            BIN[v["file_Path"]] = v


def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_type",
                        "-of", "json", path], capture_output=True, text=True)
    j = json.loads(r.stdout)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    return float(j["format"]["duration"]), v.get("width"), v.get("height")


def loud(path, ss=None, t=None):
    cmd = ["ffmpeg", "-nostats"] + (["-ss", str(ss)] if ss is not None else []) + (["-t", str(t)] if t else []) + \
          ["-i", path, "-af", "ebur128", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)[-1])


def mean_vol(path):
    r = subprocess.run(["ffmpeg", "-i", path, "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True)
    return float(re.findall(r"max_volume:\s+(-?[\d.]+) dB", r.stderr)[-1])


SFX_PEAK = {k: mean_vol(v) for k, v in SFX.items()}
SFX_DUR = {k: probe(v)[0] for k, v in SFX.items()}

skel_name = next(n for n in ("draft_content.json", "draft_info.json") if os.path.exists(f"{skel_dir}/{n}"))
SKEL = cct.load(f"{skel_dir}/{skel_name}")
assert SKEL["canvas_config"]["width"] == 1080 and SKEL["canvas_config"]["height"] == 1920, "skeleton is not 9:16"
SKEL_META = cct.load(f"{skel_dir}/draft_meta_info.json")


def build(rid):
    rd = f"{work}/r{rid}"
    E = cct.load(f"{rd}/reel_edl.json")
    WT = [w for w in cct.load(f"{rd}/words_tl.json") if w["s"] is not None]
    C = cct.load(f"{rd}/captions.json")
    M = copy.deepcopy(SKEL["materials"])
    for k in M:
        if isinstance(M[k], list):
            M[k] = []

    def add(kind, tmpl, **kw):
        o = copy.deepcopy(tmpl)
        o["id"] = cct.U()
        o.update(kw)
        M.setdefault(kind, []).append(o)
        return o["id"]

    def refs(pairs, speed=None):
        return [add(k, o, **({"speed": float(speed)} if (k == "speeds" and speed is not None) else {})) for k, o in pairs]

    def kf(prop, pts):
        return {"id": cct.U(), "material_id": "", "property_type": prop,
                "keyframe_list": [{"id": cct.U(), "curveType": "Line", "time_offset": int(t), "left_control": {"x": 0.0, "y": 0.0},
                                   "right_control": {"x": 0.0, "y": 0.0}, "values": [float(v)], "string_value": "",
                                   "graphID": ""} for t, v in pts]}

    def track(kind, flag=0):
        return {"id": cct.U(), "type": kind, "flag": flag, "attribute": 0, "name": "", "is_default_name": True, "segments": []}

    def vseg(mid, src_us, dur_us, tl_us, s0, s1, vol, x0=0.0, x1=0.0, blur=False):
        s = copy.deepcopy(T["video_segment"])
        vr = [(k, dict(o, type="canvas_blur", blur=BLUR) if (blur and k == "canvases") else o) for k, o in T["video_refs"]]
        s.update({"id": cct.U(), "material_id": mid, "extra_material_refs": refs(vr, speed=1.0),
                  "source_timerange": {"start": src_us, "duration": dur_us},
                  "target_timerange": {"start": tl_us, "duration": dur_us}, "speed": 1.0,
                  "volume": float(vol), "last_nonzero_volume": 1.0, "keyframe_refs": [], "render_index": 0,
                  "track_render_index": 0})
        s["clip"] = {"scale": {"x": s0, "y": s0}, "rotation": 0.0, "transform": {"x": x0, "y": 0.0},
                     "flip": {"vertical": False, "horizontal": False}, "alpha": 1.0}
        s["uniform_scale"] = {"on": True, "value": 1.0}
        if abs(s1 - s0) > 1e-4 or abs(x1 - x0) > 1e-4:
            a, b = src_us, src_us + dur_us - us(1)
            s["common_keyframes"] = [kf("KFTypePositionX", [(a, x0), (b, x1)]), kf("KFTypePositionY", [(a, 0), (b, 0)]),
                                     kf("KFTypeScaleX", [(a, s0), (b, s1)]), kf("KFTypeRotation", [(a, 0), (b, 0)])]
        else:
            s["common_keyframes"] = []
        return s

    def cover(w, h):
        fit = min(CW / w, CH / h)
        return max(CW / w, CH / h) / fit

    # voice level: lift towards -14 LUFS only as far as the peaks allow (true peak <= -1 dBFS)
    voice0 = min(loud(f"{rd}/p{k}/camera_16k.wav") for k in range(len(PLAN[rid]["parts"])))
    peak = max(mean_vol(f"{rd}/p{k}/camera_16k.wav") for k in range(len(PLAN[rid]["parts"])))
    gain_db = max(0.0, min(STYLE["loudness_lufs"] - voice0, -1.0 - peak))
    CAM_VOL = round(10 ** (gain_db / 20), 4)

    # 1 camera: 16:9 4K into 9:16 (cover), framed on the speaker per part, punch-ins x the cover factor
    main = track("video")
    paths = set()
    for c in E["clips"]:
        b = BIN[c["path"]]
        w, h, dur_us = b["width"], b["height"], int(b["duration"])
        cv = min(cover(w, h), FRAME)
        tl_us = us(c["tl0"]); d_us = us(c["tl1"]) - tl_us; src_us = us(c["src0"])
        if src_us + d_us > dur_us:
            assert c is E["clips"][-1], (rid, "camera clip runs past the file end")
            f_end = int((dur_us - src_us) * FPS // 1000000) - 1      # whole frames that still fit
            c["tl1"] = c["tl0"] + f_end
            E["total_frames"] = c["tl1"]
            d_us = us(c["tl1"]) - tl_us
        s0, s1 = cv * c["scale0"], cv * c["scale1"]
        xf = lambda s: max(-(s - 1), min(s - 1, (0.5 - c["f"]) * 2 * s))
        mid = add("videos", T["video_material"], path=c["path"], material_name=os.path.basename(c["path"]),
                  width=w, height=h, duration=dur_us, unique_id="", local_material_id="", media_path="")
        main["segments"].append(vseg(mid, src_us, d_us, tl_us, round(s0, 4), round(s1, 4), CAM_VOL, round(xf(s0), 4), round(xf(s1), 4), blur=cv < cover(w, h)))
        paths.add(c["path"])
    TOTAL = us(E["total_frames"])
    tracks = [main]

    # 2 grade (adjustment layer directly above the main track)
    g = STYLE["grade"]["capcut"]
    adj = dict(copy.deepcopy(T["adjust_track"]), id=cct.U(), segments=[])
    s = copy.deepcopy(T["adjust_segment"])
    rr = []
    for kind, o in T["adjust_refs"]:
        if kind == "effects":
            if o.get("type") in g:
                rr.append(add("effects", o, value=float(g[o["type"]])))
        else:
            rr.append(add(kind, o))
    s.update({"id": cct.U(), "material_id": add(T.get("adjust_placeholder_kind", "placeholders"), T["adjust_placeholder"]),
              "extra_material_refs": rr, "target_timerange": {"start": 0, "duration": TOTAL}, "keyframe_refs": [], "common_keyframes": []})
    adj["segments"].append(s)
    tracks.append(adj)

    # 3 B-roll: full-screen cover, 1.5 s, anchored to the first time the word is said, snapped to camera cuts
    norm = lambda x: re.sub(r"[^a-z0-9$]", "", x.lower())
    cam_cuts = sorted({c["tl0"] / FPS for c in E["clips"] if not c["cont"]} | {E["total_frames"] / FPS})
    items, after = [], 1.2          # never over the first 1.2 s (the hook shows the face)
    for anchor, q in ([] if NO_BROLL else PLAN[rid]["broll"]):
        v = BDB.get(q)
        if not v:
            continue
        w = next((x for x in WT if norm(x["w"]).startswith(norm(anchor)) and x["s"] >= after), None)
        if not w:
            print(f"  ({rid}) no anchor word {anchor!r}")
            continue
        fd, bw, bh = probe(v["device"])
        a = w["s"] - 0.05
        b = min(a + 1.6, E["total_frames"] / FPS - 1.0, a + fd - 0.1)
        if b - a < 0.8:
            continue
        items.append({"a": a, "b": b, "max_dur": fd - 0.1, "name": q, "device": v["device"], "w": bw, "h": bh, "fd": fd})
        after = b + 2.0
    snaps = cct.snap_to_cuts(items, cam_cuts)
    btr = track("video", 2)
    prev = 0
    for it in sorted(items, key=lambda x: x["a"]):
        f0, f1 = cct.fr(it["a"]), cct.fr(it["b"])
        tl_us = max(us(f0), prev); d_us = us(f1) - tl_us
        if d_us < us(15):
            continue
        cv = cover(it["w"], it["h"])
        fdu = int(it["fd"] * 1e6)
        src_us = max(0, min(us(cct.fr(min(1.0, it["fd"] * 0.2))), fdu - d_us - us(1)))
        mid = add("videos", T["video_material"], path=it["device"], material_name=os.path.basename(it["device"]),
                  width=it["w"], height=it["h"], duration=fdu, unique_id="", local_material_id="", media_path="")
        btr["segments"].append(vseg(mid, src_us, d_us, tl_us, round(cv, 4), round(cv + 0.03, 4), 0.0))
        it["tl0"], it["tl1"] = tl_us / 1e6, (tl_us + d_us) / 1e6
        prev = tl_us + d_us
        paths.add(it["device"])
    if btr["segments"]:
        tracks.append(btr)

    # 4 music bed ~15 dB under the voice (a different stretch of the user's own track per reel)
    voice = voice0 + gain_db
    off = 60 + (int(rid) - 1) * 233.0
    mus_l = loud(MUSIC["device"], off, 60)
    vol = 10 ** (((voice - STYLE["music"]["below_voice_db"]) - mus_l) / 20)
    aid = add("audios", T["audio_material"], name=os.path.basename(MUSIC["device"]), path=MUSIC["device"],
              duration=int(MUSIC["dur"] * 1e6), unique_id="", local_material_id="")
    rr = []
    for kind, o in T["audio_refs"]:
        if kind == "audio_fades":
            rr.append(add(kind, o, fade_in_duration=int(0.8e6), fade_out_duration=int(1.5e6)))
        else:
            rr.append(add(kind, o, **({"speed": 1.0} if kind == "speeds" else {})))
    mtr = track("audio")
    s = copy.deepcopy(T["audio_segment"])
    s.update({"id": cct.U(), "material_id": aid, "extra_material_refs": rr,
              "source_timerange": {"start": us(cct.fr(off)), "duration": TOTAL},
              "target_timerange": {"start": 0, "duration": TOTAL}, "volume": round(vol, 5), "last_nonzero_volume": 1.0,
              "speed": 1.0, "keyframe_refs": [], "common_keyframes": [], "render_index": 0})
    mtr["segments"].append(s)
    tracks.append(mtr)
    paths.add(MUSIC["device"])

    # 5 SFX: whoosh as each B-roll cuts in, click on the big keyword (about 6.5 dB under the voice)
    sfx_events = [(it["tl0"] - 0.12, "whoosh") for it in items if "tl0" in it]
    for c in C["captions"]:
        if c.get("big"):
            sfx_events.append((c["a"], "click"))
    str_ = track("audio")
    prev = 0
    for t, k in sorted(sfx_events):
        d_us = min(us(cct.fr(SFX_DUR[k])) - us(1), us(cct.fr(1.2)))
        tl_us = max(us(cct.fr(max(0.0, t))), prev)
        if tl_us + d_us > TOTAL:
            continue
        v = round(10 ** ((voice + 3 - 6.5 - SFX_PEAK[k]) / 20), 4)
        aid = add("audios", T["audio_material"], name=os.path.basename(SFX[k]), path=SFX[k],
                  duration=int(SFX_DUR[k] * 1e6), unique_id="", local_material_id="")
        s = copy.deepcopy(T["audio_segment"])
        s.update({"id": cct.U(), "material_id": aid,
                  "extra_material_refs": refs([p for p in T["audio_refs"] if p[0] != "audio_fades"], speed=1.0),
                  "source_timerange": {"start": 0, "duration": d_us}, "target_timerange": {"start": tl_us, "duration": d_us},
                  "volume": v, "last_nonzero_volume": 1.0, "speed": 1.0, "keyframe_refs": [], "common_keyframes": [],
                  "render_index": 0})
        str_["segments"].append(s)
        prev = tl_us + d_us
        paths.add(SFX[k])
    if str_["segments"]:
        tracks.append(str_)

    for i, tr in enumerate(tracks):
        for s in tr["segments"]:
            s["track_render_index"] = i
            if tr["type"] == "video" and tr["flag"] == 2:
                s["render_index"] = i
    D = copy.deepcopy(SKEL)
    D.update(tracks=tracks, materials=M, duration=TOTAL, fps=float(FPS), id=cct.U())
    D["keyframes"] = {k: [] for k in (SKEL.get("keyframes") or {})}
    cct.validate(D)
    out = f"{rd}/build_base"
    os.makedirs(out, exist_ok=True)
    open(f"{out}/{skel_name}", "w", encoding="utf-8").write(json.dumps(D, ensure_ascii=False, separators=(",", ":")))
    meta = copy.deepcopy(SKEL_META)
    meta.update(tm_duration=TOTAL)
    cct.save(f"{out}/draft_meta_info.json", meta, compact=True)
    cct.save(f"{rd}/build_plan.json", {"broll": [{k: it[k] for k in ("name", "device", "tl0", "tl1")} for it in items if "tl0" in it],
                                       "snaps": snaps, "voice_lufs": voice, "music_vol": vol, "music_offset": off,
                                       "sfx": sfx_events, "cam_vol": CAM_VOL, "gain_db": gain_db, "voice_raw": voice0, "paths": sorted(paths), "seconds": TOTAL / 1e6})
    print(f"{rid}: {TOTAL / 1e6:5.1f}s camera {len(main['segments'])} | broll {len(btr['segments'])} | sfx {len(str_['segments'])} | voice {voice0:.1f}+{gain_db:.1f}dB -> {voice:.1f} LUFS, music vol {vol:.3f}")


for rid in REELS:
    if only and rid not in only:
        continue
    build(rid)
