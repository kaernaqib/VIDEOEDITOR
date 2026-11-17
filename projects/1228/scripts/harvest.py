"""Harvest CapCut object templates from the viewer's OWN saved projects.

usage: python harvest.py OUT_templates.json DRAFT.json [DRAFT.json ...]
"""
import copy, json, sys
import cct

out, paths = sys.argv[1], sys.argv[2:]
T = {"source": [], "version": None}

LOOKS = ("effects", "hsl", "color_curves", "hsl_curves", "primary_color_wheels", "log_color_wheels", "video_effects",
         "common_mask", "chromas", "beats", "audio_effects", "realtime_denoises", "audio_track_indexes")


def refs_of(draft, seg):
    m = cct.all_materials(draft)
    return [[m[r][0], copy.deepcopy(m[r][1])] for r in seg["extra_material_refs"] if r in m and m[r][0] not in LOOKS]


for p in paths:
    try:
        d = cct.load(p)
    except Exception:
        print("skipped (not plain JSON):", p)
        continue
    m = cct.all_materials(d)
    ver = (d.get("last_modified_platform") or d.get("platform") or {}).get("app_version")
    used = False
    for ti, tr in enumerate(d["tracks"]):
        for s in tr["segments"]:
            kind, mat = m.get(s["material_id"], (None, {}))
            if tr["type"] == "video" and kind == "videos" and mat.get("type") == "video" and "video_segment" not in T:
                T["video_segment"] = copy.deepcopy(s)
                T["video_refs"] = refs_of(d, s)
                T["video_material"] = copy.deepcopy(mat)
                used = True
            if tr["type"] == "video" and kind == "videos" and mat.get("type") == "photo" and "photo_material" not in T:
                T["photo_material"] = copy.deepcopy(mat)
                used = True
            if tr["type"] == "audio" and kind == "audios" and "audio_segment" not in T:
                r = refs_of(d, s)
                if any(k == "audio_fades" for k, _ in r):
                    T["audio_segment"] = copy.deepcopy(s)
                    T["audio_refs"] = r
                    T["audio_material"] = copy.deepcopy(mat)
                    used = True
            if tr["type"] == "adjust" and "adjust_segment" not in T:
                T["adjust_track"] = {k: v for k, v in tr.items() if k != "segments"}
                T["adjust_segment"] = copy.deepcopy(s)
                T["adjust_placeholder"] = copy.deepcopy(mat)
                T["adjust_placeholder_kind"] = kind
                T["adjust_refs"] = [[m[r][0], copy.deepcopy(m[r][1])] for r in s["extra_material_refs"] if r in m]
                used = True
    if used:
        T["source"].append(p)
        T["version"] = T["version"] or ver

missing = [k for k in ("video_segment", "audio_segment", "adjust_segment") if k not in T]
if "photo_material" not in T and "video_material" in T:
    pm = copy.deepcopy(T["video_material"])
    pm.update(type="photo", duration=10800000000, has_audio=False)
    T["photo_material"] = pm
if "adjust_refs" in T:
    effects = [o for k, o in T["adjust_refs"] if k == "effects"]
    have = {o.get("type") for o in effects}
    if effects:
        for need in ("saturation", "contrast", "shadow"):
            if need not in have:
                e = copy.deepcopy(effects[0])
                e.update(type=need, value=0.0)
                T["adjust_refs"].append(["effects", e])
cct.save(out, T)
print("templates from", T["source"], "CapCut", T["version"])
print("MISSING:", missing if missing else "nothing")
