"""suggest.py - draf pelan dari transkrip: pecah ayat ikut jeda, pilih kata kunci besar, cadang icon dan jenis
B-roll ikut kata dalam skrip (icon_map.json). Claude semak dan baiki draf ni sebelum render.

usage: PY suggest.py words.json --video SRC [--t0 0 --t1 60] [--theme gold] [--out plan_draft.json]
words.json: senarai {"w","s","e"} (job.json "words" pun boleh: beri path job.json) atau [[s, e, w], ...]
"""
import argparse, json, os, re

ap = argparse.ArgumentParser()
ap.add_argument("words")
ap.add_argument("--video", required=True)
ap.add_argument("--t0", type=float, default=0)
ap.add_argument("--t1", type=float, default=1e9)
ap.add_argument("--theme", default="gold")
ap.add_argument("--out", default="plan_draft.json")
A = ap.parse_args()

raw = json.load(open(A.words, encoding="utf-8"))
if isinstance(raw, dict):
    raw = raw.get("words", raw)
W = []
for x in raw:
    if isinstance(x, dict):
        W.append((float(x["s"]), float(x["e"]), x["w"]))
    else:
        W.append((float(x[0]), float(x[1]), str(x[2])))
W = [w for w in W if A.t0 <= w[0] < A.t1]
M = json.load(open(os.path.join(os.path.dirname(__file__), "icon_map.json"), encoding="utf-8"))
STOP = set("dan yang ni tu je ke kat dekat untuk the a of to is and so okey ok haa ha kan lah eh nak dah tak "
           "you i kita aku dia korang saya ini itu pun lagi macam mana apa".split())

# sentences: break on pause > 0.45 s or 8 words
segs, cur = [], []
for w in W:
    if cur and (w[0] - cur[-1][1] > 0.45 or len(cur) >= 8):
        segs.append(cur); cur = []
    cur.append(w)
if cur:
    segs.append(cur)


def match(text, table):
    t = " " + text.lower() + " "
    out = []
    for name, keys in table.items():
        for k in keys:
            if re.search(r"(?<![a-z])" + re.escape(k.lower()), t):
                out.append((name, k)); break
    return out


caps, icons, notes, last_icon = [], [], [], -9
for sg in segs:
    text = " ".join(w[2] for w in sg)
    words = [w for w in sg]
    big = None
    for w in reversed(words):
        if len(re.sub(r"\W", "", w[2])) >= 4 and w[2].lower() not in STOP:
            big = w; break
    out = sg[-1][1] + 0.35
    if big and big is not words[0]:
        i = words.index(big)
        small = [[w[2], round(w[0], 2)] for w in words[:i]][-5:]
        bigl = [[w[2].strip(",.").capitalize(), round(w[0], 2)] for w in words[i:i + 2]]
        caps.append({"small": small, "big": bigl, "out": round(out, 2)})
    else:
        caps.append({"small": [[w[2], round(w[0], 2)] for w in words][-6:], "out": round(out, 2)})
    ic = match(text, M["icons"])
    if ic and sg[0][0] - last_icon > 4:
        icons.append({"icon": ic[0][0], "t": round(sg[0][0], 2), "out": round(out - 0.1, 2),
                      "side": "left" if len(icons) % 2 else "right", "_why": ic[0][1]})
        last_icon = sg[0][0]
    sc = match(text, M["scenes"])
    if sc:
        notes.append({"t": round(sg[0][0], 2), "out": round(out, 2), "text": text,
                      "scene_ideas": [f"{n} (kata: {k})" for n, k in sc]})
    print(f"{sg[0][0]:7.2f}  {text}" + (f"   [icon {ic[0][0]}]" if ic else "") +
          (f"   [B-roll: {', '.join(n for n, _ in sc)}]" if sc else ""))

plan = {"out": "D:/CLAUDE/kerja/<projek>/preview/newera/<nama>.mp4", "video": A.video, "t0": W[0][0] if W else 0,
        "pieces": [[W[0][0] if W else 0, (W[-1][1] + 0.4) if W else 1]], "theme": A.theme,
        "captions": caps, "icons": icons, "rings": [], "scenes": [], "_scene_ideas": notes}
json.dump(plan, open(A.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("draf:", A.out, f"({len(caps)} caption, {len(icons)} icon, {len(notes)} idea B-roll)")
