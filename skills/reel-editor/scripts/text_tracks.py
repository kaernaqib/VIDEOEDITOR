"""Add caption / header / label text clips to a CapCut draft, cloned from the harvested text templates.

usage: python3 text_tracks.py WORK_DIR IN_PROJECT_DIR OUT_DIR
  WORK_DIR: captions.json (captions.py), text_templates.json (harvest_text.py)
  IN_PROJECT_DIR: draft_info.json (+ draft_meta_info.json) to build on: build.py's output, or a staged copy of
                  the CURRENT project (keeps the user's edits). Text tracks this script added before are replaced.
Writes OUT_DIR/draft_info.json + draft_meta_info.json + text_report.json (md5).
Keyword pops: second line of the same text box, highlight style, size x1.5 (x2.0 when "big").
"""
import copy, hashlib, json, os, sys, time, uuid

work, proj, outd = sys.argv[1:4]
C = json.load(open(f"{work}/captions.json", encoding="utf-8"))
T = json.load(open(f"{work}/text_templates.json", encoding="utf-8"))
assert "caption" in T, "no caption template: run harvest_text.py on the REEL TEMPLATE project"
name = next(n for n in ("draft_info.json", "draft_content.json") if os.path.exists(f"{proj}/{n}"))
D = json.load(open(f"{proj}/{name}", encoding="utf-8"))
meta_p = f"{proj}/draft_meta_info.json"
meta = json.load(open(meta_p, encoding="utf-8")) if os.path.exists(meta_p) else None
M = D["materials"]
TOTAL = D["duration"]
TAG = "reel-editor"           # marks tracks we own so re-runs replace them
U = lambda: str(uuid.uuid4()).upper()
u16 = lambda s: len(s.encode("utf-16-le")) // 2          # CapCut ranges count UTF-16 units
us = lambda t: int(round(t * 30)) * 1000000 // 30        # snap to 30 fps frames, in microseconds

D["tracks"] = [t for t in D["tracks"] if t.get("name") != TAG]


def add(kind, tmpl, **kw):
    o = copy.deepcopy(tmpl)
    o["id"] = U()
    o.update(kw)
    M.setdefault(kind, []).append(o)
    return o["id"]


def styled(base, rng, size_mul=1.0, upper=False):
    s = copy.deepcopy(base)
    s["range"] = rng
    if "size" in s:
        s["size"] = round(s["size"] * size_mul, 2)
    return s


def text_clip(role, a, b, text, styles):
    t = T[role]
    content = json.loads(t["material"]["content"])
    content["text"], content["styles"] = text, styles
    mid = add("texts", t["material"], content=json.dumps(content, ensure_ascii=False, separators=(",", ":")))
    s = copy.deepcopy(t["segment"])
    s.update({"id": U(), "material_id": mid, "extra_material_refs": [add(k, o) for k, o in t["refs"]],
              "target_timerange": {"start": us(a), "duration": max(us(b) - us(a), us(0.2))},
              "keyframe_refs": [], "common_keyframes": []})
    return s


def new_track(role):
    tr = copy.deepcopy(T[role]["track"])
    tr.update(id=U(), name=TAG, segments=[])
    return tr


cap = T["caption"]
cap_tr = new_track("caption")
for c in C["captions"]:
    a, b = max(0.0, c["a"]), min(c["b"], TOTAL / 1e6)
    if b - a < 0.1:
        continue
    if c["keyword"]:
        text = f"{c['text']}\n{c['keyword']}" if c["text"] else c["keyword"]
        k0 = u16(text) - u16(c["keyword"])
        styles = ([styled(cap["base_style"], [0, k0])] if k0 else []) + \
                 [styled(cap["hi_style"], [k0, u16(text)], 2.0 if c["big"] else 1.5)]
    else:
        text = c["text"]
        styles = [styled(cap["base_style"], [0, u16(text)])]
    cap_tr["segments"].append(text_clip("caption", a, b, text, styles))

extra = []
for role, items in (("header", C.get("headers", [])), ("header", C.get("labels", []))):
    if not items:
        continue
    r = role if role in T else "title" if "title" in T else "caption"
    tr = new_track(r)
    tpl_styles = T[r]["styles"]
    for h in items:
        text = f"{h['num']} {h['title']}" if "num" in h else h["text"]
        if "num" in h and len(tpl_styles) >= 2:      # number in the template's first style, title in the second
            n = u16(h["num"])
            styles = [styled(tpl_styles[0], [0, n]), styled(tpl_styles[-1], [n, u16(text)])]
        else:
            st = styled(tpl_styles[0], [0, u16(text)])
            if h.get("kind") in ("bad", "good"):
                st.setdefault("fill", {}).setdefault("content", {}).setdefault("solid", {})["color"] = \
                    [1.0, 0.23, 0.19] if h["kind"] == "bad" else [0.2, 0.78, 0.35]
            styles = [st]
        tr["segments"].append(text_clip(r, h["a"], min(h["b"], TOTAL / 1e6), text, styles))
    tr["segments"].sort(key=lambda s: s["target_timerange"]["start"])
    extra.append(tr)

D["tracks"] += [cap_tr] + extra

# sanity: no overlaps inside our tracks, every ref resolves
ids = {o["id"] for v in M.values() if isinstance(v, list) for o in v if isinstance(o, dict) and "id" in o}
for tr in [cap_tr] + extra:
    prev = -1
    for s in tr["segments"]:
        st, du = s["target_timerange"]["start"], s["target_timerange"]["duration"]
        assert st >= prev, ("text clips overlap at", st / 1e6)
        assert st + du <= TOTAL + 1, ("text runs past the end", st / 1e6)
        assert s["material_id"] in ids and all(r in ids for r in s["extra_material_refs"])
        prev = st + du

os.makedirs(outd, exist_ok=True)
blob = json.dumps(D, ensure_ascii=False, separators=(",", ":"))
open(f"{outd}/{name}", "w", encoding="utf-8").write(blob)
if meta:
    meta["tm_draft_modified"] = int(time.time() * 1e6)
    json.dump(meta, open(f"{outd}/draft_meta_info.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
md5 = hashlib.md5(blob.encode("utf-8")).hexdigest()
json.dump({"md5": md5, "captions": len(cap_tr["segments"]), "extra_tracks": [len(t["segments"]) for t in extra]},
          open(f"{outd}/text_report.json", "w"))
print(f"text: {len(cap_tr['segments'])} captions, extra tracks {[len(t['segments']) for t in extra]}, md5 {md5}")
