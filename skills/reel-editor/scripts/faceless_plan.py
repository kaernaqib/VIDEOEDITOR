"""Turn visual_plan.json (word-anchored) into a gap-free visual sequence that covers the whole voiceover.

usage: python3 faceless_plan.py WORK_DIR STYLE_JSON [--end-hold 1.2]
  reads  WORK_DIR/words_tl.json (or words.json): voice word timings on the timeline
         WORK_DIR/visual_plan.json: [{"from_word", "to_word", "show", "source": own|stock|ai,
                                      "device", "kind": video|photo, "w", "h", "src", "file_dur", ...}, ...]
  writes WORK_DIR/sequence.json clips (merged with an existing sequence.json's voice/music keys, if any)
Rules: entry i starts at its first word (entry 0 at 0.0) and ends where entry i+1 starts (last one: last word + end hold).
A shot longer than the style's max is split into parts; a video source continues from where the previous part
stopped, a photo or a missing device is flagged NEEDS_VISUAL so another visual can be added.
"""
import json, os, sys

work, style_p = sys.argv[1], sys.argv[2]
END_HOLD = float(sys.argv[sys.argv.index("--end-hold") + 1]) if "--end-hold" in sys.argv else 1.2
wp = f"{work}/words_tl.json" if os.path.exists(f"{work}/words_tl.json") else f"{work}/words.json"
W = {w["i"]: w for w in json.load(open(wp, encoding="utf-8")) if w.get("s") is not None}
plan = json.load(open(f"{work}/visual_plan.json", encoding="utf-8"))
style = json.load(open(style_p, encoding="utf-8"))
lo, hi = style["pacing"]["target_shot_s"]
plan.sort(key=lambda p: p["from_word"])
last_word = max(W.values(), key=lambda w: w["e"])
END = round(last_word["e"] + END_HOLD, 3)

starts = []
for k, p in enumerate(plan):
    if p["from_word"] not in W:
        raise SystemExit(f"visual {k}: from_word {p['from_word']} was cut from the edit; re-anchor it")
    starts.append(0.0 if k == 0 else round(W[p["from_word"]]["s"] - 0.04, 3))

clips, warn = [], []
for k, p in enumerate(plan):
    a, b = starts[k], (starts[k + 1] if k + 1 < len(plan) else END)
    if b - a < 0.4:
        warn.append(f"visual {k} '{p.get('show', '')}' is only {b - a:.2f}s: merge it with a neighbour")
    n = max(1, int((b - a) // hi) + (1 if (b - a) % hi > lo else 0)) if b - a > hi else 1
    step = (b - a) / n
    src = float(p.get("src", 0.0))
    for j in range(n):
        c = {k2: v for k2, v in p.items() if k2 not in ("from_word", "to_word")}
        c.update(a=round(a + j * step, 3), b=round(a + (j + 1) * step if j < n - 1 else b, 3), part=f"{j + 1}/{n}" if n > 1 else None)
        dur = c["b"] - c["a"]
        if c.get("kind", "video") == "video" and c.get("device"):
            c["src"] = round(src, 3)
            if c.get("file_dur") and src + dur > c["file_dur"] - 0.05:
                if j == 0 and dur > c["file_dur"]:
                    warn.append(f"visual {k}: clip is {c['file_dur']:.1f}s but the slot is {dur:.1f}s; split it or slow it down")
                c["src"] = round(max(0.0, c["file_dur"] - dur - 0.05), 3)
            src = c["src"] + dur
        elif j > 0 or not c.get("device"):
            c["needs_visual"] = True
        c.setdefault("audio", 0)
        c.setdefault("push", 0.03 if c.get("kind") == "photo" else 0.02)
        clips.append(c)

seq_p = f"{work}/sequence.json"
seq = json.load(open(seq_p, encoding="utf-8")) if os.path.exists(seq_p) else {}
seq.update(fps=seq.get("fps", 30), end=END, clips=clips)
json.dump(seq, open(seq_p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
for c in clips:
    flag = "  NEEDS_VISUAL" if c.get("needs_visual") else ""
    print(f"{c['a']:7.2f}-{c['b']:7.2f} ({c['b'] - c['a']:4.2f}s) [{c.get('source', '?'):5s}] {c.get('show', '')[:60]}{' ' + c['part'] if c.get('part') else ''}{flag}")
for w in warn:
    print("WARN:", w)
print(f"{len(clips)} shots, avg {END / max(1, len(clips)):.2f}s (style target {lo}-{hi}s), "
      f"{sum(1 for c in clips if c.get('needs_visual'))} need a visual -> {seq_p}")
