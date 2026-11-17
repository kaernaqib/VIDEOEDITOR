"""Pixabay stock B-roll for every reel's plan. usage: python fetch_broll.py WORK_DIR OUT_FOLDER
writes WORK_DIR/broll.json {query: {device, w, h, dur, page}} and OUT_FOLDER/credits.txt
"""
import json, os, re, sys, urllib.parse, urllib.request

work, outd = sys.argv[1], sys.argv[2]
os.makedirs(outd, exist_ok=True)
key = os.environ["PIXABAY_API_KEY"]
P = json.load(open(f"{work}/reel_plan.json", encoding="utf-8"))
dbp = f"{work}/broll.json"
DB = json.load(open(dbp, encoding="utf-8")) if os.path.exists(dbp) else {}
used = {v["id"] for v in DB.values() if v}
UA = {"User-Agent": "reel-editor/1.0"}

for rid, plan in P.items():
    for anchor, q in plan["broll"]:
        if q in DB:
            continue
        url = "https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
            {"key": key, "q": q, "safesearch": "true", "per_page": 15})
        try:
            hits = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))["hits"]
        except Exception as e:
            print("search failed", q, type(e).__name__); DB[q] = None; continue
        hits = [h for h in hits if h["id"] not in used and 3 <= h["duration"] <= 60]
        if not hits:
            print("no hit", q); DB[q] = None; continue
        qw = set(q.lower().split())
        tagset = lambda h: set(t.strip() for t in h.get("tags", "").lower().replace(",", " ").split())
        hits = [h for h in hits if qw <= tagset(h)] or [h for h in hits if len(qw & tagset(h)) >= max(1, len(qw) - 1)]
        if not hits:
            print("no tag match", q); DB[q] = None; continue
        hits.sort(key=lambda h: (-len(qw & tagset(h)), -(h["videos"]["medium"]["height"] > h["videos"]["medium"]["width"]), -h.get("downloads", 0)))
        h = hits[0]
        v = h["videos"]["medium"] if h["videos"]["medium"].get("url") else h["videos"]["small"]
        slug = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")
        dst = os.path.join(outd, f"pixabay_{slug}_{h['id']}.mp4")
        if not os.path.exists(dst):
            data = urllib.request.urlopen(urllib.request.Request(v["url"], headers=UA), timeout=120).read()
            open(dst, "wb").write(data)
        used.add(h["id"])
        DB[q] = {"id": h["id"], "device": dst.replace("\\", "/"), "w": v["width"], "h": v["height"],
                 "dur": h["duration"], "page": h["pageURL"], "user": h.get("user")}
        print(f"{rid} {q!r:38} -> {os.path.basename(dst)} {v['width']}x{v['height']} {h['duration']}s")
        json.dump(DB, open(dbp, "w", encoding="utf-8"), indent=1)
json.dump(DB, open(dbp, "w", encoding="utf-8"), indent=1)
with open(os.path.join(outd, "credits.txt"), "w", encoding="utf-8") as f:
    f.write("B-roll from Pixabay (Pixabay Content License, free to use). Source pages:\n")
    for q, v in DB.items():
        if v:
            f.write(f"{os.path.basename(v['device'])}  by {v['user']}  {v['page']}\n")
print("done", sum(1 for v in DB.values() if v), "clips")
