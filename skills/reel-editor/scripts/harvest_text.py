"""Harvest text-clip templates (caption, header, title) from the user's own CapCut template project.

usage: python3 harvest_text.py OUT_text_templates.json DRAFT_INFO.json [...]
The template project ("REEL TEMPLATE") should hold, on text tracks:
  caption: ONE text box with two colours, e.g. "caption KEYWORD" (white words + a yellow word)
  header:  a text starting with a digit, e.g. "1 TITLE"           (optional, style A listicles)
  title:   any other single-colour text, e.g. a big condensed title (optional, style B)
Everything (font, size, shadow/stroke, position, in/out animation) is cloned from these, never invented.
"""
import copy, json, sys

out, paths = sys.argv[1], sys.argv[2:]
T = {"source": []}


def mats(d):
    m = {}
    for k, v in d["materials"].items():
        if isinstance(v, list):
            for o in v:
                if isinstance(o, dict) and "id" in o:
                    m[o["id"]] = (k, o)
    return m


def color(st):
    try:
        return tuple(round(c, 2) for c in st["fill"]["content"]["solid"]["color"])
    except (KeyError, TypeError):
        return None


for p in paths:
    d = json.load(open(p, encoding="utf-8"))
    m = mats(d)
    for tr in d["tracks"]:
        if tr["type"] != "text":
            continue
        for s in tr["segments"]:
            kind, mat = m.get(s["material_id"], (None, None))
            if kind != "texts":
                continue
            content = json.loads(mat["content"])
            text, styles = content.get("text", ""), content.get("styles", [])
            colours = {color(x) for x in styles}
            role = ("header" if text.strip()[:1].isdigit() else
                    "caption" if len(colours) >= 2 else "title")
            if role in T:
                continue
            entry = {"track": {k: v for k, v in tr.items() if k != "segments"},
                     "segment": copy.deepcopy(s), "material": copy.deepcopy(mat),
                     "refs": [[m[r][0], copy.deepcopy(m[r][1])] for r in s["extra_material_refs"] if r in m],
                     "text": text, "styles": styles}
            if role == "caption":
                # base = the style covering the first character, highlight = the other colour
                base = min(styles, key=lambda x: x["range"][0])
                hi = next(x for x in styles if color(x) != color(base))
                entry["base_style"], entry["hi_style"] = base, hi
            T[role] = entry
            print(f"{role:8s} <- {text!r} ({len(styles)} styles) from {p}")
    T["source"].append(p)

missing = [r for r in ("caption", "header", "title") if r not in T]
json.dump(T, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("MISSING:", missing or "nothing", "(caption is required; header/title optional)")
