"""Shared helpers for the CapCut talking-head workflow."""
import json, os, uuid

FPS = 30


def U():
    return str(uuid.uuid4()).upper()


def fr(t, fps=FPS):
    return int(round(t * fps))


def us(frames, fps=FPS):
    """frames -> CapCut microseconds (CapCut floors to the microsecond)."""
    return int(frames * 1000000 // fps)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(p, obj, compact=False):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        if compact:
            f.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
        else:
            json.dump(obj, f, ensure_ascii=False, indent=1)


def runs(mask):
    """[(start, end)) index runs where mask is True."""
    out, i, n = [], 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def snap_to_cuts(items, cuts, thr=0.5, eps=0.02):
    """No camera flashes next to an overlay (graphic or cutaway)."""
    cuts = sorted(set(round(c, 4) for c in cuts))
    items = sorted(items, key=lambda x: x["a"])
    log = []
    prev_end = 0.0
    for it in items:
        a, b = it["a"], it["b"]
        maxd = it.get("max_dur") or 1e9
        before = [c for c in cuts if c <= a + eps]
        if before:
            p = before[-1]
            if eps < a - p < thr and p >= prev_end - eps:
                log.append(f"{it.get('name', '?')}: start {a:.3f} -> {p:.3f} (was {round((a - p) * 30)}f after a cut)")
                a = p
        after = [c for c in cuts if c >= b - eps]
        if after:
            n = after[0]
            if eps < n - b < thr:
                if n - a <= maxd + eps:
                    log.append(f"{it.get('name', '?')}: end {b:.3f} -> {n:.3f} (camera showed {round((n - b) * 30)}f)")
                    b = n
                else:
                    inside = [c for c in cuts if a + 1.0 < c < b - eps]
                    if inside and b - inside[-1] < thr:
                        log.append(f"{it.get('name', '?')}: end {b:.3f} -> {inside[-1]:.3f} (could not stretch)")
                        b = inside[-1]
        it["a"], it["b"] = a, b
        prev_end = b
    for x, y in zip(items, items[1:]):
        gap = y["a"] - x["b"]
        if eps < gap < thr:
            if y["a"] - x["a"] <= (x.get("max_dur") or 1e9) + eps:
                log.append(f"{x.get('name', '?')}: end {x['b']:.3f} -> {y['a']:.3f} (closes a {round(gap * 30)}f gap)")
                x["b"] = y["a"]
            else:
                log.append(f"{y.get('name', '?')}: start {y['a']:.3f} -> {x['b']:.3f} (closes a {round(gap * 30)}f gap)")
                y["a"] = x["b"]
    return log


def all_materials(draft):
    m = {}
    for k, v in draft["materials"].items():
        if isinstance(v, list):
            for o in v:
                if isinstance(o, dict) and "id" in o:
                    m[o["id"]] = (k, o)
    return m


def validate(draft):
    """Refuse a draft CapCut would choke on: dangling refs, duplicate ids, overlaps, keys outside clips."""
    ids = set()
    for k, v in draft["materials"].items():
        if isinstance(v, list):
            for x in v:
                if isinstance(x, dict) and "id" in x:
                    assert x["id"] not in ids, ("duplicate material id", k)
                    ids.add(x["id"])
    total = draft["duration"]
    for ti, tr in enumerate(draft["tracks"]):
        prev = -1
        for s in tr["segments"]:
            assert s["material_id"] in ids, ("missing material", ti)
            assert all(r in ids for r in s["extra_material_refs"]), ("missing extra material", ti)
            st, du = s["target_timerange"]["start"], s["target_timerange"]["duration"]
            assert du > 0 and st >= prev, (tr["type"], "overlap or empty clip at", st / 1e6)
            assert st + du <= total + 1, (tr["type"], "clip runs past the end", (st + du) / 1e6)
            src = s.get("source_timerange")
            if src:
                for k in s.get("common_keyframes") or []:
                    for p in k["keyframe_list"]:
                        assert src["start"] <= p["time_offset"] < src["start"] + src["duration"] + 1, \
                            ("keyframe outside its clip", tr["type"], st / 1e6)
            prev = st + du
    main = draft["tracks"][0]["segments"]
    assert main[0]["target_timerange"]["start"] == 0, "main track must start at 0"
    for a, b in zip(main, main[1:]):
        assert a["target_timerange"]["start"] + a["target_timerange"]["duration"] == b["target_timerange"]["start"], \
            ("gap on the main track at", b["target_timerange"]["start"] / 1e6)
    return True
