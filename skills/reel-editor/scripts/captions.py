"""Split the edited transcript into short caption chunks with keyword pops, plus headers and labels.

usage: python3 captions.py WORK_DIR
  reads  WORK_DIR/words_tl.json   (from edl.py: [{"i", "w", "s", "e"}], timeline seconds; s=None = cut out)
         WORK_DIR/caption_plan.json
           {"style": "A" | "B",
            "keywords": [word indices],      yellow pop on its own line under the chunk
            "big": [word indices],           subset of keywords rendered UPPERCASE extra-large
            "headers": [{"from_word", "to_word", "num", "title"}],
            "labels":  [{"from_word", "to_word", "text", "kind": "bad" | "good" | "neutral"}],
            "max_words": 4 (A) / 6 (B), "pause": 0.35}
  writes WORK_DIR/captions.json
           {"captions": [{"a", "b", "text", "keyword", "big"}], "headers": [...], "labels": [...]}
"""
import json, re, sys

work = sys.argv[1]
W = [w for w in json.load(open(f"{work}/words_tl.json", encoding="utf-8")) if w.get("s") is not None]
P = json.load(open(f"{work}/caption_plan.json", encoding="utf-8"))
STYLE = P.get("style", "A")
MAXW = P.get("max_words", 4 if STYLE == "A" else 6)
PAUSE = P.get("pause", 0.35)
KW = set(P.get("keywords", [])) if STYLE == "A" else set()
BIG = set(P.get("big", []))
by_i = {w["i"]: w for w in W}

clean = lambda s: re.sub(r"\s+([%,.!?])", r"\1", re.sub(r"\s+", " ", s)).strip()
ends_sentence = lambda s: bool(re.search(r"[.!?]$", s.strip()))

chunks, cur = [], []


def flush(keyword=None):
    global cur
    if cur or keyword:
        chunks.append({"words": cur, "kw": keyword})
    cur = []


for k, w in enumerate(W):
    gap = w["s"] - W[k - 1]["e"] if k else 0
    if cur and (gap > PAUSE or len(cur) >= MAXW):
        flush()
    if w["i"] in KW:
        flush(w)                      # the keyword closes the chunk it belongs to, on its own line
        continue
    cur.append(w)
    if ends_sentence(w["w"]):
        flush()
flush()

# a keyword chunk with no lead-in words joins the previous chunk (as its second line) when they flow together
merged = []
for c in chunks:
    if c["kw"] and not c["words"] and merged and not merged[-1]["kw"] and len(merged[-1]["words"]) <= MAXW \
            and c["kw"]["s"] - merged[-1]["words"][-1]["e"] < PAUSE:
        merged[-1]["kw"] = c["kw"]
    else:
        merged.append(c)

out = []
for k, c in enumerate(merged):
    ws = c["words"] + ([c["kw"]] if c["kw"] else [])
    a = ws[0]["s"]
    nxt = merged[k + 1] if k + 1 < len(merged) else None
    nxt_a = (nxt["words"] or [nxt["kw"]])[0]["s"] if nxt else None
    end = ws[-1]["e"] + 0.12
    b = nxt_a if nxt_a is not None and nxt_a - ws[-1]["e"] < PAUSE else end
    if nxt_a is not None:
        b = min(b, nxt_a)
    text = clean(" ".join(x["w"] for x in c["words"]))
    kw = clean(c["kw"]["w"]).strip(",.") if c["kw"] else None
    big = bool(c["kw"] and c["kw"]["i"] in BIG)
    if big:
        kw = kw.upper()
    if b - a < 0.2:
        b = a + 0.2
    out.append({"a": round(a, 3), "b": round(b, 3), "text": text, "keyword": kw, "big": big})

# no overlaps after the minimum-length bump
for x, y in zip(out, out[1:]):
    if x["b"] > y["a"]:
        x["b"] = y["a"]


def span(d):
    a, b = by_i.get(d["from_word"]), by_i.get(d["to_word"])
    if not a or not b:
        raise SystemExit(f"word index cut out of the edit: {d}")
    return dict(d, a=round(a["s"] - 0.05, 3), b=round(b["e"] + 0.3, 3))


res = {"style": STYLE, "captions": out,
       "headers": [span(h) for h in P.get("headers", [])],
       "labels": [span(l) for l in P.get("labels", [])]}
json.dump(res, open(f"{work}/captions.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for c in out:
    kw = f"  [{c['keyword']}{' BIG' if c['big'] else ''}]" if c["keyword"] else ""
    print(f"{c['a']:7.2f}-{c['b']:7.2f}  {c['text']}{kw}")
print(f"{len(out)} chunks, {sum(1 for c in out if c['keyword'])} keyword pops, "
      f"{len(res['headers'])} headers, {len(res['labels'])} labels -> {work}/captions.json")
