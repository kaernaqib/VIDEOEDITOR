"""Per reel: run edl.py on every camera part, merge into one reel timeline, then captions.py.

usage: python cut_reel.py WORK_DIR [ids...]
writes rNN/reel_edl.json  {fps, total_frames, clips:[{path, f, src0, src1, tl0, tl1, scale0, scale1, cont}], dur_us{}}
       rNN/words_tl.json, caption_plan.json, captions.json
"""
import json, os, re, subprocess, sys

work = sys.argv[1]
only = set(sys.argv[2:])
R = {r["id"]: r for r in json.load(open(f"{work}/reels.json", encoding="utf-8"))}
P = json.load(open(f"{work}/reel_plan.json", encoding="utf-8"))
py = sys.executable
FIX = {"spin": "bin", "trend": "tram", "sekilda": "St Kilda", "senkilda": "St Kilda", "hellwood": "Elwood",
       "Hilda": "Kilda", "kau": "kau"}
FILLERS = {"aa", "aaa", "er", "erm", "hmm", "uh", "emm", "huh"}

for rid, plan in P.items():
    if only and rid not in only:
        continue
    rd = f"{work}/r{rid}"
    parts = json.load(open(f"{rd}/parts.json", encoding="utf-8"))
    print(f"== reel {rid} {R[rid]['title']}")
    clips, words_tl, tl_off, g_off = [], [], 0, 0
    for k, (part, cfg) in enumerate(zip(parts, plan["parts"])):
        pd = f"{rd}/p{k}"
        W = json.load(open(f"{pd}/words.json", encoding="utf-8"))
        for w in W:
            t = w["w"].strip()
            if t in FIX:
                w["w"] = " " + FIX[t]
        json.dump(W, open(f"{pd}/words.json", "w", encoding="utf-8"), ensure_ascii=False)
        last = k == len(parts) - 1
        remove = [list(r) for r in cfg["remove"]]
        removed_idx = {i for a, b, _ in remove for i in range(a, b + 1)}
        for w in W:      # lone fillers with no neighbour inside 0.15 s
            if w["w"].strip().lower() in FILLERS and w["i"] not in removed_idx:
                remove.append([w["i"], w["i"], "filler"])
        gone = {i for a, b, _ in remove for i in range(a, b + 1)}
        kept = [w for w in W if w["i"] not in gone]
        gaps = [[x["e"] + 0.15, y["s"] - 0.12, "gap"] for x, y in zip(kept, kept[1:]) if y["s"] - x["e"] > 0.7]
        job = {"fps": 30, "pacing": "tight", "punch": 1.12, "zooms": [[a, min(b, len(W) - 1), "push-in"] for a, b in cfg["zooms"]], "remove_words": remove,
               "remove_time": part["remove"] + gaps, "end_hold": 1.5 if last else 0.15}
        if not last:
            job["end_src"] = W[-1]["e"] + 0.15
        json.dump(job, open(f"{pd}/job.json", "w", encoding="utf-8"), indent=1)
        r = subprocess.run([py, f"{work}/scripts/edl.py", pd], capture_output=True, text=True, cwd=f"{work}/scripts")
        if r.returncode:
            raise SystemExit(r.stderr[-2000:])
        print(r.stdout.rstrip())
        E = json.load(open(f"{pd}/edl.json", encoding="utf-8"))
        for j, c in enumerate(E["clips"]):
            clips.append(dict(c, path=part["path"], f=cfg["f"], tl0=c["tl0"] + tl_off, tl1=c["tl1"] + tl_off,
                              cont=c["cont"] and j > 0))
        for w in json.load(open(f"{pd}/words_tl.json", encoding="utf-8")):
            words_tl.append({"i": w["i"] + g_off, "w": w["w"], "part": k, "li": w["i"],
                             "s": None if w["s"] is None else round(w["s"] + tl_off / 30, 3),
                             "e": None if w["e"] is None else round(w["e"] + tl_off / 30, 3)})
        tl_off += E["total_frames"]
        g_off += len(W)
    json.dump({"fps": 30, "total_frames": tl_off, "clips": clips}, open(f"{rd}/reel_edl.json", "w", encoding="utf-8"), indent=0)
    json.dump(words_tl, open(f"{rd}/words_tl.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)

    # caption plan: keywords by text, first match at least 3 s after the previous keyword
    live = [w for w in words_tl if w["s"] is not None]
    norm = lambda s: re.sub(r"[^a-z0-9$]", "", s.lower())
    kws, big, last_t = [], [], -9
    for kw in plan["kw"]:
        for w in live:
            if norm(w["w"]).startswith(norm(kw)) and w["s"] - last_t >= 3 and w["i"] not in kws:
                kws.append(w["i"]); last_t = w["s"]
                if kw in plan["big"]:
                    big.append(w["i"])
                break
    cp = {"style": "A", "keywords": kws, "big": big,
          "headers": [{"from_word": live[0]["i"], "to_word": live[-1]["i"], "num": "#" + R[rid]["num"],
                       "title": R[rid]["header"]}]}
    json.dump(cp, open(f"{rd}/caption_plan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    r = subprocess.run([py, f"{work}/scripts/captions.py", rd], capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        raise SystemExit(r.stderr[-2000:])
    print("  ", r.stdout.strip().splitlines()[-1], f"| reel {tl_off / 30:.1f}s, {len(clips)} clips")
