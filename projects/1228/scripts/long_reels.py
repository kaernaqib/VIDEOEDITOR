"""v4 long reels (60-120 s) cut straight from the 1228 timeline, rendered in the poster-frame style.

usage: python long_reels.py WORK_DIR OUT_DIR ID [ID ...] [--still] [--reuse-band] [--plan-only]
  reads  WORK_DIR/source_map.json (1228 timeline -> source segments + word timings), WORK_DIR/long_plan.json,
         WORK_DIR/poster_hooks.json (_series poster + per-reel "sfx" under key "L<ID>")
  writes WORK_DIR/long/rID/{job.json, audio.wav} and OUT_DIR/long_ID.mp4
"""
import json, os, re, subprocess, sys

work, out_dir = sys.argv[1], sys.argv[2]
ids = [a.zfill(2) for a in sys.argv[3:] if not a.startswith("--")]
flags = [a for a in sys.argv[3:] if a.startswith("--")]
L = lambda p: json.load(open(p, encoding="utf-8"))
SM, PLAN, HOOKS = L(f"{work}/source_map.json"), L(f"{work}/long_plan.json"), L(f"{work}/poster_hooks.json")
SEG, WORDS = SM["segments"], SM["words"]
FPS = 30
SKIP = ("100 POPULAR MEMES", "TV Static")          # 1228's own meme inserts; we add our own SFX instead
FIX = [(r"\b(saint|st)\s+(kilda|hilda)\b", "St Kilda"), (r"\bse[nk]+ilda\b", "St Kilda"), (r"\bhellwood\b", "Elwood"),
       (r"\bshine of remembrance\b", "Shrine of Remembrance"), (r"\bremembrance of shrine\b", "Shrine of Remembrance"),
       (r"\b(prince|queens) victoria market\b", "Queen Victoria Market"), (r"\bnasional galeri\b", "National Gallery"),
       (r"\bnational galeri\b", "National Gallery"), (r"\bspin\b", "bin"), (r"\bbotanical garden\b", "Botanical Garden"),
       (r"\bstate library\b", "State Library"), (r"\bbrighton\b", "Brighton"), (r"\bmelbourne\b", "Melbourne"),
       (r"\bsydney\b", "Sydney"), (r"\bindonesia\b", "Indonesia"), (r"\bmalaysia\b", "Malaysia"),
       (r"\bRoyal Botanical Garden\b", "Royal Botanic Gardens"), (r"\bof victor who serve\b", "of Victoria who served"),
       (r"\bgrateful man\b", "grateful people"), (r"\bman and woman\b", "men and women")]
FILLER = {"aa", "aaa", "er", "erm", "hmm", "uh", "emm", "huh"}


def keep_intervals(a, b, max_sil):
    """Timeline intervals inside [a, b] with long silences shortened to max_sil (half kept each side)."""
    ws = sorted((w["tl_s"], w["tl_e"]) for w in WORDS if w["tl_s"] >= a and w["tl_e"] <= b)
    marks = [a] + [x for s, e in ws for x in (s, e)] + [b]
    out, cur = [], a
    for i in range(0, len(marks) - 1, 2):                    # (gap start, gap end) pairs: a..first word, word..word ...
        g0, g1 = marks[i], marks[i + 1]
        if g1 - g0 > max_sil:
            out.append((cur, g0 + max_sil / 2))
            cur = g1 - max_sil / 2
    out.append((cur, b))
    return [(s, e) for s, e in out if e - s > 0.05]


def map_to_source(iv):
    """timeline interval -> list of (segment, t0_src, t1_src, tl0, tl1); meme inserts dropped."""
    s, e = iv
    res = []
    for g in SEG:
        a, b = max(s, g["tl0"]), min(e, g["tl1"])
        if b - a <= 0.03 or any(k in g["path"] for k in SKIP):
            continue
        res.append((g, g["src0"] + (a - g["tl0"]) * g["speed"], g["src0"] + (b - g["tl0"]) * g["speed"], a, b))
    return res


def build(r):
    rid = r["id"]
    rd = f"{work}/long/r{rid}"
    os.makedirs(rd, exist_ok=True)
    pieces = []
    for a, b in r["ranges"]:
        for iv in keep_intervals(a, b, PLAN.get("max_silence", 1.6)):
            pieces += map_to_source(iv)
    # exact frame boundaries on the new timeline (cumulative rounding -> no drift between picture and sound)
    clips, tl_map, t_new = [], [], 0.0
    for g, s0, s1, tl0, tl1 in pieces:
        d = tl1 - tl0
        f0, f1 = round(t_new * FPS), round((t_new + d) * FPS)
        if f1 > f0:
            clips.append({"path": g["path"], "t0": s0, "t1": s1, "frames": f1 - f0, "f": r.get("f", 0.55),
                          "vol": g.get("vol", 1.0), "start": f0 / FPS, "dur": (f1 - f0) / FPS})
            tl_map.append((tl0, tl1, f0 / FPS))
        t_new += d
    total = round(t_new * FPS) / FPS

    def to_new(t):
        for tl0, tl1, n0 in tl_map:
            if tl0 - 0.01 <= t <= tl1 + 0.01:
                return n0 + (t - tl0)
        return None

    # words on the new timeline, then caption phrases (<= 4 words, break on pauses / cuts)
    words = []
    for w in WORDS:
        s, e = to_new(w["tl_s"]), to_new(w["tl_e"])
        if s is None or e is None or e < s or w["w"].strip().lower() in FILLER:
            continue
        words.append({"w": w["w"].strip(), "s": round(s, 3), "e": round(e, 3)})
    caps, cur = [], []
    for w in words:
        if cur and (len(cur) >= 4 or w["s"] - cur[-1]["e"] > 0.35):
            caps.append(cur); cur = []
        cur.append(w)
    if cur:
        caps.append(cur)
    captions = []
    for c in caps:
        txt = " ".join(x["w"] for x in c)
        for pat, rep in FIX:
            txt = re.sub(pat, rep, txt, flags=re.I)
        captions.append({"a": c[0]["s"], "b": c[-1]["e"], "text": txt, "keyword": None})

    # audio: voice from every clip (photos = silence) + quiet music bed
    audio = f"{rd}/audio.wav"
    if "--reuse-band" not in flags or not os.path.exists(audio):
        inputs, fc, labels = [], [], []
        for k, c in enumerate(clips):
            img = os.path.splitext(c["path"])[1].lower() in (".jpg", ".jpeg", ".png")
            if img:
                inputs += ["-f", "lavfi", "-t", f"{c['dur']:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
            else:
                inputs += ["-ss", f"{c['t0']:.3f}", "-t", f"{c['dur']:.3f}", "-i", c["path"]]
            fc.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={c['vol']},"
                      f"apad,atrim=0:{c['dur']:.3f},asetpts=PTS-STARTPTS,afade=t=in:d=0.02,"
                      f"afade=t=out:st={max(0, c['dur'] - 0.02):.3f}:d=0.02[a{k}]")
            labels.append(f"[a{k}]")
        mus = PLAN.get("music")
        n = len(clips)
        fc.append("".join(labels) + f"concat=n={n}:v=0:a=1[voice]")
        if mus:
            off = 60 * (int(rid) - 1) + 30
            inputs += ["-ss", str(off), "-t", f"{total:.3f}", "-i", mus["file"]]
            fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={mus['vol']},"
                      f"afade=t=out:st={max(0, total - 1.5):.2f}:d=1.5[mus];[voice][mus]amix=inputs=2:normalize=0:duration=first[mix]")
        else:
            fc.append("[voice]anull[mix]")
        fc.append("[mix]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[out]")
        script = f"{rd}/audio_fc.txt"
        open(script, "w", encoding="utf-8").write(";".join(fc))
        r_ = subprocess.run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-/filter_complex", script, "-map", "[out]",
                                                                       "-t", f"{total:.3f}", "-c:a", "pcm_s16le", audio],
                            capture_output=True, text=True)
        if r_.returncode:
            raise SystemExit(r_.stderr[-1500:])

    series = HOOKS.get("_series", {})
    hk = HOOKS.get(f"L{rid}", {})
    sfx_dir = series.get("sfx_dir", "D:/Video/_sfx")
    lib = {x["name"]: x for x in L(f"{sfx_dir}/library.json")}
    def when(s):
        """"t": seconds, or "at": a phrase in the captions (+ "off" seconds after that caption starts)."""
        if "t" in s:
            return s["t"]
        hits = [c for c in captions if s["at"].lower() in c["text"].lower()]
        if not hits:
            raise SystemExit(f"reel {rid}: SFX anchor not found: {s['at']!r}")
        return round(hits[s.get("nth", 0)]["a"] + s.get("off", 0.0), 2)

    sfx = [{"t": when(s), "file": lib[s["name"]]["file"], "vol": s.get("vol", 0.4),
            "dur": s.get("dur", min(2.5, lib[s["name"]]["dur"]))} for s in hk.get("sfx", [])]
    job = {"out": f"{out_dir}/long_{rid}.mp4", "tmp": f"{rd}/_poster",
           "poster": {"image": series["poster_image"], "zoom": 1.0, "contrast": 1.0, "saturation": 1.0},
           "headline": r["headline"], "accent_line": r.get("accent_line", 0),
           "clips": [{k: c[k] for k in ("path", "t0", "t1", "frames", "f")} for c in clips],
           "audio": audio, "sfx": sfx, "sfx_dir": sfx_dir, "captions": captions, "words": words}
    jp = f"{rd}/job.json"
    json.dump(job, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"reel {rid} '{r['title']}': {total:.1f}s, {len(clips)} clips, {len(captions)} captions -> {jp}")
    open(f"{rd}/transcript.txt", "w", encoding="utf-8").write(
        "\n".join(f"{c['a']:6.1f}  {c['text']}" for c in captions))
    return jp


os.makedirs(out_dir, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
renderer = os.path.join(here, "..", "..", "..", "skills", "poster-frame-reel", "scripts", "render_poster_reel.py")
if not os.path.exists(renderer):
    renderer = os.path.expanduser("~/.claude/skills/poster-frame-reel/scripts/render_poster_reel.py")
for r in PLAN["reels"]:
    if ids and r["id"] not in ids:
        continue
    jp = build(r)
    if "--plan-only" not in flags:
        subprocess.run([sys.executable, renderer, jp] + [f for f in flags if f in ("--still", "--reuse-band")], check=True)
