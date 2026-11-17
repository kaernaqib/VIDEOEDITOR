"""Map 1228's main track + CapCut auto-caption word timings back to SOURCE files.

usage: python extract_words.py DRAFT.json OUT.json
writes: {"segments": [{tl0, tl1, path, src0, vol}], "words": [{w, tl_s, tl_e, path, s, e}]}
"""
import json, sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
m = {}
for k, v in d["materials"].items():
    if isinstance(v, list):
        for o in v:
            if isinstance(o, dict) and "id" in o:
                m[o["id"]] = (k, o)
segs = []
for s in d["tracks"][0]["segments"]:
    k, o = m[s["material_id"]]
    segs.append({"tl0": s["target_timerange"]["start"] / 1e6,
                 "tl1": (s["target_timerange"]["start"] + s["target_timerange"]["duration"]) / 1e6,
                 "path": o.get("path"), "src0": s["source_timerange"]["start"] / 1e6,
                 "speed": s.get("speed", 1.0), "vol": s.get("volume", 1.0)})


def to_src(t):
    for g in segs:
        if g["tl0"] <= t < g["tl1"]:
            return g["path"], g["src0"] + (t - g["tl0"]) * g["speed"]
    return None, None


words = []
for s in d["tracks"][2]["segments"]:
    k, o = m[s["material_id"]]
    t0 = s["target_timerange"]["start"] / 1e6
    for r in o.get("text_info_resources") or []:
        km, mo = m.get(r.get("text_material_id"), (None, {}))
        if km != "texts":
            continue
        W = mo.get("words") or {}
        for txt, a, b in zip(W.get("text", []), W.get("start_time", []), W.get("end_time", [])):
            if not txt.strip():
                continue
            ta, tb = t0 + a / 1000, t0 + b / 1000
            p, sa = to_src(ta)
            p2, sb = to_src(max(ta, tb - 0.01))
            words.append({"w": txt.strip(), "tl_s": round(ta, 3), "tl_e": round(tb, 3), "path": p,
                          "s": None if sa is None else round(sa, 3),
                          "e": None if (sb is None or p2 != p) else round(sb + 0.01, 3)})
json.dump({"segments": segs, "words": words}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print(len(segs), "segments,", len(words), "words")
